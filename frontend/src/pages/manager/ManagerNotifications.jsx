import { useMemo, useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import PriorityPill from "../../components/common/PriorityPill";
import { apiUrl } from "../../config/apiBase";
import "./ManagerNotifications.css";

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

export default function ManagerNotifications() {
  const navigate = useNavigate();
  const [notifications, setNotifications] = useState([]);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All");
  const [onlyUnread, setOnlyUnread] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const token = localStorage.getItem("access_token");

  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(apiUrl("/manager/notifications"), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.status === 401) { navigate("/login"); return; }
      if (!res.ok) throw new Error("Failed to load notifications");
      const data = await res.json();
      setNotifications(data.notifications || []);
    } catch (e) {
      setError(e?.message || "Failed to load notifications.");
    } finally {
      setLoading(false);
    }
  }, [token, navigate]);

  useEffect(() => {
    if (!token) { navigate("/login"); return; }
    fetchNotifications();
  }, []);


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
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    try {
      await fetch(apiUrl("/manager/notifications/read-all"), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (e) {
      console.error("Failed to mark all notifications as read:", e);
    }
  };

  const onNotificationClick = async (n) => {
    setNotifications((prev) => prev.map((x) => (x.id === n.id ? { ...x, read: true } : x)));
    try {
      await fetch(apiUrl(`/manager/notifications/${n.id}/read`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (e) {
      console.error("Failed to mark notification as read:", e);
    }
    if (n.ticketId) navigate(`/manager/complaints/${n.ticketId}`);
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
            onChange={(v) => typeof v === "string" ? setQuery(v) : setQuery(v?.target?.value ?? "")}
            placeholder="Search notifications..."
          />
          <div className="empNotifs__filtersRow">
            <PillSelect
              value={filter}
              onChange={setFilter}
              ariaLabel="Filter notifications"
              options={[
                { value: "All",     label: "All" },
                { value: "Ticket",  label: "Ticket" },
                { value: "SLA",     label: "SLA" },
                { value: "Reports", label: "Reports" },
                { value: "System",  label: "System" },
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
                onClick={() => n.ticketId ? onNotificationClick(n) : null}
              >
                <div className="empNotifs__left">
                  <div className="empNotifs__icon">{iconForType(n.type)}</div>
                  <div className="empNotifs__content">
                    <div className="empNotifs__topRow">
                      <div className="empNotifs__title">{n.title}</div>
                      {n.priority && <PriorityPill priority={n.priority} />}
                    </div>
                    <div className="empNotifs__message">{n.message}</div>
                    <div className="empNotifs__meta">
                      <span>{formatTime(n.timestamp)}</span>
                      {n.ticketCode && <span>• {n.ticketCode}</span>}
                    </div>
                  </div>
                </div>
                <div className="empNotifs__right">
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