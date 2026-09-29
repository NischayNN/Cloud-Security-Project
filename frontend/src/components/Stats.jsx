import { SEVERITIES, sevColor } from "../constants.js";

export default function Stats({ incidents, sevF, onSelect }) {
  return (
    <section className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
      {SEVERITIES.map((s) => {
        const n = incidents.filter((i) => i.severity === s && i.status !== "Resolved").length;
        return (
          <button key={s} data-testid={`tile-${s}`} onClick={() => onSelect(s)}
                  className={`panel p-3 text-left ${sevF === s ? "ring-2" : ""}`}
                  style={{ borderLeft: `6px solid ${sevColor(s)}`, ...(sevF === s ? { "--tw-ring-color": sevColor(s) } : {}) }}>
            <div className="text-3xl font-bold">{n}</div>
            <div className="text-sm mute">Open {s.toLowerCase()}</div>
          </button>
        );
      })}
    </section>
  );
}
