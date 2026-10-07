import { SEVERITIES, sevColor } from "../constants.js";
import Icon from './Icon.jsx';

export default function Stats({ incidents, sevF, onSelect }) {
  return <section className="stats-grid" aria-label="Open incidents by severity">
    {SEVERITIES.map(s => {
      const n = incidents.filter(i => i.severity === s && i.status !== 'Resolved').length;
      return <button key={s} data-testid={`tile-${s}`} onClick={() => onSelect(s)} aria-pressed={sevF === s}
        className={`panel stat-card ${sevF === s ? 'stat-selected' : ''}`} style={{ '--severity': sevColor(s) }}>
        <div className="stat-label"><span className="stat-icon"><Icon name={s === 'Critical' || s === 'High' ? 'alert' : 'shield'} size={21}/></span><span>{s}<small>Priority level</small></span><Icon name="arrow" size={17}/></div>
        <div className="stat-value">{n.toString().padStart(2, '0')}</div>
        <div className="stat-caption">Open {s.toLowerCase()} incidents</div>
        <div className="stat-bottom"><span>View incidents</span><Icon name="arrow" size={15}/></div>
      </button>;
    })}
  </section>;
}
