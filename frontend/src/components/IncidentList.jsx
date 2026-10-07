import { fmt, sevColor, originLabel } from "../constants.js";
import Icon from './Icon.jsx';

export default function IncidentList({ items, selectedId, onSelect }) {
  return <div className="incident-list" aria-label="Incident list">
    {items.length === 0 && <div className="empty-list mute">No incidents match these filters. Clear a filter to see more.</div>}
    {items.map(i => <button key={i.incident_id} data-testid="incident-item" onClick={() => onSelect(i.incident_id)}
      aria-pressed={selectedId === i.incident_id} className={`incident-row ${selectedId === i.incident_id ? 'incident-selected' : ''}`}>
      <div className="incident-row-top"><span className="severity-badge" style={{ '--severity': sevColor(i.severity) }}>{i.severity}</span><span className="row-status">{i.status}</span></div>
      <div className="incident-row-title">{i.title}</div>
      <div className={`origin-tag ${i.event.origin === 'aws-cloudtrail' ? 'origin-aws' : ''}`}><Icon name={i.event.origin === 'aws-cloudtrail' ? 'cloud' : 'flask'} size={13}/>{originLabel(i.event.origin)}</div>
      <div className="incident-row-meta"><span>{i.incident_id}</span><span>{fmt(i.event.event_time)}</span></div>
    </button>)}
  </div>;
}
