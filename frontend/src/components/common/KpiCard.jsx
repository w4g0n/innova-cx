import "./KpiCard.css";

export default function KpiCard({ label, value, caption }) {
  return (
    <div className="kpiCard">
      <span className="kpiLabel">{label}</span>
      <span className="kpiValue">{value}</span>
      {caption && <span className="kpiCaption">{caption}</span>}
    </div>
  );
}