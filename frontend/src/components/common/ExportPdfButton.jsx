import "./ExportPdfButton.css";

export default function ExportPdfButton({
  loading = false,
  label = "Export PDF",
  as = "span", // "span" | "button"
  onClick,
  type = "button",
  className = "",
}) {
  const combinedClassName = `exportPdfBtn ${loading ? "isLoading" : ""} ${className}`.trim();

  if (as === "button") {
    return (
      <button
        className={combinedClassName}
        type={type}
        onClick={onClick}
        disabled={loading}
      >
        <span className="exportPdfIcon" aria-hidden="true">
          ⭳
        </span>
        {loading ? "Preparing PDF…" : label}
      </button>
    );
  }

  return (
    <span className={combinedClassName} aria-disabled={loading}>
      <span className="exportPdfIcon" aria-hidden="true">
        ⭳
      </span>
      {loading ? "Preparing PDF…" : label}
    </span>
  );
}
