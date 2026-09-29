"""FastAPI app. Run from backend/:  uvicorn app.main:app --reload"""
from typing import Any, Optional
from fastapi import Body, FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .engine import process_event
from .sample_data import SAMPLE_EVENTS
from .schemas import Incident, Severity, Status
from .store import InMemoryStore, InvalidTransition

app = FastAPI(title="Multi-Cloud Incident Response API", version="0.2.0")

# Lets the React dev server (Step 3) call this API from the browser.
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://localhost:3000"],
                   allow_methods=["*"], allow_headers=["*"])

store = InMemoryStore()


class StatusUpdate(BaseModel):
    status: Status
    note: str = ""


class EventResult(BaseModel):
    detected: bool
    duplicate: bool = False
    message: str
    incident: Optional[Incident] = None


def ingest(raw: dict) -> EventResult:
    """Shared by POST /events and POST /demo/load: engine -> store."""
    try:
        incident = process_event(raw)
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise HTTPException(422, f"Could not parse event, missing or invalid field: {exc!r}")
    if incident is None:
        return EventResult(detected=False, message="No incident: event is not monitored or is harmless.")
    saved, created = store.add(incident)
    if not created:
        return EventResult(detected=True, duplicate=True, incident=saved,
                           message="Event already processed; returning the existing incident.")
    return EventResult(detected=True, incident=saved, message="Incident created.")


@app.get("/incidents", response_model=list[Incident])
def list_incidents(severity: Optional[Severity] = None, status: Optional[Status] = None):
    """All incidents, highest severity score first. Optional filters: ?severity=High&status=Detected"""
    return store.list(severity, status)


@app.get("/incidents/{incident_id}", response_model=Incident)
def get_incident(incident_id: str):
    incident = store.get(incident_id)
    if incident is None:
        raise HTTPException(404, f"Incident {incident_id} not found.")
    return incident


@app.post("/events", response_model=EventResult)
def post_event(response: Response, raw: dict[str, Any] = Body(...)):
    """Send one CloudTrail record (or EventBridge envelope). 201 = new incident, 200 = otherwise."""
    result = ingest(raw)
    if result.detected and not result.duplicate:
        response.status_code = 201
    return result


@app.post("/demo/load")
def load_demo(reset: bool = False):
    """Feed the 7 sample CloudTrail events through the engine. ?reset=true clears existing incidents first."""
    if reset:
        store.clear()
    summary = {"events_processed": 0, "incidents_created": 0, "duplicates_skipped": 0, "no_incident": 0}
    for raw in SAMPLE_EVENTS:
        result = ingest(raw)
        summary["events_processed"] += 1
        if not result.detected:
            summary["no_incident"] += 1
        elif result.duplicate:
            summary["duplicates_skipped"] += 1
        else:
            summary["incidents_created"] += 1
    return summary


@app.patch("/incidents/{incident_id}/status", response_model=Incident)
def update_status(incident_id: str, body: StatusUpdate):
    """Advance an incident one step: Detected -> Investigating -> Contained -> Resolved."""
    try:
        incident = store.update_status(incident_id, body.status, body.note)
    except InvalidTransition as exc:
        raise HTTPException(409, str(exc))
    if incident is None:
        raise HTTPException(404, f"Incident {incident_id} not found.")
    return incident
