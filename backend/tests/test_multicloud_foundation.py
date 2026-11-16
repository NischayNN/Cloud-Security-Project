"""Tests for multi-cloud provider schema, normalizer dispatch, and legacy SQLite compatibility."""
import copy
import json
import pytest
from app.schemas import CloudProvider, EventOrigin, NormalizedEvent, Incident, IncidentType, Severity, Status
from app.normalizer import normalize, normalize_aws, normalize_azure, detect_provider, WATCHED_AWS
from app.engine import process_event
from app.sqlite_store import SQLiteStore
from tests.sample_data import SAMPLE_EVENTS


def test_cloud_provider_enum():
    assert CloudProvider.AWS == "aws"
    assert CloudProvider.AZURE == "azure"
    assert CloudProvider("aws") == CloudProvider.AWS
    assert CloudProvider("azure") == CloudProvider.AZURE
    with pytest.raises(ValueError):
        CloudProvider("gcp")


def test_normalized_event_structure_and_provider_defaults():
    event = NormalizedEvent(
        event_id="evt-100",
        source="s3.amazonaws.com",
        event_name="PutBucketAcl",
        event_time="2026-11-17T00:00:00Z",
        region="ap-south-1",
        account_id="123456789012",
        actor="student-dev",
        resource_type="s3_bucket",
        resource_id="my-bucket",
    )
    assert event.provider == CloudProvider.AWS
    assert event.origin == EventOrigin.SUBMITTED
    assert event.raw_payload == {}


def test_normalized_event_preserves_raw_payload_and_azure_provider():
    raw_azure = {
        "eventDataId": "evt-data-guid-001",
        "id": "/subscriptions/sub-123/providers/Microsoft.Insights/eventtypes/management/events/evt-az-1",
        "correlationId": "corr-uuid-1",
        "resourceProvider": "Microsoft.Storage",
        "operationName": "Microsoft.Storage/storageAccounts/write",
        "eventTimestamp": "2026-11-17T01:00:00Z",
        "resourceLocation": "eastus",
        "subscriptionId": "sub-123",
        "caller": "admin@contoso.com",
        "callerIpAddress": "203.0.113.50",
        "resourceType": "Microsoft.Storage/storageAccounts",
        "resourceId": "/subscriptions/sub-123/resourceGroups/rg-sec/providers/Microsoft.Storage/storageAccounts/mystorage",
        "properties": {"allowBlobPublicAccess": True},
    }
    event = normalize(raw_azure)
    assert event is not None
    assert event.provider == CloudProvider.AZURE
    assert event.event_id == "evt-data-guid-001"  # Preferred eventDataId
    assert event.source == "Microsoft.Storage"
    assert event.event_name == "Microsoft.Storage/storageAccounts/write"
    assert event.region == "eastus"
    assert event.account_id == "sub-123"
    assert event.actor == "admin@contoso.com"
    assert event.source_ip == "203.0.113.50"
    assert event.raw_payload == raw_azure


def test_azure_event_id_resolution_and_missing_id():
    # Uses eventDataId over id
    ev1 = normalize_azure({"eventDataId": "data-id-1", "id": "fallback-id"})
    assert ev1.event_id == "data-id-1"

    # Falls back to id when eventDataId is missing
    ev2 = normalize_azure({"id": "/subscriptions/sub/events/fallback-id"})
    assert ev2.event_id == "/subscriptions/sub/events/fallback-id"

    # Does NOT use correlationId as unique event_id
    ev3 = normalize_azure({"correlationId": "shared-corr-uuid"})
    assert ev3 is None

    # Empty/whitespace id returns None
    assert normalize_azure({}) is None
    assert normalize_azure({"eventDataId": "   "}) is None


def test_provider_detection_and_explicit_dispatch():
    aws_raw = copy.deepcopy(SAMPLE_EVENTS[0])
    # Auto-detection for AWS
    assert detect_provider(aws_raw) == CloudProvider.AWS
    norm_auto = normalize(aws_raw)
    assert norm_auto.provider == CloudProvider.AWS
    assert norm_auto.raw_payload == aws_raw

    # Explicit dispatch
    norm_explicit = normalize(aws_raw, provider="aws")
    assert norm_explicit.provider == CloudProvider.AWS

    # Azure detection
    azure_raw = {
        "eventDataId": "az-data-id-100",
        "correlationId": "corr-1",
        "subscriptionId": "sub-1",
        "operationName": "Microsoft.Authorization/roleAssignments/write",
    }
    assert detect_provider(azure_raw) == CloudProvider.AZURE
    norm_az = normalize(azure_raw)
    assert norm_az.provider == CloudProvider.AZURE
    assert norm_az.event_id == "az-data-id-100"

    # Unsupported provider raises ValueError
    with pytest.raises(ValueError):
        normalize(aws_raw, provider="unsupported")


def test_provider_origin_consistency_validation():
    aws_raw = copy.deepcopy(SAMPLE_EVENTS[0])
    azure_raw = {
        "eventDataId": "az-data-id-200",
        "subscriptionId": "sub-2",
        "operationName": "Microsoft.Storage/storageAccounts/write",
    }

    # AWS record cannot claim azure-activity-log
    with pytest.raises(ValueError, match="Origin 'azure-activity-log' cannot be used with an AWS event"):
        process_event(aws_raw, origin=EventOrigin.AZURE_ACTIVITY_LOG)

    # Azure record cannot claim aws-cloudtrail
    with pytest.raises(ValueError, match="Origin 'aws-cloudtrail' cannot be used with an Azure event"):
        process_event(azure_raw, origin=EventOrigin.AWS_CLOUDTRAIL)

    # Valid combinations succeed without error
    # AWS with AWS CloudTrail
    inc_aws = process_event(aws_raw, origin=EventOrigin.AWS_CLOUDTRAIL)
    assert inc_aws.event.origin == EventOrigin.AWS_CLOUDTRAIL
    assert inc_aws.provider == CloudProvider.AWS

    # Azure with Azure Activity Log (returns None if no security rule hit, but doesn't raise attribution error)
    res = process_event(azure_raw, origin=EventOrigin.AZURE_ACTIVITY_LOG)
    assert res is None  # no detection hit yet, but consistent origin passed validation


def test_existing_aws_detection_pipeline_unaffected():
    # S3 Public Bucket
    inc_s3 = process_event(copy.deepcopy(SAMPLE_EVENTS[0]), EventOrigin.AWS_CLOUDTRAIL)
    assert inc_s3 is not None
    assert inc_s3.provider == CloudProvider.AWS
    assert inc_s3.type == IncidentType.PUBLIC_S3
    assert inc_s3.severity == Severity.MEDIUM
    assert inc_s3.event.provider == CloudProvider.AWS

    # Admin IAM
    inc_iam = process_event(copy.deepcopy(SAMPLE_EVENTS[2]), EventOrigin.AWS_CLOUDTRAIL)
    assert inc_iam is not None
    assert inc_iam.provider == CloudProvider.AWS
    assert inc_iam.type == IncidentType.EXCESSIVE_IAM
    assert inc_iam.severity == Severity.CRITICAL

    # Open SSH
    inc_ssh = process_event(copy.deepcopy(SAMPLE_EVENTS[4]), EventOrigin.AWS_CLOUDTRAIL)
    assert inc_ssh is not None
    assert inc_ssh.provider == CloudProvider.AWS
    assert inc_ssh.type == IncidentType.OPEN_SSH
    assert inc_ssh.severity == Severity.CRITICAL

    # Harmless
    inc_harmless = process_event(copy.deepcopy(SAMPLE_EVENTS[6]), EventOrigin.AWS_CLOUDTRAIL)
    assert inc_harmless is None


def test_sqlite_backward_compatibility_with_legacy_records(tmp_path):
    db_path = tmp_path / "legacy_test.sqlite3"
    store = SQLiteStore(db_path)

    # Simulate legacy JSON serialized before provider was introduced or when provider was a plain string
    legacy_incident_json = json.dumps({
        "incident_id": "INC-LEGACY01",
        "type": "open_ssh_security_group",
        "title": "Legacy SSH incident",
        "description": "Legacy description",
        "severity": "High",
        "severity_score": 60,
        "severity_reasons": ["SSH reachable from the entire internet (+60)"],
        "status": "Detected",
        "provider": "aws",
        "resource_type": "security_group",
        "resource_id": "sg-legacy",
        "actor": "arn:aws:iam::123456789012:root",
        "event": {
            "event_id": "evt-legacy-1",
            "origin": "aws-cloudtrail",
            "provider": "aws",
            "source": "ec2.amazonaws.com",
            "event_name": "AuthorizeSecurityGroupIngress",
            "event_time": "2026-10-06T18:58:37Z",
            "region": "ap-south-1",
            "account_id": "123456789012",
            "actor": "arn:aws:iam::123456789012:root",
            "source_ip": "10.0.0.1",
            "resource_type": "security_group",
            "resource_id": "sg-legacy",
            "details": {"rules": []}
            # Note: raw_payload omitted, tests schema default factory
        },
        "playbook": [],
        "history": [{"status": "Detected", "timestamp": "2026-10-06T18:58:37Z", "note": "Auto detected"}],
        "created_at": "2026-10-06T18:58:37Z",
        "updated_at": "2026-10-06T18:58:37Z",
    })

    with store._connection() as conn:
        conn.execute("INSERT INTO incidents VALUES (?, ?, ?)",
                     ("INC-LEGACY01", "evt-legacy-1", legacy_incident_json))

    loaded = store.get("INC-LEGACY01")
    assert loaded is not None
    assert loaded.provider == CloudProvider.AWS
    assert loaded.event.provider == CloudProvider.AWS
    assert loaded.event.raw_payload == {}
    assert loaded.status == Status.DETECTED
