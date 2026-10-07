# Multi-Cloud Incident Response System (AWS MVP)

Pipeline: AWS event → normalize → detect → severity → playbook → dashboard.

## Run the backend locally (Step 2)

Requires Python 3.10+. Run everything from the `backend/` folder.

**1. Create a virtual environment and install dependencies**

macOS / Linux:
```
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```
Windows (PowerShell):
```
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
```

**2. Start the API**
```
uvicorn app.main:app --reload
```
- API: http://127.0.0.1:8000
- Interactive docs (try every endpoint in the browser): http://127.0.0.1:8000/docs

**3. Load the sample events**

Open `/docs`, run `POST /demo/load`, then `GET /incidents`. Or from a terminal:
```
curl -X POST http://127.0.0.1:8000/demo/load
curl http://127.0.0.1:8000/incidents
```

**4. Run the tests**
```
python -m pytest -v
```

Incidents are stored locally in SQLite at `backend/data/incidents.sqlite3` by default. Incidents, history, and event-ID deduplication survive backend restarts. The database is ignored by Git.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/incidents` | List incidents, highest severity first. Filters: `?severity=High&status=Detected` |
| GET | `/incidents/{id}` | One incident: severity, reasons, resource, event, playbook, history |
| POST | `/events` | Send one CloudTrail record (or EventBridge envelope). `201` new incident, `200` no incident or duplicate |
| POST | `/demo/load` | Run the 7 sample events. `?reset=true` clears existing incidents first |
| PATCH | `/incidents/{id}/status` | Body `{"status": "Investigating", "note": "optional"}`. Moves forward one step; anything else returns `409` |

## Run the dashboard (Step 3)

Requires Node.js 18+. Keep the backend from the section above running in one terminal, then in a second terminal:
```
cd frontend
npm install
npm run dev
```
Open **http://localhost:5173** (use `localhost`, not `127.0.0.1`, because the backend's CORS setting allows that origin).

1. Click **Load demo incidents** to run the 7 sample AWS events through the engine (6 incidents appear). Loading is non-destructive and preserves existing incidents.
2. Click a severity card or a status chip to filter. Click an incident to open its details and playbook.
3. Use the **Mark as …** button to move it Detected → Investigating → Contained → Resolved. Each change is saved by the backend, so a page refresh keeps it.

If the backend is not at `http://127.0.0.1:8000`, copy `.env.example` to `.env` and change `VITE_API_URL`.

**Automated check (React → FastAPI → store → engine).** Start a separate disposable backend with `CLOUD_SECURITY_STORE=memory uvicorn app.main:app --port 8001` from `backend/`, then:
```
cd frontend
VITE_API_URL=http://127.0.0.1:8001 npm run test:e2e
```
The tests reset only the disposable backend on port 8001 and run independently. They render the real dashboard against that API. It loads the demo data, exercises the filters, opens an incident, walks it to Resolved, and simulates a page refresh.


## Review 2: local AWS collector

Architecture: CloudTrail Event History → local AWS CLI collector → existing `POST /events` → engine → local SQLite store → dashboard.

The collector uses Python's standard library and the installed AWS CLI. It does not provision infrastructure, execute playbooks, save AWS log archives, or print credentials/raw AWS errors. Samples remain available through `/demo/load` and `python -m app.demo`.

### Offline verification (no AWS access)

From `backend/`, with the API running:

```bash
.venv/bin/python -m app.aws_collector --fixture tests/fixtures/cloudtrail_lookup.json
```

This fixture is synthetic, not evidence of live AWS integration. It contains one successful SSH change and one denied request. The first run creates one High incident and ignores the denied request; replay returns one duplicate. Use `--backend-url http://127.0.0.1:8001` to target a disposable test server.

### Live retrieval (only after the user's approval)

```bash
.venv/bin/python -m app.aws_collector --live --region ap-south-1 --minutes 30 --max-pages 2
```

Optional flags: `--profile NAME`, `--account-id EXPECTED_ACCOUNT`, and `--event-name NAME` (one of the six existing watched event names). Default event name: `AuthorizeSecurityGroupIngress`. Default AWS profile resolution is delegated to the CLI; authenticate through `aws login` if needed. Do not create access keys or commit credentials. The retrieval identity needs `cloudtrail:LookupEvents`; it does not need remediation permissions.

Each run freezes a recent time window, retrieves at most 50 records per page, decodes each `CloudTrailEvent`, and forwards individual records to the existing API. Pagination uses service `NextToken` with CLI automatic pagination disabled. Requests are spaced below two per second with bounded retry/backoff; no automatic ongoing polling. Limits: 1–1440 minutes and 1–20 pages. Exit code 2 means errors or truncation; a truncated run is incomplete. Increase the page cap within its limit or narrow the window. AWS Event History delivery is delayed, so rerun the overlapping window after the action appears in AWS; backend event-ID deduplication handles replay across restarts.

The JSON summary reports pages, fetched records, created incidents, duplicates, ignored records, failed records, and truncation. Invalid records are skipped and counted; persistent backend unavailability stops the batch. The backend URL must be a loopback HTTP origin. HTTP redirects and proxies are disabled for event posting.

[CloudTrail Event History](https://docs.aws.amazon.com/awscloudtrail/latest/userguide/view-cloudtrail-events.html) is regional management-event history, available for 90 days without a new trail or S3 bucket. It excludes S3 object data events. [AWS lookup documentation](https://docs.aws.amazon.com/cli/latest/reference/cloudtrail/lookup-events.html) describes its format and rate limit. For this milestone use EC2 management events in Mumbai; other services, including global IAM activity, may require a different lookup region.

### Local limitations

- Failed operations are excluded from successful-change detection; watched events must contain expected source and nonempty event ID, time, region, and account metadata.
- Existing request-based rules are heuristic: they do not verify current AWS resource state or execute remediation.
- The dashboard refreshes manually. Playbook checkboxes are browser-only progress.
- SQLite persists incidents and duplicate tracking across restarts; keep the database on local disk.
- `/demo/load?reset=true` remains an explicit destructive reset of the entire incident store. The dashboard uses non-destructive loading instead.
- Do not expose this unauthenticated API publicly. No AWS resources or remediation should be created/executed without separate approval.


## Local persistence

SQLite is included with Python; this adds no packages or AWS services. The store keeps the complete validated incident JSON, including event details, severity reasons, playbook, status, and history. Event IDs have a uniqueness constraint and writes use transactions, preventing duplicate incidents from concurrent requests. Normal ingestion and analyst status changes are saved immediately.

The default database path is anchored to `backend/data/incidents.sqlite3`, independent of the working directory. Override it with `CLOUD_SECURITY_DB_PATH=/absolute/path/incidents.sqlite3`. Choose `CLOUD_SECURITY_STORE=memory` for disposable sessions. Unsupported store modes fail explicitly.

Backend tests automatically use memory or temporary test databases; they never reset the default database. Frontend integration tests must use a separate backend on port 8001 with `CLOUD_SECURITY_STORE=memory`. Do not point destructive tests at your review database.

`POST /demo/load` preserves existing incidents. `POST /demo/load?reset=true` explicitly deletes **all** saved incidents, including real AWS incidents, and reloads the samples. The dashboard does not call this destructive reset.

The seven existing review incidents were migrated before switching the running backend to SQLite, retaining their original IDs and history. In future, switching from memory mode to SQLite does not automatically migrate in-memory incidents. For backups, stop the backend and copy the SQLite database to a private location; avoid committing incident data, which can contain account identifiers, actor names, and IP addresses. This is local persistence, not a hosted production database.


## Event origin and presentation

The normalized event includes `origin`: `demo`, `aws-cloudtrail`, `fixture`, or `submitted`. The dashboard shows readable labels and the original event ID. `/demo/load` labels samples as demo; the collector posts `?origin=aws-cloudtrail` in live mode and `?origin=fixture` in offline mode. Ordinary API submissions default to unverified; caller-provided body fields cannot silently change that default. Duplicate replay retains the first stored origin.

Origin is ingestion metadata, not cryptographic proof of authenticity: this local API is unauthenticated, and a caller can explicitly supply the supported query parameter. Verify real-event claims against AWS CloudTrail using the displayed event ID. The existing six sample incidents and the one AWS incident were labeled using their known event IDs; unknown records remain unverified. These labels persist in SQLite.

The dashboard warns that imported records describe past actions, not necessarily current exposure. Playbooks and status changes remain manual. Present the AWS component as a tested one-cloud MVP with manual bounded collection, not a continuously streaming, deployed multi-cloud service.
