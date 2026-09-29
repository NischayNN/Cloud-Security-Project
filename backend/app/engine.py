"""The pipeline: raw event -> normalize -> detect -> severity -> playbook -> Incident."""
from typing import Optional
from .schemas import Incident, HistoryEntry, Status
from .normalizer import normalize
from .rules import detect
from .severity import assess
from .playbooks import get_playbook


def process_event(raw: dict) -> Optional[Incident]:
    event = normalize(raw)
    if event is None:
        return None                       # not an event we watch
    hit = detect(event)
    if hit is None:
        return None                       # watched event, but harmless
    itype, title, description = hit
    severity, score, reasons = assess(event, itype)
    return Incident(
        type=itype, title=title, description=description,
        severity=severity, severity_score=score, severity_reasons=reasons,
        resource_type=event.resource_type, resource_id=event.resource_id, actor=event.actor,
        event=event, playbook=get_playbook(itype),
        history=[HistoryEntry(status=Status.DETECTED, note="Incident automatically detected")])
