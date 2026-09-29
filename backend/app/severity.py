"""Transparent score-based severity. Every point added is explained in `reasons`."""
from .schemas import NormalizedEvent, IncidentType, Severity
from .rules import ADMIN_POLICY, is_wildcard_action

SENSITIVE = ("prod", "backup", "customer", "finance", "hr", "secret", "private")
WRITE_PERMS = ("WRITE", "WRITE_ACP", "FULL_CONTROL", "s3:Put*", "s3:*", "s3:PutObject", "s3:DeleteObject")


def to_level(score: int) -> Severity:
    if score >= 80: return Severity.CRITICAL
    if score >= 60: return Severity.HIGH
    if score >= 40: return Severity.MEDIUM
    return Severity.LOW


def assess(e: NormalizedEvent, itype: IncidentType):
    d, name = e.details, e.resource_id.lower()
    score, why = 0, []

    def add(points, reason):
        nonlocal score
        score += points
        why.append(f"{reason} ({points:+d})")

    if itype == IncidentType.PUBLIC_S3:
        add(50, "Bucket is publicly accessible")
        if any(p in WRITE_PERMS for p in d["public_permissions"]): add(30, "Public WRITE access")
        if any(k in name for k in SENSITIVE): add(20, "Bucket name suggests sensitive data")

    elif itype == IncidentType.EXCESSIVE_IAM:
        stmts = [s for s in d.get("statements", []) if s["effect"] == "Allow"]
        if d.get("policy_arn") == ADMIN_POLICY or any("*" in s["actions"] and "*" in s["resources"] for s in stmts):
            add(85, "Full administrator access granted")
        elif any(is_wildcard_action(a) and "*" in s["resources"] for s in stmts for a in s["actions"]):
            add(65, "Service-wide wildcard on all resources")
        else:
            add(45, "Wildcard action limited to specific resources")

    elif itype == IncidentType.OPEN_SSH:
        add(60, "SSH reachable from the entire internet")
        if any(r["protocol"] == "-1" or (r["from_port"] == 0 and r["to_port"] == 65535) for r in d["rules"]):
            add(25, "All ports/protocols opened")
        if "prod" in d.get("group_name", "").lower(): add(20, "Production security group")
        if any(k in d.get("group_name", "").lower() for k in ("dev", "test", "sandbox")):
            add(-25, "Non-production security group")

    return to_level(score), score, why
