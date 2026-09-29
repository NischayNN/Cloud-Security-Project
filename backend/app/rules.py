"""Rule-based detection. Each rule: NormalizedEvent -> (IncidentType, title, description) or None."""
from typing import Optional
from .schemas import NormalizedEvent, IncidentType

ADMIN_POLICY = "arn:aws:iam::aws:policy/AdministratorAccess"


def is_wildcard_action(a: str) -> bool:
    return a == "*" or a.endswith(":*")


def rule_public_s3(e: NormalizedEvent):
    if e.resource_type == "s3_bucket" and e.details.get("public_permissions"):
        return (IncidentType.PUBLIC_S3, f"Public S3 bucket: {e.resource_id}",
                f"{e.actor} made bucket '{e.resource_id}' publicly accessible via {e.event_name}.")


def rule_excessive_iam(e: NormalizedEvent):
    if e.resource_type != "iam_principal":
        return None
    d = e.details
    bad = d.get("policy_arn") == ADMIN_POLICY or any(
        s["effect"] == "Allow" and any(is_wildcard_action(a) for a in s["actions"])
        for s in d.get("statements", []))
    if bad:
        return (IncidentType.EXCESSIVE_IAM, f"Excessive IAM permissions for {e.resource_id}",
                f"{e.actor} granted overly broad permissions to '{e.resource_id}' via {e.event_name}.")


def rule_open_ssh(e: NormalizedEvent):
    if e.resource_type != "security_group":
        return None
    for r in e.details.get("rules", []):
        world = r["cidr"] in ("0.0.0.0/0", "::/0")
        covers_22 = r["protocol"] in ("tcp", "-1") and (
            r["protocol"] == "-1" or (r["from_port"] is not None and r["from_port"] <= 22 <= r["to_port"]))
        if world and covers_22:
            return (IncidentType.OPEN_SSH, f"SSH open to the world: {e.resource_id}",
                    f"{e.actor} opened SSH (port 22) on {e.resource_id} to {r['cidr']}.")


RULES = [rule_public_s3, rule_excessive_iam, rule_open_ssh]


def detect(event: NormalizedEvent) -> Optional[tuple]:
    for rule in RULES:
        hit = rule(event)
        if hit:
            return hit
    return None
