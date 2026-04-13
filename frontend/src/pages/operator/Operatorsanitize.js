// Shared input-sanitization helpers for all Operator pages.
// Follows the same pattern as customer/sanitize.js and employee/EmployeeSanitize.js.

export const MAX_SEARCH_LEN     = 200;   // PillSearch / search inputs
export const MAX_NOTE_LEN       = 2000;  // Analyst note textarea (TicketReviewDetail)
export const MAX_NAME_LEN       = 100;   // Full names
export const MAX_EMAIL_LEN      = 254;   // RFC 5321
export const MAX_LOCATION_LEN   = 200;   // Location field
export const MAX_TEXT_LEN       = 1000;  // Generic short text

export const ALLOWED_ROLES = ["customer", "employee", "manager", "operator"];

export const ALLOWED_STATUSES = ["all", "active", "inactive"];

export const ALLOWED_ROLE_FILTERS = ["all", "customer", "employee", "manager", "operator"];

export const ALLOWED_NOTIF_FILTERS = ["All", "Users", "Model", "Escalation", "Reports", "System"];

export const ALLOWED_TIME_FILTERS = ["last7days", "last30days", "quarter"];

export const ALLOWED_DEPARTMENTS = [
  "All Departments",
  "Facilities Management",
  "Legal & Compliance",
  "Safety & Security",
  "HR",
  "Leasing",
  "Maintenance",
  "IT",
];

export const ALLOWED_QC_SECTIONS = ["acceptance", "rescoring", "learning"];

export const ALLOWED_MODEL_AGENTS = ["chatbot", "sentiment", "feature"];

/**
 * Allowlist for general text fields.
 * Keeps Unicode letters, digits, whitespace, and common punctuation. Strips everything else.
 */
const _ALLOWED_TEXT_RE = /[^\p{L}\p{N}\s\-.,!?'"+()\u005B\u005D@/:;#%&*\n]/gu;

/**
 * Trim, apply allowlist, and truncate a string to maxLen. Returns "" for nullish input.
 */
export function sanitizeText(value, maxLen = MAX_TEXT_LEN) {
  if (value === null || value === undefined) return "";
  return String(value).replace(_ALLOWED_TEXT_RE, "").trim().slice(0, maxLen);
}

/**
 * Sanitize a ticket/user/request ID: alphanumeric + hyphens only, max 50 chars.
 */
export function sanitizeId(value) {
  if (!value) return "";
  return String(value)
    .replace(/[^a-zA-Z0-9-]/g, "")
    .slice(0, 50);
}

/**
 * Clamp a search/query string to MAX_SEARCH_LEN.
 */
export function sanitizeSearchQuery(value) {
  return sanitizeText(value, MAX_SEARCH_LEN);
}

/**
 * Validate a role value against the known allowlist. Falls back to "customer".
 */
export function sanitizeRole(value) {
  const v = String(value || "").trim().toLowerCase();
  return ALLOWED_ROLES.includes(v) ? v : "customer";
}

/**
 * Sanitize a filename: strip path separators and control chars.
 */
export function sanitizeFilename(name) {
  if (!name) return "file";
  return (
    String(name)
      .replace(/[/\\<>:"|?*]/g, "_")
      .slice(0, 200) || "file"
  );
}
/**
 * Safely parse the user object from localStorage. Returns {} on failure.
 */
export function safeParseUser() {
  try {
    const raw = localStorage.getItem("user");
    if (!raw) return {};
    return JSON.parse(raw) || {};
  } catch {
    return {};
  }
}

/**
 * Format an ISO date string. Returns "—" on failure.
 */
const DUBAI_TZ = "Asia/Dubai";

export function safeFormatDate(isoString, opts) {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleString("en-GB", { timeZone: DUBAI_TZ, ...opts });
  } catch {
    return "—";
  }
}
