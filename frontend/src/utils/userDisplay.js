export function getDisplayNameFromEmail(email, fallback = "there") {
  const value = (email || "").trim();
  if (!value.includes("@")) return fallback;
  const raw = value.split("@")[0];
  const cleaned = raw.replace(/[._-]+/g, " ").trim();
  if (!cleaned) return fallback;
  return cleaned
    .split(" ")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function getInitialsFromEmail(email, fallback = "U") {
  const value = (email || "").trim();
  if (!value.includes("@")) return fallback;
  const raw = value.split("@")[0] || "";
  const parts = raw.replace(/[._-]+/g, " ").trim().split(" ").filter(Boolean);
  if (parts.length === 0) return fallback;
  if (parts.length === 1) return (parts[0][0] || fallback).toUpperCase();
  return `${(parts[0][0] || fallback).toUpperCase()}${(parts[1][0] || "").toUpperCase()}`;
}
