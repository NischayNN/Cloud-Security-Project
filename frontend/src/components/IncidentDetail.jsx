import { STATUSES, fmt, sevColor } from "../constants.js";
import Playbook from "./Playbook.jsx";
import History from "./History.jsx";

export default function IncidentDetail({ incident: i, error, busy, onAdvance }) {
  if (!i) {
    return (
      <div className="md:col-span-3 panel p-5">
        {error ? <p role="alert" className="text-sm">{error}</p> : <p className="mute">Loading incident…</p>}
      </div>
    );
  }
  const k = STATUSES.indexOf(i.status);
  const next = STATUSES[k + 1];
  const e = i.event;
  const facts = [
    ["Cloud", i.provider.toUpperCase()], ["Actor", i.actor], ["Resource", `${i.resource_type} · ${i.resource_id}`],
    ["Time", fmt(e.event_time)], ["Event", e.event_name], ["Source IP", e.source_ip || "unknown"],
    ["Account", e.account_id], ["Region", e.region],
  ];
  return (
    <div className="md:col-span-3 panel p-5">
      {error && <p role="alert" className="text-sm mb-3 p-2 rounded" style={{ borderLeft: "4px solid var(--Critical)" }}>{error}</p>}
      <div className="flex flex-wrap items-center gap-2 mb-1">
        <span className="text-sm font-bold px-2 py-0.5 rounded text-white" style={{ background: sevColor(i.severity) }}>{i.severity}</span>
        <span className="text-xs mute">{i.incident_id} · {i.type.replaceAll("_", " ")}</span>
      </div>
      <h2 className="text-xl font-bold">{i.title}</h2>
      <p className="text-sm mt-1">{i.description}</p>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm mt-4">
        {facts.map(([label, value]) => (
          <div key={label} className="min-w-0"><dt className="text-xs mute">{label}</dt><dd className="break-words">{value}</dd></div>
        ))}
      </dl>
      <pre className="p-2 mt-3 overflow-x-auto" aria-label="Event details">{JSON.stringify(e.details, null, 2)}</pre>

      <h3 className="font-semibold mt-5 mb-2">Status</h3>
      <div className="flex items-center gap-2 flex-wrap">
        {STATUSES.map((s, n) => (
          <span key={s} className={`text-sm px-2 py-1 rounded border line ${n <= k ? "font-semibold" : "mute"}`}
                style={n === k ? { background: "var(--sel)" } : {}}>{n < k ? "✓ " : ""}{s}</span>
        ))}
        {next && (
          <button disabled={busy} onClick={() => onAdvance(next)} className="ml-auto px-3 py-1.5 rounded text-sm font-semibold"
                  style={{ background: "var(--ink)", color: "var(--panel)" }}>{busy ? "Saving…" : `Mark as ${next}`}</button>
        )}
      </div>

      <h3 className="font-semibold mt-5 mb-1">Why {i.severity.toLowerCase()} (score {i.severity_score})</h3>
      <ul className="text-sm list-disc pl-5">{i.severity_reasons.map((r) => <li key={r}>{r}</li>)}</ul>

      <Playbook key={i.incident_id} steps={i.playbook} resource={i.resource_id} />
      <History history={i.history} />
    </div>
  );
}
