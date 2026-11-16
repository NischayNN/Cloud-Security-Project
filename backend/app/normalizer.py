"""Normalizes raw cloud provider audit records into provider-independent NormalizedEvent."""
import json
from typing import Callable, Optional, Union
from .schemas import CloudProvider, NormalizedEvent

WATCHED_AWS = {
    "PutBucketAcl", "PutBucketPolicy", "DeletePublicAccessBlock",
    "AttachUserPolicy", "PutUserPolicy",
    "AuthorizeSecurityGroupIngress",
}
# Backward compatibility alias
WATCHED = WATCHED_AWS


def _statements(doc) -> list[dict]:
    """Normalize an IAM/bucket policy into [{effect, principal, actions, resources}]."""
    if isinstance(doc, str):
        doc = json.loads(doc)
    stmts = doc.get("Statement", [])
    stmts = [stmts] if isinstance(stmts, dict) else stmts
    as_list = lambda v: v if isinstance(v, list) else [v] if v else []
    out = []
    for s in stmts:
        principal = s.get("Principal")
        if isinstance(principal, dict):
            principal = principal.get("AWS", "")
        out.append({"effect": s.get("Effect"), "principal": principal,
                    "actions": as_list(s.get("Action")), "resources": as_list(s.get("Resource"))})
    return out


def normalize_aws(record: dict) -> Optional[NormalizedEvent]:
    """Normalizes AWS CloudTrail records or EventBridge envelopes."""
    raw_copy = dict(record)
    record = record.get("detail", record)          # unwrap EventBridge envelope
    name = record.get("eventName")
    if name not in WATCHED_AWS:
        return None
    # A failed API call does not establish that an unsafe change happened.
    if record.get("errorCode") or record.get("errorMessage"):
        return None
    expected_source = ("s3.amazonaws.com" if name in {"PutBucketAcl", "PutBucketPolicy", "DeletePublicAccessBlock"}
                       else "iam.amazonaws.com" if name in {"AttachUserPolicy", "PutUserPolicy"}
                       else "ec2.amazonaws.com")
    if record.get("eventSource") != expected_source:
        raise ValueError("Unexpected event source")
    for field in ("eventID", "eventTime", "awsRegion", "recipientAccountId"):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError(f"Missing event metadata: {field}")
    p = record.get("requestParameters") or {}
    details, rtype, rid = {}, "", ""

    if name == "PutBucketAcl":
        rtype, rid = "s3_bucket", p["bucketName"]
        grants = p.get("AccessControlPolicy", {}).get("AccessControlList", {}).get("Grant", [])
        details["public_permissions"] = [
            g["Permission"] for g in grants if g.get("Grantee", {}).get("URI", "").endswith("AllUsers")]
    elif name == "PutBucketPolicy":
        rtype, rid = "s3_bucket", p["bucketName"]
        perms = []
        for s in _statements(p.get("bucketPolicy", {})):
            if s["effect"] == "Allow" and s["principal"] == "*":
                perms += s["actions"]
        details["public_permissions"] = perms
    elif name == "DeletePublicAccessBlock":
        rtype, rid = "s3_bucket", p["bucketName"]
        details["public_permissions"] = ["PublicAccessBlockRemoved"]
    elif name == "AttachUserPolicy":
        rtype, rid = "iam_principal", p["userName"]
        details["policy_arn"] = p["policyArn"]
    elif name == "PutUserPolicy":
        rtype, rid = "iam_principal", p["userName"]
        details["statements"] = _statements(p["policyDocument"])
    elif name == "AuthorizeSecurityGroupIngress":
        rtype, rid = "security_group", p["groupId"]
        details["group_name"] = p.get("groupName", "")
        details["rules"] = [
            {"protocol": r.get("ipProtocol"), "from_port": r.get("fromPort"),
             "to_port": r.get("toPort"), "cidr": c.get("cidrIp") or c.get("cidrIpv6")}
            for r in p.get("ipPermissions", {}).get("items", [])
            for c in (r.get("ipRanges", {}).get("items", []) + r.get("ipv6Ranges", {}).get("items", []))]

    ident = record.get("userIdentity", {})
    return NormalizedEvent(
        event_id=record.get("eventID", ""),
        provider=CloudProvider.AWS,
        source=record.get("eventSource", ""),
        event_name=name,
        event_time=record.get("eventTime", ""),
        region=record.get("awsRegion", ""),
        account_id=record.get("recipientAccountId", ""),
        actor=ident.get("userName") or ident.get("arn", "unknown"),
        source_ip=record.get("sourceIPAddress"),
        resource_type=rtype,
        resource_id=rid,
        details=details,
        raw_payload=raw_copy,
    )


def normalize_azure(record: dict) -> Optional[NormalizedEvent]:
    """Provider stub for Azure Activity Log events. Detailed parsing in subsequent phase."""
    # Azure unique event ID: eventDataId is the standard unique event record identifier.
    # We do NOT use correlationId because it groups multiple distinct operations/events.
    event_id = str(record.get("eventDataId") or record.get("id") or record.get("eventID") or "").strip()
    if not event_id:
        return None
    return NormalizedEvent(
        event_id=event_id,
        provider=CloudProvider.AZURE,
        source=str(record.get("resourceProvider", "") or record.get("eventSource", "Microsoft.Resources")),
        event_name=str(record.get("operationName", "") or record.get("eventName", "")),
        event_time=str(record.get("eventTimestamp", "") or record.get("eventTime", "")),
        region=str(record.get("resourceLocation", "") or record.get("region", "")),
        account_id=str(record.get("subscriptionId", "") or record.get("account_id", "")),
        actor=str(record.get("caller", "") or record.get("actor", "unknown")),
        source_ip=record.get("callerIpAddress") or record.get("source_ip"),
        resource_type=str(record.get("resourceType", "") or record.get("resource_type", "")),
        resource_id=str(record.get("resourceId", "") or record.get("resource_id", "")),
        details=record.get("details") or {},
        raw_payload=dict(record),
    )


NORMALIZERS: dict[CloudProvider, Callable[[dict], Optional[NormalizedEvent]]] = {
    CloudProvider.AWS: normalize_aws,
    CloudProvider.AZURE: normalize_azure,
}


def detect_provider(record: dict) -> CloudProvider:
    """Infers cloud provider from event signature if not explicitly specified."""
    raw = record.get("detail", record)
    if "eventSource" in raw and ("awsRegion" in raw or "recipientAccountId" in raw):
        return CloudProvider.AWS
    if "correlationId" in raw or "subscriptionId" in raw or "resourceProvider" in raw or "operationName" in raw:
        return CloudProvider.AZURE
    # Default to AWS for backward compatibility with existing tests and submissions
    return CloudProvider.AWS


def normalize(record: dict, provider: Optional[Union[str, CloudProvider]] = None) -> Optional[NormalizedEvent]:
    """Provider-aware dispatch to normalize a raw cloud record."""
    if provider is not None:
        target_provider = CloudProvider(provider)
    else:
        target_provider = detect_provider(record)

    handler = NORMALIZERS.get(target_provider)
    if not handler:
        raise ValueError(f"Unsupported cloud provider: {target_provider}")
    return handler(record)
