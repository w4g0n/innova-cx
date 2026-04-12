import "./KpiCard.css";

export default function KpiCard({ label, value, caption }) {
  return (
    <div className="kpiCard">
      <span className="kpiCard__glow" aria-hidden="true" />
      <span className="kpiCard__spark" aria-hidden="true" />
      <div className="kpiCard__inner">
        <div className="kpiCard__meta">
          <span className="kpiLabel">{label}</span>
          <span className="kpiCard__status" aria-hidden="true" />
        </div>
        <span className="kpiValue">{value}</span>
        {caption && <span className="kpiCaption">{caption}</span>}
      </div>
    </div>
  );
}
