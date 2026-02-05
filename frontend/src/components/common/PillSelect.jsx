import "./PillSelect.css";

export default function PillSelect({
  value,
  onChange,
  options = [],
  ariaLabel = "Select option",
  className = "",
  minWidth = 200,
}) {
  return (
    <div className={`pillSelect ${className}`}>
      <select
        className="pillSelect__select"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={ariaLabel}
        style={{ minWidth }}
      >
        {options.map((opt) => {
          const v = typeof opt === "string" ? opt : opt.value;
          const label = typeof opt === "string" ? opt : opt.label;
          return (
            <option key={v} value={v}>
              {label}
            </option>
          );
        })}
      </select>
    </div>
  );
}