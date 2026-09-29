// All calls to the FastAPI backend live here.
const BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(BASE + path, {
      ...options,
      headers: options.body ? { "Content-Type": "application/json" } : undefined,
    });
  } catch {
    throw new Error(`Cannot reach the API at ${BASE}. Is the backend running?`);
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") msg = body.detail;
    } catch { /* keep default message */ }
    throw new Error(msg);
  }
  return res.json();
}

export const getIncidents = () => request("/incidents");
export const getIncident = (id) => request(`/incidents/${id}`);
export const postEvent = (rawEvent) => request("/events", { method: "POST", body: JSON.stringify(rawEvent) });
export const loadDemo = (reset = false) => request(`/demo/load?reset=${reset}`, { method: "POST" });
export const updateStatus = (id, status, note = "") =>
  request(`/incidents/${id}/status`, { method: "PATCH", body: JSON.stringify({ status, note }) });
