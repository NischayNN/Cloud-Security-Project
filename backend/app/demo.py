"""Run:  python -m app.demo   (from the backend/ folder)"""
from .sample_data import SAMPLE_EVENTS
from .engine import process_event
from .schemas import EventOrigin

for raw in SAMPLE_EVENTS:
    inc = process_event(raw, EventOrigin.DEMO)
    if inc is None:
        print(f"{raw['eventID']}  {raw['eventName']:<32} -> no incident")
        continue
    print(f"{raw['eventID']}  {raw['eventName']:<32} -> [{inc.severity.value:<8}] {inc.title}  (score {inc.severity_score})")
    for r in inc.severity_reasons:
        print(f"           - {r}")
