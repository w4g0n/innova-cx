function trimTrailingSlash(value) {
  return String(value || "").replace(/\/+$/, "");
}

function stripApiSuffix(value) {
  return value.replace(/\/api\/?$/i, "");
}

function inferDefaultBaseUrl() {
  if (typeof window !== "undefined" && window.location?.hostname) {
    const protocol = window.location.protocol === "https:" ? "https" : "http";
    return `${protocol}://${window.location.hostname}:8000`;
  }
  return "http://localhost:8000";
}

const configuredBase =
  import.meta.env.VITE_BACKEND_BASE_URL || import.meta.env.VITE_API_BASE_URL || "";

export const API_BASE_URL = trimTrailingSlash(
  stripApiSuffix(configuredBase.trim()) || inferDefaultBaseUrl()
);

export function apiUrl(path = "") {
  const normalizedPath = String(path || "").replace(/^\/+/, "");
  return `${API_BASE_URL}/${normalizedPath}`;
}

