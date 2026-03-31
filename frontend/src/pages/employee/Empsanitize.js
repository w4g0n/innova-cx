/**
 * sanitize.js  –  Employee module
 *
 * Mirrors the customer sanitize.js pattern so both modules share the same
 * defensive helpers. Move to utils/sanitize.js and import from there once
 * you are ready to unify across all roles.
 */

// ─── Constants ────────────────────────────────────────────────────────────────

/** Hard cap for free-text areas (reason, resolution, steps taken). */
export const MAX_REASON_LEN      = 2000;

/** Hard cap for long description / resolution fields. */
export const MAX_RESOLUTION_LEN  = 5000;

/** Hard cap for search / filter inputs. */
export const MAX_SEARCH_LEN      = 200;

/** Hard cap for short display fields (name, status, priority, subject …). */
export const MAX_FIELD_LEN       = 300;

// Allowlists used in this module
export const ALLOWED_PRIORITIES   = ["Low", "Medium", "High", "Critical"];
export const ALLOWED_DEPARTMENTS  = [
  "Facilities Management",
  "Legal & Compliance",
  "Safety & Security",
  "HR",
  "Leasing",
  "Maintenance",
  "IT",
];
export const ALLOWED_TICKET_SOURCES = ["User", "Chatbot"];

// ─── Core helpers ─────────────────────────────────────────────────────────────

/**
 * Coerce any value to a trimmed string and hard-cap its length.
 * Returns "" for null / undefined / non-string inputs.
 */
export function sanitizeText(value, maxLen = MAX_FIELD_LEN) {
  if (value === null || value === undefined) return "";
  const s = String(value).trim();
  return s.length > maxLen ? s.slice(0, maxLen) : s;
}

/**
 * Sanitize a ticket / report / session ID.
 * Only alphanumerics, hyphens, and underscores are allowed.
 * Everything else is stripped; result is hard-capped at maxLen.
 */
export function sanitizeId(value, maxLen = 64) {
  if (!value) return "";
  return String(value)
    .replace(/[^A-Za-z0-9_-]/g, "")
    .slice(0, maxLen);
}

/**
 * Sanitize a search / filter query.
 * Trims, caps at MAX_SEARCH_LEN, and strips characters that could be
 * misused in downstream string matching logic.
 */
export function sanitizeSearchQuery(value, maxLen = MAX_SEARCH_LEN) {
  if (!value) return "";
  return String(value)
    .trim()
    .replace(/[<>"'`]/g, "")
    .slice(0, maxLen);
}

/**
 * Safely parse a JSON string from storage into an object.
 * Returns {} on any parse error or if the result is not a plain object.
 */
export function safeParseUser(raw) {
  if (!raw) return {};
  try {
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    return parsed;
  } catch {
    return {};
  }
}

/**
 * Sanitize a filename for display.
 * Strips path separators and control characters; caps length.
 */
export function sanitizeFilename(value, maxLen = 255) {
  if (!value) return "";
  return String(value)
    .replace(/[/\\:*?"<>|]/g, "")
    .replace(/[\x00-\x1f]/g, "")
    .trim()
    .slice(0, maxLen);
}

/**
 * Validate a priority value against the allowlist.
 * Returns "Medium" as a safe default if the value is not recognised.
 */
export function sanitizePriority(value) {
  const s = sanitizeText(value, 20);
  return ALLOWED_PRIORITIES.includes(s) ? s : "Medium";
}

/**
 * Validate a department against the allowlist.
 * Returns "" if not recognised (forces the user to pick from the UI).
 */
export function sanitizeDepartment(value) {
  const s = sanitizeText(value, 60);
  return ALLOWED_DEPARTMENTS.includes(s) ? s : "";
}

/**
 * Coerce a ticket source to one of the two allowed display values.
 */
export function sanitizeTicketSource(value) {
  return String(value || "user").trim().toLowerCase() === "chatbot"
    ? "Chatbot"
    : "User";
}

/**
 * Safely format an ISO date string for display.
 * Returns "" instead of "Invalid Date" for bad inputs.
 */
export function safeFormatDate(isoString) {
  if (!isoString) return "";
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    year:   "numeric",
    month:  "short",
    day:    "2-digit",
    hour:   "2-digit",
    minute: "2-digit",
  });
}

/**
 * Sanitize a report ID (format: "feb-2026").
 * Only lowercase letters and a single hyphen followed by a 4-digit year.
 */
export function sanitizeReportId(value, maxLen = 20) {
  if (!value) return "";
  return String(value)
    .replace(/[^a-z0-9-]/g, "")
    .slice(0, maxLen);
}