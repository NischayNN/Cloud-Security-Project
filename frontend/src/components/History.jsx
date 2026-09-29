import { fmt } from "../constants.js";

export default function History({ history }) {
  return (
    <>
      <h3 className="font-semibold mt-5 mb-2">History</h3>
      <ol className="text-sm space-y-1 border-l line pl-4">
        {[...history].reverse().map((h, n) => (
          <li key={n}><b>{h.status}</b> <span className="mute">· {fmt(h.timestamp)} · {h.note}</span></li>
        ))}
      </ol>
    </>
  );
}
