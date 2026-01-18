import "./FilterPillButton.css";

export default function FilterPillButton({ onClick, label = "Filters", type = "button" }) {
  return (
    <button className="filterPillBtn" type={type} onClick={onClick}>
      <span className="filterPillIcon" aria-hidden="true">
        <svg width="14" height="14" viewBox="0 0 24 24">
          <path d="M3 4h18l-7 8v6l-4 2v-8L3 4z" fill="currentColor" />
        </svg>
      </span>
      {label}
    </button>
  );
}
