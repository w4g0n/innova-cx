import { useMemo, useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import PillSearch from "../../components/common/PillSearch";
import PillSelect from "../../components/common/PillSelect";
import { apiUrl } from "../../config/apiBase";
import "./OperatorNotifications.css";

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
    case "user_created":     return "👤";
    case "user_deactivated":
    case "user_deleted":     return "🗑️";
    case "model_alert":      return "🤖";
    case "model_ready":      return "✅";
    case "chatbot_issue":    return "💬";
    case "escalation":       return "🚨";
    case "report_ready":     return "📊";
    case "system":           return "🛠️";
    default:                 return "🔔";
  }
}

function Toast({ message, visible }) {
  return (
    <div
      style={{
        position: "fixed",
        bottom: "28px",
        right: "28px",
        background: "#1e1e2e",
        color: "#fff",
        padding: "12px 20px",
        borderRadius: "10px",
        fontSize: "14px",
        fontWeight: 500,
        boxShadow: "0 4px 20px rgba(0,0,0,0.25)",
        display: "flex",
        alignItems: "center",
        gap: "8px",
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(12px)",
        transition: "opacity 0.25s ease, transform 0.25s ease",
        pointerEvents: "none",
        zIndex: 9999,
      }}
    >
      <span style={{ fontSize: "16px" }}>✅</span>
      {message}
    </div>
  );
}

export default function OperatorNotifications() {
  const navigate = useNavigate();

  const [notifications, setNotifications] = useState([]);
  const [query, setQuery]               = useState("");
  const [filter, setFilter]             = useState("All");
  const [onlyUnread, setOnlyUnread]     = useState(false);
  const [loading, setLoading]           = useState(false);
  const [error, setError]               = useState("");
  const [toast, setToast]               = useState({ visible: false, message: "" });

  const token = localStorage.getItem("access_token");

  const showToast = (message) => {
    setToast({ visible: true, message });
    setTimeout(() => setToast({ visible: false, message: "" }), 2500);
  };

  const fetchNotifications = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const res = await fetch(apiUrl("/api/operator/notifications"), {
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
  }, [fetchNotifications, navigate, token]);

  const unreadCount = useMemo(
    () => notifications.filter((n) => !n.read).length,
    [notifications]
  );

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    return notifications
      .filter((n) => {
        if (onlyUnread && n.read) return false;

        const matchesType =
          filter === "All" ||
          (filter === "Users"      && ["user_created", "user_deactivated", "user_deleted"].includes(n.type)) ||
          (filter === "Model"      && ["model_alert", "model_ready", "chatbot_issue"].includes(n.type)) ||
          (filter === "System"     && n.type === "system") ||
          (filter === "Escalation" && n.type === "escalation") ||
          (filter === "Reports"    && n.type === "report_ready");

        const blob = `${n.title} ${n.message} ${n.userId ?? ""} ${n.reportId ?? ""}`.toLowerCase();
        return matchesType && (!q || blob.includes(q));
      })
      .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
  }, [notifications, query, filter, onlyUnread]);

  const markAllRead = async () => {
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    try {
      await fetch(apiUrl("/api/operator/notifications/read-all"), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      showToast("All notifications marked as read");
    } catch (e) {
      console.error("Failed to mark all notifications as read:", e);
    }
  };

  const onNotificationClick = async (n) => {
    if (n.read) {
      // Already read — just navigate if applicable
      if (n.userId)   navigate(`/operator/users`);
      if (n.reportId) navigate(`/operator/model-analysis`);
      return;
    }

    setNotifications((prev) =>
      prev.map((x) => (x.id === n.id ? { ...x, read: true } : x))
    );
    try {
      await fetch(apiUrl(`/api/operator/notifications/${n.id}/read`), {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      showToast("Notification marked as read");
    } catch (e) {
      console.error("Failed to mark notification as read:", e);
    }
    if (n.userId)   navigate(`/operator/users`);
    if (n.reportId) navigate(`/operator/model-analysis`);
  };

  return (
    <Layout role="operator">
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
                { value: "All",        label: "All" },
                { value: "Users",      label: "Users" },
                { value: "Model",      label: "Model" },
                { value: "Escalation", label: "Escalation" },
                { value: "Reports",    label: "Reports" },
                { value: "System",     label: "System" },
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
            <div className="empNotifs__empty">Loading…</div>
          ) : filtered.length === 0 ? (
            <div className="empNotifs__empty">No notifications found.</div>
          ) : (
            filtered.map((n) => (
              <div
                key={n.id}
                className={`empNotifs__item ${n.read ? "read" : "unread"} clickable`}
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
                      {n.userId   && <span>• {n.userId}</span>}
                      {n.reportId && <span>• {n.reportId}</span>}
                    </div>
                  </div>
                </div>

                <div className="empNotifs__right">
                  {!n.read && <span className="empNotifs__dot" />}
                  {(n.userId || n.reportId) && <span className="empNotifs__chev">›</span>}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <Toast message={toast.message} visible={toast.visible} />
    </Layout>
  );
}