import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import PriorityPill from "../../components/common/PriorityPill";
import "./EmployeeNotifications.css";

function formatTime(isoString) {
  if (!isoString) return "";
  const d = new Date(isoString);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function iconForType(type) {
  switch (type) {
    case "ticket_assignment":
      return "📌";
    case "sla_warning":
      return "⏰";
    case "customer_reply":
      return "💬";
    case "status_change":
      return "🔄";
    case "report_ready":
      return "📊";
    case "system":
      return "🛠️";
    default:
      return "🔔";
  }
}

// Token may be stored under one of these keys
function getAuthToken() {
  return (
    localStorage.getItem("access_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("jwt") ||
    localStorage.getItem("authToken") ||
    ""
  );
}

const API_BASE = "http://localhost:8000/api";

export default function EmployeeNotifications() {
  const navigate = useNavigate();

  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);

  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All");
  const [onlyUnread, setOnlyUnread] = useState(false);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function fetchNotifications({ unreadOnly }) {
    const token = getAuthToken();
    if (!token) {
      setError("Missing auth token. Please log in again.");
      return;
    }

    setLoading(true);
    setError("");

    try {
      const url = new URL(`${API_BASE}/employee/notifications`);
      url.searchParams.set("limit", "500");
      url.searchParams.set("only_unread", unreadOnly ? "true" : "false");

      const res = await fetch(url.toString(), {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        const msg = await res.text();
        throw new Error(msg || `Failed to load notifications (${res.status})`);
      }

      const data = await res.json();
      setUnreadCount(Number(data?.unreadCount || 0));
      setNotifications(Array.isArray(data?.notifications) ? data.notifications : []);
    } catch (e) {
      setError(e?.message || "Failed to load notifications.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchNotifications({ unreadOnly: onlyUnread });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [onlyUnread]);

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();

    return notifications
      .filter((n) => {
        if (onlyUnread && n.read) return false;

        const matchesType =
          filter === "All" ||
          (filter === "Ticket" &&
            ["ticket_assignment", "status_change", "customer_reply"].includes(n.type)) ||
          (filter === "SLA" && n.type === "sla_warning") ||
          (filter === "Reports" && n.type === "report_ready") ||
          (filter === "System" && n.type === "system");

        const blob = `${n.title} ${n.message} ${n.ticketId ?? ""} ${n.reportId ?? ""}`
          .toLowerCase();

        return matchesType && (!q || blob.includes(q));
      })
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  }, [notifications, query, filter, onlyUnread]);

  const markAllRead = async () => {
    const token = getAuthToken();
    if (!token) return;

    // optimistic UI
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    setUnreadCount(0);

    try {
      const res = await fetch(`${API_BASE}/employee/notifications/read-all`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        // revert by refetch
        await fetchNotifications({ unreadOnly: onlyUnread });
      }
    } catch {
      await fetchNotifications({ unreadOnly: onlyUnread });
    }
  };

  const markOneRead = async (notificationId) => {
    const token = getAuthToken();
    if (!token) return;

    try {
      await fetch(`${API_BASE}/employee/notifications/${notificationId}/read`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch {
      // ignore; UI is already updated optimistically
    }
  };

  const onNotificationClick = async (n) => {
    // optimistic
    setNotifications((prev) =>
      prev.map((x) => (x.id === n.id ? { ...x, read: true } : x))
    );
    if (!n.read) setUnreadCount((c) => Math.max(0, c - 1));

    await markOneRead(n.id);

    if (n.ticketId) {
      navigate(`/employee/details/${n.ticketId}`);
    } else if (n.reportId) {
      navigate(`/employee/reports?report=${encodeURIComponent(n.reportId)}`);
    }
  };

  return (
    <Layout role="employee">
      <div className="empNotifs">
        <PageHeader
          title="Notifications"
          subtitle={`You have ${unreadCount} unread notification${unreadCount === 1 ? "" : "s"}.`}
          actions={
            <button
              className="filterPillBtn empNotifs__actionBtn"
              onClick={markAllRead}
              disabled={loading || notifications.length === 0}
              title={notifications.length === 0 ? "No notifications" : "Mark all as read"}
            >
              Mark all as read
            </button>
          }
        />

        <div className="empNotifs__controls">
          <PillSearch
            value={query}
            onChange={(v) =>
              typeof v === "string" ? setQuery(v) : setQuery(v?.target?.value ?? "")
            }
            placeholder="Search notifications..."
          />

          <div className="empNotifs__filtersRow">
            <PillSelect
              value={filter}
              onChange={setFilter}
              ariaLabel="Filter notifications"
              options={[
                { value: "All", label: "All" },
                { value: "Ticket", label: "Ticket" },
                { value: "SLA", label: "SLA" },
                { value: "Reports", label: "Reports" },
                { value: "System", label: "System" },
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
                className={`empNotifs__item ${n.read ? "read" : "unread"} ${
                  n.ticketId || n.reportId ? "clickable" : ""
                }`}
                onClick={() => (n.ticketId || n.reportId ? onNotificationClick(n) : null)}
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
                      {n.ticketId && <span>• {n.ticketId}</span>}
                      {n.reportId && <span>• {n.reportId}</span>}
                    </div>
                  </div>
                </div>

                <div className="empNotifs__right">
                  {!n.read && <span className="empNotifs__dot" />}
                  {(n.ticketId || n.reportId) && <span className="empNotifs__chev">›</span>}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </Layout>
  );
}