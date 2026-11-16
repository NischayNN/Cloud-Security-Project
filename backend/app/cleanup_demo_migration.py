"""Idempotent cleanup migration script to purge demo records from the SQLite database."""
import os
import sqlite3
import sys
from pathlib import Path

def run_cleanup(db_path: str = None) -> dict:
    if not db_path:
        db_path = os.environ.get("CLOUD_SECURITY_DB_PATH") or str(
            Path(__file__).resolve().parent.parent / "data" / "incidents.sqlite3"
        )
    
    path = Path(db_path)
    if not path.exists():
        print(f"Database not found at {path}")
        return {"before": 0, "deleted": 0, "after": 0, "preserved_genuine": 0}

    connection = sqlite3.connect(path, timeout=10)
    try:
        with connection:
            cursor = connection.cursor()
            cursor.execute("SELECT count(*) FROM incidents")
            before_count = cursor.fetchone()[0]

            cursor.execute(
                "SELECT incident_id, event_id, json_extract(payload, '$.event.origin'), json_extract(payload, '$.title') FROM incidents WHERE json_extract(payload, '$.event.origin') = 'demo'"
            )
            demo_records = cursor.fetchall()

            cursor.execute(
                "DELETE FROM incidents WHERE json_extract(payload, '$.event.origin') = 'demo'"
            )
            deleted_count = cursor.rowcount

            cursor.execute("SELECT count(*) FROM incidents")
            after_count = cursor.fetchone()[0]

            cursor.execute(
                "SELECT incident_id, event_id, json_extract(payload, '$.event.origin'), json_extract(payload, '$.title') FROM incidents"
            )
            remaining_records = cursor.fetchall()
            
        return {
            "before": before_count,
            "deleted": deleted_count,
            "after": after_count,
            "demo_records_removed": demo_records,
            "remaining": remaining_records
        }
    finally:
        connection.close()

if __name__ == "__main__":
    res = run_cleanup()
    print(f"Before: {res['before']}")
    print(f"Deleted: {res['deleted']}")
    print(f"After: {res['after']}")
    print("Remaining incidents:")
    for r in res['remaining']:
        print(f"  {r[0]} | {r[1]} | {r[2]} | {r[3]}")
