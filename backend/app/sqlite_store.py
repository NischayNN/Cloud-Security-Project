"""Small local SQLite store with the same API as InMemoryStore."""
from contextlib import contextmanager
from pathlib import Path
import sqlite3

from .schemas import Incident, HistoryEntry, Status, STATUS_ORDER, now
from .store import InvalidTransition


class SQLiteStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY,
                event_id TEXT UNIQUE,
                payload TEXT NOT NULL
            )""")

    @contextmanager
    def _connection(self):
        # Connections are short-lived and never shared across FastAPI threads.
        connection = sqlite3.connect(self.path, timeout=10)
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def add(self, incident: Incident) -> tuple[Incident, bool]:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            event_id = incident.event.event_id or None
            if event_id:
                existing = connection.execute(
                    "SELECT payload FROM incidents WHERE event_id = ?", (event_id,)).fetchone()
                if existing:
                    return Incident.model_validate_json(existing[0]), False
            connection.execute("INSERT INTO incidents VALUES (?, ?, ?)",
                               (incident.incident_id, event_id, incident.model_dump_json()))
            return incident, True

    def get(self, incident_id: str):
        with self._connection() as connection:
            row = connection.execute("SELECT payload FROM incidents WHERE incident_id = ?",
                                     (incident_id,)).fetchone()
        return Incident.model_validate_json(row[0]) if row else None

    def list(self, severity=None, status=None):
        with self._connection() as connection:
            rows = connection.execute("SELECT payload FROM incidents").fetchall()
        incidents = [Incident.model_validate_json(row[0]) for row in rows]
        items = [i for i in incidents if (severity is None or i.severity == severity)
                 and (status is None or i.status == status)]
        return sorted(items, key=lambda i: (i.severity_score, i.created_at), reverse=True)

    def update_status(self, incident_id: str, new_status: Status, note: str = ""):
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute("SELECT payload FROM incidents WHERE incident_id = ?",
                                     (incident_id,)).fetchone()
            if row is None:
                return None
            incident = Incident.model_validate_json(row[0])
            index = STATUS_ORDER.index(incident.status)
            if index == len(STATUS_ORDER) - 1:
                raise InvalidTransition("Incident is already Resolved; no further changes are allowed.")
            allowed = STATUS_ORDER[index + 1]
            if new_status != allowed:
                raise InvalidTransition(
                    f"Cannot move from {incident.status.value} to {new_status.value}. Next allowed status: {allowed.value}.")
            incident.status = new_status
            incident.updated_at = now()
            incident.history.append(HistoryEntry(status=new_status, note=note or "Status changed by analyst"))
            connection.execute("UPDATE incidents SET payload = ? WHERE incident_id = ?",
                               (incident.model_dump_json(), incident_id))
            return incident

    def clear(self):
        with self._connection() as connection:
            connection.execute("DELETE FROM incidents")
