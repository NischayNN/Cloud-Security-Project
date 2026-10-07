"""Turns raw AWS CloudTrail records (or EventBridge envelopes) into NormalizedEvent."""
import json
from typing import Optional
from .schemas import NormalizedEvent

WATCHED = {
    "PutBucketAcl", "PutBucketPolicy", "DeletePublicAccessBlock",
    "AttachUserPolicy", "PutUserPolicy",
    "AuthorizeSecurityGroupIngress",
}


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


def normalize(record: dict) -> Optional[NormalizedEvent]:
    record = record.get("detail", record)          # unwrap EventBridge envelope
    name = record.get("eventName")
    if name not in WATCHED:
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
        event_id=record.get("eventID", ""), source=record.get("eventSource", ""),
        event_name=name, event_time=record.get("eventTime", ""),
        region=record.get("awsRegion", ""), account_id=record.get("recipientAccountId", ""),
        actor=ident.get("userName") or ident.get("arn", "unknown"),
        source_ip=record.get("sourceIPAddress"),
        resource_type=rtype, resource_id=rid, details=details)
