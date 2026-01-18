import "./PillSearch.css";

export default function PillSearch({
  value,
  onChange,
  placeholder = "Search...",
  ariaLabel = "Search",
  className = "",
}) {
  return (
    <div className={`pillSearch ${className}`}>
      <span className="pillSearch__icon">🔍</span>
      <input
        type="text"
        className="pillSearch__input"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={ariaLabel}
      />
    </div>
  );
}
