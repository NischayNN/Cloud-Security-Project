"""The pipeline: raw event -> normalize -> detect -> severity -> playbook -> Incident."""
from typing import Optional
from .schemas import CloudProvider, Incident, HistoryEntry, Status, EventOrigin
from .normalizer import normalize
from .rules import detect
from .severity import assess
from .playbooks import get_playbook


def process_event(raw: dict, origin: EventOrigin = EventOrigin.SUBMITTED, provider: Optional[str] = None) -> Optional[Incident]:
    event = normalize(raw, provider=provider)
    if event is None:
        return None                       # not an event we watch

    # Validate provider and origin consistency to prevent attribution corruption
    if event.provider == CloudProvider.AZURE and origin == EventOrigin.AWS_CLOUDTRAIL:
        raise ValueError("Origin 'aws-cloudtrail' cannot be used with an Azure event")
    if event.provider == CloudProvider.AWS and origin == EventOrigin.AZURE_ACTIVITY_LOG:
        raise ValueError("Origin 'azure-activity-log' cannot be used with an AWS event")

    event.origin = origin
    hit = detect(event)
    if hit is None:
        return None                       # watched event, but harmless
    itype, title, description = hit
    severity, score, reasons = assess(event, itype)
    return Incident(
        type=itype, title=title, description=description,
        severity=severity, severity_score=score, severity_reasons=reasons,
        provider=event.provider,
        resource_type=event.resource_type, resource_id=event.resource_id, actor=event.actor,
        event=event, playbook=get_playbook(itype),
        history=[HistoryEntry(status=Status.DETECTED, note="Incident automatically detected")])
