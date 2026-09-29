import { STATUSES } from "../constants.js";

export default function IncidentFilters({ incidents, stF, onChange }) {
  return (
    <div className="flex flex-wrap gap-2 mb-4">
      {["All", ...STATUSES].map((s) => (
        <button key={s} onClick={() => onChange(s)}
                className={`px-3 py-1 rounded-full text-sm border line ${stF === s ? "font-semibold" : "mute"}`}
                style={stF === s ? { background: "var(--sel)" } : {}}>
          {s}{s === "All" ? "" : ` (${incidents.filter((i) => i.status === s).length})`}
        </button>
      ))}
    </div>
  );
}
