import { useMemo, useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import { apiUrl } from "../../config/apiBase";
import { fireNotifRefresh } from "../../utils/notifRefresh";
import {
  sanitizeText,
  sanitizeId,
  sanitizeSearchQuery,
  ALLOWED_NOTIF_FILTERS,
  MAX_SEARCH_LEN,
} from "./ManagerSanitize";
import "./ManagerNotifications.css";

function getAuthToken() {
  return (
    localStorage.getItem("access_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("jwt") ||
    localStorage.getItem("authToken") ||
    ""
  );
}

function formatTime(isoString) {
  if (!isoString) return "";
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "2-digit",
    hour: "2-digit", minute: "2-digit",
  });
}

function iconForType(type) {
  switch (type) {
    case "ticket_assignment": return "📌";
    case "sla_warning":       return "⏰";
    case "customer_reply":    return "💬";
    case "status_change":     return "🔄";
    case "report_ready":      return "📊";
    case "system":            return "🛠️";
    default:                  return "🔔";
  }
}

const API_BASE = apiUrl("/api");

export default function ManagerNotifications() {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All");
  const [onlyUnread, setOnlyUnread] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchNotifications = useCallback(async () => {
    const token = getAuthToken();
    if (!token) {
      navigate("/login");
      return;
    }

    setLoading(true);
    setError("");
    try {
      const res = await fetch(`${API_BASE}/manager/notifications`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { navigate("/login"); return; }
      if (!res.ok) throw new Error("Failed to load notifications.");
      const data = await res.json();
      const normalized = (data.notifications || []).map((n) => {
        const typeMap = {
          approval: "ticket_assignment",
          escalation: "status_change",
          sla_breach: "sla_warning",
        };
        const rawTitle = sanitizeText(n.title, 200);
        const codeMatch = rawTitle.match(/([A-Z]{2,}-\d+)/);
        const rawTicketId = n.ticketId || (codeMatch ? codeMatch[1] : null);
        return {
          ...n,
          type: typeMap[n.type] || n.type,
          title: rawTitle,
          message: sanitizeText(n.message || n.body || "", 500),
          ticketId: sanitizeId(rawTicketId),
        };
      });
      setNotifications(normalized);
    } catch {
      setError("Failed to load notifications. Please try again.");
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    fetchNotifications();
  }, [fetchNotifications]);

  const unreadCount = useMemo(() => notifications.filter((n) => !n.read).length, [notifications]);

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    return notifications
      .filter((n) => {
        if (onlyUnread && n.read) return false;
        const matchesType =
          filter === "All" ||
          (filter === "Ticket" && ["ticket_assignment", "status_change", "customer_reply"].includes(n.type)) ||
          (filter === "SLA" && n.type === "sla_warning") ||
          (filter === "Reports" && n.type === "report_ready") ||
          (filter === "System" && n.type === "system");
        const blob = `${n.title} ${n.message} ${n.ticketId ?? ""} ${n.reportId ?? ""}`.toLowerCase();
        return matchesType && (!q || blob.includes(q));
      })
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  }, [notifications, query, filter, onlyUnread]);

  const markAllRead = async () => {
    const token = getAuthToken();
    if (!token) return;
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    try {
      await fetch(`${API_BASE}/manager/notifications/read-all`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (e) {
      console.error("Failed to mark all notifications as read:", e);
      return;
    }
    fireNotifRefresh();
  };

  const dismissOne = async (e, n) => {
    e.stopPropagation();
    setNotifications((prev) => prev.filter((x) => x.id !== n.id));
    if (!n.read) {
      const token = getAuthToken();
      try {
        await fetch(`${API_BASE}/manager/notifications/${n.id}/read`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
        fireNotifRefresh();
      } catch { /* non-critical */ }
    }
  };

  const onNotificationClick = async (n) => {
    const token = getAuthToken();

    // Always mark as read, regardless of whether there's a ticketId
    if (!n.read) {
      setNotifications((prev) =>
        prev.map((x) => (x.id === n.id ? { ...x, read: true } : x))
      );
      try {
        await fetch(`${API_BASE}/manager/notifications/${n.id}/read`, {
          method: "POST",
          headers: { Authorization: `Bearer ${token}` },
        });
        fireNotifRefresh();
      } catch { /* silently ignore */ }
    }

    // Navigate AFTER state update and API call
    if (n.ticketId) navigate(`/manager/complaints/${encodeURIComponent(n.ticketId)}`);
  };

  return (
    <Layout role="manager">
      <div className="empNotifs">
        <PageHeader
          title="Notifications"
          subtitle={`You have ${unreadCount} unread notification${unreadCount === 1 ? "" : "s"}.`}
          actions={
            <button
              className="filterPillBtn empNotifs__actionBtn"
              onClick={markAllRead}
              disabled={loading || notifications.length === 0}
            >
              Mark all as read
            </button>
          }
        />

        <div className="empNotifs__controls">
          <PillSearch
            value={query}
            onChange={(v) => {
              const raw = typeof v === "string" ? v : (v?.target?.value ?? "");
              setQuery(sanitizeSearchQuery(raw));
            }}
            placeholder="Search notifications..."
            maxLength={MAX_SEARCH_LEN}
          />
          <div className="empNotifs__filtersRow">
            <PillSelect
              value={filter}
              ariaLabel="Filter notifications"
              options={[
                { value: "All",     label: "All" },
                { value: "Ticket",  label: "Ticket" },
                { value: "SLA",     label: "SLA" },
                { value: "Reports", label: "Reports" },
                { value: "System",  label: "System" },
              ]}
              onChange={(v) => {
                if (ALLOWED_NOTIF_FILTERS.includes(v)) setFilter(v);
              }}
            />
            <button
              className="filterPillBtn empNotifs__actionBtn"
              onClick={() => setOnlyUnread((s) => !s)}
              disabled={loading}
            >
              {onlyUnread ? "Showing Unread" : "Show Unread"}
            </button>
          </div>
        </div>

        {error && <div className="empNotifs__empty">{error}</div>}

        <div className="empNotifs__list">
          {loading ? (
            <div className="empNotifs__empty">Loading...</div>
          ) : filtered.length === 0 ? (
            <div className="empNotifs__empty">No notifications found.</div>
          ) : (
            filtered.map((n) => (
              <div
                key={n.id}
                className={`empNotifs__item ${n.read ? "read" : "unread"} ${n.ticketId ? "clickable" : ""}`}
                onClick={() => onNotificationClick(n)} 
              >
                <div className="empNotifs__left">
                  <div className="empNotifs__icon">{iconForType(n.type)}</div>
                  <div className="empNotifs__content">
                    <div className="empNotifs__topRow">
                      <div className="empNotifs__title">{n.title}</div>
                    </div>
                    <div className="empNotifs__message">{n.message}</div>
                    <div className="empNotifs__meta">
                      <span>{formatTime(n.timestamp)}</span>
                      {(n.ticketCode || n.ticketId) && <span>• {n.ticketCode || n.ticketId}</span>}
                    </div>
                  </div>
                </div>
                <div className="empNotifs__right">
                  <button
                    type="button"
                    className="empNotifs__dismiss"
                    onClick={(e) => dismissOne(e, n)}
                    aria-label="Dismiss notification"
                  >
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                      <path d="M18 6 6 18M6 6l12 12" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/>
                    </svg>
                  </button>
                  {!n.read && <span className="empNotifs__dot" />}
                  {n.ticketId && <span className="empNotifs__chev">›</span>}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </Layout>
  );
}