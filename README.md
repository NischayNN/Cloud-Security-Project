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

Incidents are stored in memory, so they disappear when the server restarts. Call `POST /demo/load` again to refill.

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

1. Click **Load demo incidents** to run the 7 sample AWS events through the engine (6 incidents appear).
2. Click a severity card or a status chip to filter. Click an incident to open its details and playbook.
3. Use the **Mark as …** button to move it Detected → Investigating → Contained → Resolved. Each change is saved by the backend, so a page refresh keeps it.

If the backend is not at `http://127.0.0.1:8000`, copy `.env.example` to `.env` and change `VITE_API_URL`.

**Automated check (React → FastAPI → store → engine).** Start the backend on a fresh store (restart it), then:
```
cd frontend
npm run test:e2e
```
The test renders the real dashboard against the running API. It loads the demo data, exercises the filters, opens an incident, walks it to Resolved, and simulates a page refresh.
