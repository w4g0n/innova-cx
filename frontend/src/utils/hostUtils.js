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