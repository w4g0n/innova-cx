// src/utils/hostUtils.js
// Returns: null = local dev (no enforcement), true = staff subdomain, false = customer domain
export function isStaffHost() {
  const host = window.location.hostname;
  if (
    host === "localhost" ||
    host === "127.0.0.1" ||
    host.startsWith("192.168.")
  )
    return null;
  return host.startsWith("staff.");
}