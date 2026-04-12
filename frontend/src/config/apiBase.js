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

function isNativeApp() {
  if (typeof window === "undefined") return false;
  if (window.Capacitor?.isNativePlatform && typeof window.Capacitor.isNativePlatform === "function") {
    try {
      return window.Capacitor.isNativePlatform();
    } catch {
      return false;
    }
  }
  return window.location?.protocol === "capacitor:";
}

const configuredBase =
  import.meta.env.VITE_BACKEND_BASE_URL || import.meta.env.VITE_API_BASE_URL || "";

const mobileConfiguredBase =
  import.meta.env.VITE_MOBILE_BACKEND_BASE_URL || import.meta.env.VITE_CAPACITOR_BACKEND_BASE_URL || "";

export const API_BASE_URL = trimTrailingSlash(
  stripApiSuffix(
    ((isNativeApp() ? mobileConfiguredBase : configuredBase) || "").trim()
  ) || inferDefaultBaseUrl()
);

export function apiUrl(path = "") {
  const normalizedPath = String(path || "").replace(/^\/+/, "");
  return `${API_BASE_URL}/${normalizedPath}`;
}

