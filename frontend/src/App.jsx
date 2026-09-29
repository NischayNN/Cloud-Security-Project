import { useCallback, useEffect, useState } from "react";
import { getIncidents, getIncident, loadDemo, updateStatus } from "./api.js";
import Stats from "./components/Stats.jsx";
import IncidentFilters from "./components/IncidentFilters.jsx";
import IncidentList from "./components/IncidentList.jsx";
import IncidentDetail from "./components/IncidentDetail.jsx";

export default function App() {
  const [incidents, setIncidents] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [sevF, setSevF] = useState(null);
  const [stF, setStF] = useState("All");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [detailError, setDetailError] = useState(null);

  const refreshList = useCallback(async () => {
    try {
      setIncidents(await getIncidents());
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, []);

  const refreshDetail = useCallback(async (id) => {
    try {
      setDetail(await getIncident(id));
      setDetailError(null);
    } catch (e) {
      setDetailError(e.message);
    }
  }, []);

  useEffect(() => {
    refreshList();
  }, [refreshList]);

  useEffect(() => {
    if (!selectedId && incidents.length) {
      setSelectedId(incidents[0].incident_id);
    }
  }, [incidents, selectedId]);

  useEffect(() => {
    if (selectedId) {
      refreshDetail(selectedId);
    }
  }, [selectedId, refreshDetail]);

  async function handleAdvance(status) {
    setBusy(true);

    try {
      await updateStatus(selectedId, status);

      await Promise.all([
        refreshList(),
        refreshDetail(selectedId)
      ]);
    } catch (e) {
      setDetailError(e.message);
    } finally {
      setBusy(false);
    }
  }

  // Reset the demo data and reload all sample incidents
  async function handleResetDemo() {
    setBusy(true);

    try {
      await loadDemo(true);

      // Clear current selection/details
      setSelectedId(null);
      setDetail(null);
      setDetailError(null);

      // Reload the fresh demo incidents
      await refreshList();

      // Reset filters
      setSevF(null);
      setStF("All");

      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  const visible = incidents.filter(
    (i) =>
      (!sevF || i.severity === sevF) &&
      (stF === "All" || i.status === stF)
  );

  const current =
    detail && detail.incident_id === selectedId
      ? detail
      : null;

  return (
    <div className="max-w-6xl mx-auto p-4 md:p-6">

      <header className="flex flex-wrap items-end justify-between gap-2 mb-5">

        <div>
          <h1 className="text-2xl font-bold">
            Incident response console
          </h1>

          <p className="mute text-sm">
            AWS · live data from the FastAPI backend
          </p>
        </div>

        <div className="flex gap-2">

          {/* Refresh: only fetch current incidents */}
          <button
            onClick={refreshList}
            disabled={busy}
            className="px-3 py-1.5 rounded text-sm border line"
          >
            Refresh
          </button>

          {/* Reset Demo: clear old incidents and reload demo data */}
          <button
            onClick={handleResetDemo}
            disabled={busy}
            className="px-3 py-1.5 rounded text-sm font-semibold"
            style={{
              background: "var(--ink)",
              color: "var(--panel)"
            }}
          >
            Reset Demo
          </button>

        </div>
      </header>

      {error && (
        <div
          role="alert"
          className="panel p-3 mb-4 text-sm"
          style={{
            borderLeft: "6px solid var(--Critical)"
          }}
        >
          <b>Something went wrong.</b> {error}

          <div className="mute mt-1">
            Start the backend with{" "}
            <code className="px-1">
              uvicorn app.main:app --reload
            </code>{" "}
            from the backend folder, then press Refresh.
          </div>
        </div>
      )}

      {loading ? (
        <p className="mute">
          Loading incidents…
        </p>
      ) : incidents.length === 0 && !error ? (

        <div className="panel p-6 text-sm">

          <p className="font-semibold">
            No incidents yet.
          </p>

          <p className="mute mt-1">
            Load the sample AWS events to run them through the detection engine.
          </p>

        </div>

      ) : (

        <>
          <Stats
            incidents={incidents}
            sevF={sevF}
            onSelect={(s) =>
              setSevF(sevF === s ? null : s)
            }
          />

          <IncidentFilters
            incidents={incidents}
            stF={stF}
            onChange={setStF}
          />

          <div className="grid md:grid-cols-5 gap-4">

            <IncidentList
              items={visible}
              selectedId={selectedId}
              onSelect={setSelectedId}
            />

            <IncidentDetail
              incident={current}
              error={detailError}
              busy={busy}
              onAdvance={handleAdvance}
            />

          </div>
        </>
      )}

    </div>
  );
}