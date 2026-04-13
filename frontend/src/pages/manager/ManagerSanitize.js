// Shared input-sanitization helpers for all Manager pages.
// Mirror of the employee-side utility, adapted to manager-specific constants.

export const MAX_SEARCH_LEN      = 200;   // PillSearch / search inputs
export const MAX_REASON_LEN      = 2000;  // reroute / rescore / escalate reason
export const MAX_RESOLUTION_LEN  = 5000;  // final resolution text
export const MAX_NAME_LEN        = 100;   // display names
export const MAX_EMAIL_LEN       = 254;   // RFC 5321

export const ALLOWED_PRIORITIES = ["Low", "Medium", "High", "Critical"];

// Status filters used across complaints list
export const ALLOWED_STATUS_FILTERS = [
  "All Status", "Hide Resolved", "Submitted", "Assigned",
  "Escalated", "Resolved", "Unassigned", "Overdue",
];

// Priority filters used across complaints list
export const ALLOWED_PRIORITY_FILTERS = [
  "All Priorities", "Critical", "High", "Medium", "Low",
];

// Notification filter tabs
export const ALLOWED_NOTIF_FILTERS = ["All", "Ticket", "SLA", "Reports", "System"];

// Approval sort keys
export const ALLOWED_SORT_KEYS = [
  "requestId", "ticketCode", "type", "current", "requested",
  "submittedBy", "submittedOn", "status", "subject",
  "confidencePct", "predictedDepartment", "createdAt",
  "ticket_code", "priority", "assignee", "issueDate",
  "respondTime", "resolveTime", "source",
];

/**
 * Trim and truncate a string. Strips leading/trailing whitespace.
 * Returns "" for non-string / nullish input.
 */
export function sanitizeText(value, maxLen = 1000) {
  if (value === null || value === undefined) return "";
  const str = String(value).trim();
  return str.slice(0, maxLen);
}

/**
 * Sanitize a ticket / review / request ID:
 * Allow only alphanumeric characters and hyphens. Max 50 chars.
 */
export function sanitizeId(value) {
  if (!value) return "";
  return String(value).replace(/[^a-zA-Z0-9_-]/g, "").slice(0, 50);
}

/**
 * Validate a priority value against the known allowlist.
 * Falls back to "Medium" if the value is not recognised.
 */
export function sanitizePriority(value) {
  const v = String(value || "").trim();
  return ALLOWED_PRIORITIES.includes(v) ? v : "Medium";
}

/**
 * Clamp a search query to MAX_SEARCH_LEN.
 */
export function sanitizeSearchQuery(value) {
  return sanitizeText(value, MAX_SEARCH_LEN);
}

/**
 * Sanitize a file name: strip path separators and control chars.
 */
export function sanitizeFilename(value, maxLen = 255) {
  if (!value) return "";

  return String(value)
    .replace(/[/\\:*?"<>|]/g, "")
    .split("")
    .filter((ch) => {
      const code = ch.charCodeAt(0);
      return code >= 32 && code !== 127;
    })
    .join("")
    .trim()
    .slice(0, maxLen);
}

/**
 * Safely parse the user object out of localStorage.
 * Returns {} on any failure.
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
 * Format an ISO date string for display. Returns "—" on failure.
 */
export function safeFormatDate(isoString, opts) {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    if (Number.isNaN(d.getTime())) return "—";
    return d.toLocaleString(undefined, opts);
  } catch {
    return "—";
  }
}