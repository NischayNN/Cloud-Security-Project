from concurrent.futures import ThreadPoolExecutor
import pytest
from app.engine import process_event
from app.sample_data import SAMPLE_EVENTS
from app.schemas import Status, Severity, EventOrigin
from app.sqlite_store import SQLiteStore
from app.store import InvalidTransition


def test_restart_preserves_complete_incident_and_duplicate_tracking(tmp_path):
    path = tmp_path / "incidents.sqlite3"
    store = SQLiteStore(path)
    original = process_event(SAMPLE_EVENTS[0], EventOrigin.AWS_CLOUDTRAIL)
    store.add(original)
    store.update_status(original.incident_id, Status.INVESTIGATING, "Investigated locally")
    expected = store.get(original.incident_id).model_dump()
    reopened = SQLiteStore(path)
    assert reopened.get(original.incident_id).model_dump() == expected
    saved, created = reopened.add(process_event(SAMPLE_EVENTS[0]))
    assert not created and saved.incident_id == original.incident_id
    assert saved.event.origin == EventOrigin.AWS_CLOUDTRAIL
    assert saved.history[-1].note == "Investigated locally"


def test_filters_sorting_and_clear_survive_reopen(tmp_path):
    path = tmp_path / "nested" / "incidents.sqlite3"
    store = SQLiteStore(path)
    for raw in SAMPLE_EVENTS:
        incident = process_event(raw)
        if incident:
            store.add(incident)
    reopened = SQLiteStore(path)
    assert len(reopened.list()) == 6
    assert len(reopened.list(Severity.CRITICAL, Status.DETECTED)) == 3
    scores = [i.severity_score for i in reopened.list()]
    assert scores == sorted(scores, reverse=True)
    assert reopened.list(status=Status.RESOLVED) == []
    reopened.clear()
    assert SQLiteStore(path).list() == []
    assert SQLiteStore(path).add(process_event(SAMPLE_EVENTS[0]))[1]


def test_invalid_transitions_do_not_change_persistent_history(tmp_path):
    store = SQLiteStore(tmp_path / "incidents.sqlite3")
    incident = process_event(SAMPLE_EVENTS[0])
    store.add(incident)
    assert store.update_status("missing", Status.INVESTIGATING) is None
    with pytest.raises(InvalidTransition):
        store.update_status(incident.incident_id, Status.CONTAINED)
    assert len(store.get(incident.incident_id).history) == 1
    for status in [Status.INVESTIGATING, Status.CONTAINED, Status.RESOLVED]:
        store.update_status(incident.incident_id, status)
    with pytest.raises(InvalidTransition):
        store.update_status(incident.incident_id, Status.INVESTIGATING)
    assert len(SQLiteStore(store.path).get(incident.incident_id).history) == 4


def test_concurrent_duplicate_writers_create_one_incident(tmp_path):
    path = tmp_path / "incidents.sqlite3"
    stores = [SQLiteStore(path) for _ in range(8)]
    def add(store):
        return store.add(process_event(SAMPLE_EVENTS[0]))
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(add, stores))
    assert sum(created for _, created in results) == 1
    assert len({i.incident_id for i, _ in results}) == 1
    assert len(SQLiteStore(path).list()) == 1


def test_caller_mutations_do_not_modify_persisted_incident(tmp_path):
    store = SQLiteStore(tmp_path / "incidents.sqlite3")
    incident = process_event(SAMPLE_EVENTS[0])
    store.add(incident)
    incident.title = "Changed outside store"
    assert store.get(incident.incident_id).title != incident.title
