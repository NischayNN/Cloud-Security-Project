import { fmt, sevColor } from "../constants.js";

export default function IncidentList({ items, selectedId, onSelect }) {
  return (
    <div className="md:col-span-2 space-y-2">
      {items.length === 0 && (
        <div className="panel p-5 mute text-sm">No incidents match these filters. Clear a filter to see more.</div>
      )}
      {items.map((i) => (
        <button key={i.incident_id} data-testid="incident-item" onClick={() => onSelect(i.incident_id)}
                className="panel w-full text-left p-3 block"
                style={{ borderLeft: `6px solid ${sevColor(i.severity)}`, ...(selectedId === i.incident_id ? { background: "var(--sel)" } : {}) }}>
          <div className="flex justify-between gap-2">
            <span className="font-semibold text-sm" style={{ color: sevColor(i.severity) }}>{i.severity}</span>
            <span className="text-xs mute">{i.status}</span>
          </div>
          <div className="font-medium">{i.title}</div>
          <div className="text-xs mute mt-1">{i.incident_id} · {fmt(i.event.event_time)}</div>
        </button>
      ))}
    </div>
  );
}
