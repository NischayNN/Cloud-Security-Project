"""In-memory incident storage. In Step 4 a DynamoDB class with these same methods replaces it."""
from threading import Lock
from typing import Optional
from .schemas import Incident, HistoryEntry, Status, STATUS_ORDER, now


class InvalidTransition(Exception):
    pass


class InMemoryStore:
    def __init__(self):
        self._incidents: dict[str, Incident] = {}
        self._by_event: dict[str, str] = {}        # event_id -> incident_id (prevents duplicates)
        self._lock = Lock()

    def add(self, incident: Incident) -> tuple[Incident, bool]:
        """Save an incident. Returns (incident, created). Re-sending the same event returns the original."""
        with self._lock:
            existing_id = self._by_event.get(incident.event.event_id)
            if existing_id and incident.event.event_id:
                return self._incidents[existing_id], False
            self._incidents[incident.incident_id] = incident
            if incident.event.event_id:
                self._by_event[incident.event.event_id] = incident.incident_id
            return incident, True

    def get(self, incident_id: str) -> Optional[Incident]:
        return self._incidents.get(incident_id)

    def list(self, severity=None, status=None) -> list[Incident]:
        items = [i for i in self._incidents.values()
                 if (severity is None or i.severity == severity) and (status is None or i.status == status)]
        return sorted(items, key=lambda i: (i.severity_score, i.created_at), reverse=True)

    def update_status(self, incident_id: str, new_status: Status, note: str = "") -> Optional[Incident]:
        """Move forward exactly one step and record it in history. None if incident not found."""
        with self._lock:
            inc = self._incidents.get(incident_id)
            if inc is None:
                return None
            cur = STATUS_ORDER.index(inc.status)
            if cur == len(STATUS_ORDER) - 1:
                raise InvalidTransition("Incident is already Resolved; no further changes are allowed.")
            allowed = STATUS_ORDER[cur + 1]
            if new_status != allowed:
                raise InvalidTransition(
                    f"Cannot move from {inc.status.value} to {new_status.value}. Next allowed status: {allowed.value}.")
            inc.status = new_status
            inc.updated_at = now()
            inc.history.append(HistoryEntry(status=new_status, note=note or "Status changed by analyst"))
            return inc

    def clear(self):
        with self._lock:
            self._incidents.clear()
            self._by_event.clear()
