import "./PriorityPill.css";

export default function PriorityPill({ priority }) {
  const p = (priority || "").toLowerCase();

  let variant = "medium";
  if (p === "critical") variant = "critical";
  else if (p === "high") variant = "high";
  else if (p === "low") variant = "low";

  return <span className={`priorityPill priorityPill--${variant}`}>{priority}</span>;
}
