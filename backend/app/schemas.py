"""Common schema shared by every part of the system (and later, other clouds)."""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Severity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class Status(str, Enum):
    DETECTED = "Detected"
    INVESTIGATING = "Investigating"
    CONTAINED = "Contained"
    RESOLVED = "Resolved"


# Incidents may only move forward, one step at a time.
STATUS_ORDER = [Status.DETECTED, Status.INVESTIGATING, Status.CONTAINED, Status.RESOLVED]


class IncidentType(str, Enum):
    PUBLIC_S3 = "public_s3_bucket"
    EXCESSIVE_IAM = "excessive_iam_permission"
    OPEN_SSH = "open_ssh_security_group"


class CloudProvider(str, Enum):
    AWS = "aws"
    AZURE = "azure"


class EventOrigin(str, Enum):
    DEMO = "demo"
    AWS_CLOUDTRAIL = "aws-cloudtrail"
    AZURE_ACTIVITY_LOG = "azure-activity-log"
    FIXTURE = "fixture"
    SUBMITTED = "submitted"


class NormalizedEvent(BaseModel):
    """Provider-independent normalized cloud event structure."""
    event_id: str
    origin: EventOrigin = EventOrigin.SUBMITTED
    provider: CloudProvider = CloudProvider.AWS
    source: str                      # e.g. s3.amazonaws.com or Microsoft.Storage
    event_name: str                  # action, e.g. PutBucketAcl or Microsoft.Storage/storageAccounts/write
    event_time: str                  # timestamp in ISO 8601
    region: str                      # region/location, e.g. ap-south-1 or eastus
    account_id: str                  # account or Azure subscription ID
    actor: str                       # identity / caller principal
    source_ip: Optional[str] = None
    resource_type: str               # resource type, e.g. s3_bucket | iam_principal | security_group
    resource_id: str                 # resource identifier or ARN / Resource ID
    details: dict[str, Any] = Field(default_factory=dict)
    raw_payload: Optional[dict[str, Any]] = Field(default_factory=dict)


class PlaybookStep(BaseModel):
    title: str
    action: str
    command: Optional[str] = None    # example remediation command
    done: bool = False


class HistoryEntry(BaseModel):
    status: Status
    timestamp: str = Field(default_factory=now)
    note: str = ""


class Incident(BaseModel):
    incident_id: str = Field(default_factory=lambda: "INC-" + uuid4().hex[:8].upper())
    type: IncidentType
    title: str
    description: str
    severity: Severity
    severity_score: int
    severity_reasons: list[str]
    status: Status = Status.DETECTED
    provider: CloudProvider = CloudProvider.AWS
    resource_type: str
    resource_id: str
    actor: str
    event: NormalizedEvent
    playbook: list[PlaybookStep]
    history: list[HistoryEntry]
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)
