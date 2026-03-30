/**
 * sanitize.js
 * Shared sanitization helpers for all customer-facing modules.
 * Import what you need — all functions are pure and side-effect free.
 */

/**
 * Coerce any value to a safe, trimmed string.
 * Strips null bytes (\x00) which can confuse downstream parsers.
 * @param {*}      val    - any value
 * @param {number} maxLen - hard character cap (default 1000)
 * @returns {string}
 */
export function sanitizeText(val, maxLen = 1000) {
  if (val === null || val === undefined) return "";
  // eslint-disable-next-line no-control-regex
  return String(val).replace(/\x00/g, "").trim().slice(0, maxLen);
}

/**
 * Sanitize an ID-like value: keep only alphanumerics, hyphens, underscores.
 * Safe for use in URLs, CSS class suffixes, and aria labels.
 * @param {*}      val    - any value
 * @param {number} maxLen - default 64
 * @returns {string}
 */
export function sanitizeId(val, maxLen = 64) {
  return sanitizeText(val, maxLen).replace(/[^A-Za-z0-9_-]/g, "");
}

/**
 * Sanitize a filename: keep only printable ASCII (32–126), no path separators.
 * @param {*}      val    - any value
 * @param {number} maxLen - default 255
 * @returns {string}
 */
export function sanitizeFilename(val, maxLen = 255) {
  return sanitizeText(val, maxLen)
    // eslint-disable-next-line no-control-regex
    .replace(/[^\x20-\x7E]/g, "")
    .replace(/[/\\:*?"<>|]/g, "");
}

/**
 * Sanitize a free-text search query: trim + length cap.
 * @param {*}      val    - any value
 * @param {number} maxLen - default 200
 * @returns {string}
 */
export function sanitizeSearchQuery(val, maxLen = 200) {
  return sanitizeText(val, maxLen);
}

/**
 * Safely parse a JSON string from storage.
 * Returns `fallback` on any error instead of throwing.
 * Optionally validates the parsed value with a `validate` function.
 * @param {string|null} raw      - raw string from localStorage / sessionStorage
 * @param {*}           fallback - value to return on failure (default {})
 * @param {Function}    [validate] - optional (parsed) => boolean guard
 * @returns {*}
 */
export function safeParseJSON(raw, fallback = {}, validate) {
  if (!raw) return fallback;
  try {
    const parsed = JSON.parse(raw);
    if (validate && !validate(parsed)) return fallback;
    return parsed;
  } catch {
    return fallback;
  }
}

/**
 * Safely parse a user object from storage.
 * Ensures the result is a plain object (not an array / primitive).
 * @param {string|null} raw
 * @returns {{ id?: string, email?: string, role?: string, [key: string]: unknown }}
 */
export function safeParseUser(raw) {
  return safeParseJSON(raw, {}, (v) => v !== null && typeof v === "object" && !Array.isArray(v));
}

/**
 * Safely coerce a value into a Date, returning null if invalid.
 * Prevents `new Date(untrustedString)` from silently producing Invalid Date.
 * @param {*} val
 * @returns {Date|null}
 */
export function safeDate(val) {
  if (!val) return null;
  const d = new Date(val);
  return isNaN(d.getTime()) ? null : d;
}

/**
 * Format an ISO date string as a "time ago" label.
 * Falls back to empty string on bad input (no Invalid Date bleeding into UI).
 * @param {*} isoString
 * @returns {string}
 */
export function formatTimeAgo(isoString) {
  const d = safeDate(isoString);
  if (!d) return "";
  const diff = Math.floor((Date.now() - d.getTime()) / 1000);
  if (diff < 60)     return `${diff}s ago`;
  if (diff < 3600)   return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400)  return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return d.toLocaleDateString();
}

/** Maximum characters allowed in a ticket description / message body. */
export const MAX_DESCRIPTION_LEN = 5000;

/** Maximum characters allowed in a ticket subject / title. */
export const MAX_SUBJECT_LEN = 200;

/** Allowed values for the ticket type / form type selector. */
export const ALLOWED_TICKET_TYPES = ["complaint", "inquiry"];

/**
 * Validate and normalise a ticket type string.
 * Returns "complaint" if the value is not in the allowlist.
 * @param {*} val
 * @returns {"complaint"|"inquiry"}
 */
export function sanitizeTicketType(val) {
  const normalised = sanitizeText(val, 20).toLowerCase();
  return ALLOWED_TICKET_TYPES.includes(normalised) ? normalised : "complaint";
}