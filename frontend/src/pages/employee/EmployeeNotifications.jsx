import { useMemo, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import { apiUrl } from "../../config/apiBase";
import { getCsrfToken } from "../../services/api";
import {
  sanitizeText,
  sanitizeId,
  sanitizeReportId,
  safeFormatDate,
  MAX_SEARCH_LEN,
} from "./EmployeeSanitize";
import "./EmployeeNotifications.css";

// safeFormatDate already validates the date — re-export under local alias for clarity
const formatTime = safeFormatDate;

function iconForType(type) {
  switch (type) {
    case "ticket_assignment": return "📌";
    case "sla_warning":       return "⏰";
    case "customer_reply":    return "💬";
    case "status_change":     return "🔄";
    case "report_ready":      return "📊";
    case "recurrence_reminder": return "🔁";
    case "system":            return "🛠️";
    default:                  return "🔔";
  }
}

function getAuthToken() {
  return (
    localStorage.getItem("access_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("jwt") ||
    localStorage.getItem("authToken") ||
    ""
  );
}

const API_BASE = apiUrl("/api");

// Allowed notification type filter values — never trust user-controlled strings directly
const ALLOWED_FILTERS = ["All", "Ticket", "SLA", "Reports", "System"];

export default function EmployeeNotifications() {
  const navigate = useNavigate();

  const [notifications, setNotifications] = useState([]);
  const [query,         setQuery]         = useState("");
  const [filter,        setFilter]        = useState("All");
  const [onlyUnread,    setOnlyUnread]    = useState(false);
  const [loading,       setLoading]       = useState(false);
  // Fixed internal error string — raw e.message from the network is never rendered
  const [error,         setError]         = useState("");

  useEffect(() => {
    fetchNotifications();
  }, []);

  async function fetchNotifications() {
    const token = getAuthToken();
    if (!token) return;

    setLoading(true);
    setError("");

    try {
      const res = await fetch(`${API_BASE}/employee/notifications`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        // Never render raw server response text — use a fixed internal message
        throw new Error("server_error");
      }

      const data = await res.json();
      setNotifications(data.notifications || []);
    } catch {
      // Fixed string — raw error.message is never surfaced to the DOM
      setError("Failed to load notifications. Please try again.");
      setNotifications([]);
    } finally {
      setLoading(false);
    }
  }

  const filtered = useMemo(() => {
    // sanitizeSearchQuery already applied at onChange; cap again here as defence-in-depth
    const q = sanitizeText(query, MAX_SEARCH_LEN).toLowerCase();

    // Validate filter against allowlist — ignore unknown values
    const safeFilter = ALLOWED_FILTERS.includes(filter) ? filter : "All";

    return notifications
      .filter((n) => {
        if (onlyUnread && n.read) return false;

        const matchesType =
          safeFilter === "All" ||
          (safeFilter === "Ticket" &&
            ["ticket_assignment", "status_change", "customer_reply"].includes(n.type)) ||
          (safeFilter === "SLA"     && n.type === "sla_warning")  ||
          (safeFilter === "Reports" && n.type === "report_ready") ||
          (safeFilter === "System"  && n.type === "system");

        // Sanitize all server-supplied fields before using them in filter logic
        const blob = [
          sanitizeText(n.title,    100),
          sanitizeText(n.message,  300),
          sanitizeId(n.ticketId,    48),
          sanitizeReportId(n.reportId, 20),
        ].join(" ").toLowerCase();

        return matchesType && (!q || blob.includes(q));
      })
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  }, [notifications, query, filter, onlyUnread]);

  const markAllRead = async () => {
    const token = getAuthToken();
    if (!token) return;

    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));

    try {
      const csrf = await getCsrfToken();
      await fetch(`${API_BASE}/employee/notifications/read-all`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
      });
    } catch {
      // Network error — silently ignore, optimistic UI update stays
    }
  };

  const markOneRead = async (id) => {
    const token = getAuthToken();
    if (!token) return;

    try {
      const csrf = await getCsrfToken();
      // sanitizeId ensures the ID only contains safe chars before it enters the URL
      await fetch(`${API_BASE}/employee/notifications/${encodeURIComponent(sanitizeId(id, 64))}/read`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
      });
    } catch {
      // Network error — silently ignore
    }
  };

  const dismissOne = async (e, id) => {
    e.stopPropagation(); // don't trigger the card's onClick
    setNotifications((prev) => prev.filter((n) => n.id !== id));
    await markOneRead(id);
  };

  const onNotificationClick = async (n) => {
    setNotifications((prev) =>
      prev.map((x) => (x.id === n.id ? { ...x, read: true } : x))
    );

    await markOneRead(n.id);

    if (n.ticketId) {
      // sanitizeId prevents path-traversal or injection in the navigation URL
      const safeTicketId = sanitizeId(n.ticketId, 48);
      if (safeTicketId) navigate(`/employee/details/${safeTicketId}`);
    } else if (n.reportId) {
      // sanitizeReportId strips chars outside [a-z0-9-]
      const safeReportId = sanitizeReportId(n.reportId, 20);
      if (safeReportId)
        navigate(`/employee/reports?report=${encodeURIComponent(safeReportId)}`);
    }
  };

  return (
    <Layout role="employee">
      <div className="empNotifs">
        <div className="empNotifs__hero">
          <h1 className="empNotifs__heroTitle">Notifications</h1>
        </div>

        <div className="empNotifs__controls">
          <PillSearch
            value={query}
            onChange={(v) => {
              // Cap search input length client-side before it enters state
              const raw = typeof v === "string" ? v : (v?.target?.value ?? "");
              if (raw.length <= MAX_SEARCH_LEN) setQuery(raw);
            }}
            placeholder="Search notifications..."
            maxLength={MAX_SEARCH_LEN}
          />

          <div className="empNotifs__filtersRow">
            <div className="empNotifs__filtersLeft">
              <PillSelect
                value={filter}
                onChange={(v) => {
                  // Only allow values from our allowlist
                  if (ALLOWED_FILTERS.includes(v)) setFilter(v);
                }}
                ariaLabel="Filter notifications"
                options={[
                  { value: "All",     label: "All"     },
                  { value: "Ticket",  label: "Ticket"  },
                  { value: "SLA",     label: "SLA"     },
                  { value: "Reports", label: "Reports" },
                  { value: "System",  label: "System"  },
                ]}
              />

              <button
                className="filterPillBtn empNotifs__actionBtn"
                onClick={() => setOnlyUnread((s) => !s)}
                disabled={loading}
              >
                {onlyUnread ? "Showing Unread" : "Show Unread"}
              </button>
            </div>

            <div className="empNotifs__filtersRight">
              <button
                className="filterPillBtn empNotifs__actionBtn"
                onClick={markAllRead}
                disabled={loading || notifications.length === 0}
              >
                Mark all as read
              </button>
            </div>
          </div>
        </div>

        {/* error is a fixed internal string — never raw network error text */}
        {error && <div className="empNotifs__empty">{error}</div>}

        <div className="empNotifs__list">
          {loading ? (
            <div className="empNotifs__empty">Loading...</div>
          ) : filtered.length === 0 ? (
            <div className="empNotifs__empty">No notifications found.</div>
          ) : (
            filtered.map((n) => {
              // Sanitize all server-supplied fields before rendering
              const safeTitle    = sanitizeText(n.title    || "Notification", 100);
              const safeMessage  = sanitizeText(n.message  || "",             300);
              const safeTicketId = sanitizeId(n.ticketId,   48);
              const safeReportId = sanitizeReportId(n.reportId, 20);
              const safeTime     = formatTime(n.timestamp);

              return (
                <div
                  key={n.id}
                  className={`empNotifs__item ${n.read ? "read" : "unread"} ${
                    safeTicketId || safeReportId ? "clickable" : ""
                  }`}
                  onClick={() =>
                    safeTicketId || safeReportId ? onNotificationClick(n) : null
                  }
                >
                  <div className="empNotifs__left">
                    {/* iconForType uses the raw n.type only for an emoji lookup — safe */}
                    <div className="empNotifs__icon">{iconForType(n.type)}</div>

                    <div className="empNotifs__content">
                      <div className="empNotifs__topRow">
                        <div className="empNotifs__title">{safeTitle}</div>
                      </div>

                      <div className="empNotifs__message">{safeMessage}</div>

                      <div className="empNotifs__meta">
                        <span>{safeTime}</span>
                        {safeTicketId && <span>• {safeTicketId}</span>}
                        {safeReportId && <span>• {safeReportId}</span>}
                      </div>
                    </div>
                  </div>

                  <div className="empNotifs__right">
                    <button
                      type="button"
                      className="empNotifs__dismiss"
                      onClick={(e) => dismissOne(e, n.id)}
                      aria-label="Dismiss notification"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                        <path d="M18 6 6 18M6 6l12 12" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/>
                      </svg>
                    </button>
                    {!n.read && <span className="empNotifs__dot" />}
                    {(safeTicketId || safeReportId) && (
                      <span className="empNotifs__chev">›</span>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </Layout>
  );
}
