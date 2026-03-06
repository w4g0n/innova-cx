import { useState, useRef, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useTheme, ThemeToggleBtn } from "./customerTheme";
import { getUser, getToken } from "../../utils/auth";
import { getInitialsFromEmail } from "../../utils/userDisplay";
import { apiUrl } from "../../config/apiBase";
import novaLogo from "../../assets/nova-logo.png";
import "./CustomerHistory.css";

const STATUS_KEYS = ["all", "open", "inprogress", "assigned", "resolved", "overdue"];
const STATUS_LABELS = {
  all: "All",
  open: "Open",
  inprogress: "In Progress",
  assigned: "Assigned",
  resolved: "Resolved",
  overdue: "Overdue",
};

function normalizeStatus(s = "") {
  return s.toLowerCase().replace(/[\s_-]+/g, "");
}

function formatTimeAgo(isoString) {
  if (!isoString) return "";
  const diff = Math.floor((Date.now() - new Date(isoString)) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
  return new Date(isoString).toLocaleDateString();
}

export default function CustomerMyTickets() {
  const navigate = useNavigate();
  const [theme, toggleTheme] = useTheme();
  const [user] = useState(() => getUser() || {});
  const profileRef = useRef(null);
  const notifRef = useRef(null);

  const [tickets, setTickets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const [filterStatus, setFilterStatus] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [sortOrder, setSortOrder] = useState("newest"); // newest | oldest

  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState([]);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  const initials = getInitialsFromEmail(user?.email, "U");
  const displayName = useMemo(() => {
    const name = user?.name || user?.full_name || "";
    if (name) return name.split(" ")[0];
    const email = (user?.email || "")
      .split("@")[0]
      .replace(/[._\-\d]+/g, " ")
      .trim();
    if (!email) return "User";
    return email.split(" ")[0].charAt(0).toUpperCase() + email.split(" ")[0].slice(1);
  }, [user]);

  const unreadCount = useMemo(() => notifications.filter((n) => !n.read).length, [notifications]);

  // Fetch tickets
  useEffect(() => {
    async function load() {
      try {
        const token = getToken();
        const res = await fetch(apiUrl("/api/customer/mytickets"), {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error("Failed to load tickets.");
        const data = await res.json();
        setTickets(data.tickets || []);
      } catch (e) {
        setError(e.message);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  // Fetch notifications
  useEffect(() => {
    async function loadNotifs() {
      try {
        const token = getToken();
        const res = await fetch(apiUrl("/api/customer/notifications"), {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) setNotifications((await res.json()).notifications || []);
      } catch (_err) {
        // ignore notification fetch errors (non-critical)
      }
    }
    loadNotifs();
  }, []);

  // Click-outside to close popovers
  useEffect(() => {
    const handler = (e) => {
      if (profileRef.current && !profileRef.current.contains(e.target)) setProfileMenuOpen(false);
      if (notifRef.current && !notifRef.current.contains(e.target)) setNotifOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Filtered + sorted tickets
  const displayedTickets = useMemo(() => {
    let list = [...tickets];

    // Filter by status
    if (filterStatus !== "all") {
      list = list.filter((t) => normalizeStatus(t.status) === filterStatus);
    }

    // Search
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      list = list.filter(
        (t) =>
          (t.ticketId || "").toLowerCase().includes(q) ||
          (t.subject || t.description?.subject || "").toLowerCase().includes(q) ||
          (t.status || "").toLowerCase().includes(q) ||
          (t.ticketType || t.type || "").toLowerCase().includes(q)
      );
    }

    // Sort by latest (updatedAt or issueDate), default newest first
    list.sort((a, b) => {
      const da = new Date(a.updatedAt || a.issueDate || 0);
      const db = new Date(b.updatedAt || b.issueDate || 0);
      return sortOrder === "newest" ? db - da : da - db;
    });

    return list;
  }, [tickets, filterStatus, searchQuery, sortOrder]);

  const markNotificationsRead = async () => {
    try {
      const token = getToken();
      await fetch(apiUrl("/api/customer/notifications?mark_read=true"), {
        headers: { Authorization: `Bearer ${token}` },
      });
      setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    } catch (_err) {
      // ignore mark-read errors (non-critical)
    }
  };

  const handleLogout = () => {
    setProfileMenuOpen(false);
    setShowLogoutConfirm(true);
  };

  const confirmLogout = () => {
    ["user", "token", "temp_token", "access_token"].forEach((k) => localStorage.removeItem(k));
    navigate("/");
  };

  return (
    <div className="cs-page cmyt-page">
      {/* TOPBAR */}
      <header className="cs-topbar">
        <div className="cs-topbar-left">
          <img src={novaLogo} alt="InnovaAI" className="cs-topbar-logo" />
          <div className="cs-topbar-divider" />
          <span className="cs-topbar-label">My Tickets</span>
        </div>
        <div className="cs-topbar-right">
          <ThemeToggleBtn theme={theme} onToggle={toggleTheme} />

          {/* Notifications */}
          <div className="navAction" ref={notifRef}>
            <button
              type="button"
              className={`cl-icon-btn${notifOpen ? " is-active" : ""}`}
              onClick={() => {
                setNotifOpen((p) => !p);
                setProfileMenuOpen(false);
                if (!notifOpen) markNotificationsRead();
              }}
            >
              <svg
                width="17"
                height="17"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
              </svg>
              {unreadCount > 0 && <span className="notifBadge">{unreadCount > 9 ? "9+" : unreadCount}</span>}
            </button>

            {notifOpen && (
              <div className="navPopover">
                <div className="navPopoverHeader">Notifications</div>
                <div className="navPopoverList">
                  {notifications.length === 0 ? (
                    <div className="navPopoverEmpty">No notifications</div>
                  ) : (
                    notifications.map((n, i) => (
                      <div key={i} className={`navPopoverItem${n.read ? "" : " unread"}`}>
                        <div className="navPopoverItemHeader">
                          <span className="navPopoverItemTitle">{n.title || "Update"}</span>
                          <span className="navPopoverItemTime">{formatTimeAgo(n.createdAt)}</span>
                        </div>
                        <div className="navPopoverItemMeta">{n.message || n.body}</div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Profile */}
          <div className="navAction" ref={profileRef}>
            <button
              type="button"
              className={`cl-avatar-btn${profileMenuOpen ? " is-active" : ""}`}
              onClick={() => {
                setProfileMenuOpen((p) => !p);
                setNotifOpen(false);
              }}
            >
              <div className="cl-avatar-initials">{initials}</div>
              <span className="cl-avatar-name">{displayName}</span>
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.2"
                strokeLinecap="round"
                strokeLinejoin="round"
                style={{ marginLeft: 2 }}
              >
                <path d="M6 9l6 6 6-6" />
              </svg>
            </button>

            {profileMenuOpen && (
              <div className="navDropdown">
                <button type="button" className="navDropdownItem" onClick={() => navigate("/customer/settings")}>
                  Settings
                </button>
                <div className="navDropdownDivider" />
                <button type="button" className="navDropdownItem danger" onClick={handleLogout}>
                  Log out
                </button>
              </div>
            )}
          </div>

          <button type="button" className="cs-back-btn" onClick={() => navigate("/customer")}>
            <svg
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M19 12H5M12 5l-7 7 7 7" />
            </svg>
            Dashboard
          </button>
        </div>
      </header>

      {/* HERO */}
      <section className="cs-hero">
        <div className="cs-hero-neb cs-hero-neb1" />
        <div className="cs-hero-neb cs-hero-neb2" />
        <div className="cs-hero-content">
          <div className="cs-eyebrow">
            <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor">
              <circle cx="12" cy="12" r="5" />
            </svg>
            Support History
          </div>
          <h1 className="cs-page-title">
            My <span className="cs-grad-text">Tickets</span>
          </h1>
          <p className="cs-page-sub">All your submitted requests, ordered by most recent activity.</p>
        </div>
      </section>

      {/* MAIN */}
      <main className="cs-main">
        {/* TOOLBAR */}
        <div className="cmyt-toolbar">
          {/* Search */}
          <div className="cmyt-search-wrap">
            <svg
              className="cmyt-search-icon"
              width="15"
              height="15"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <circle cx="11" cy="11" r="8" />
              <path d="M21 21l-4.35-4.35" />
            </svg>

            <input
              className="cmyt-search-input"
              placeholder="Search tickets…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />

            {searchQuery && (
              <button type="button" className="cmyt-search-clear" onClick={() => setSearchQuery("")}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none">
                  <path
                    d="M18 6 6 18M6 6l12 12"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            )}
          </div>

          <div className="cmyt-toolbar-right">
            {/* Sort */}
            <div className="cmyt-sort-group">
              <button
                type="button"
                className={`cmyt-sort-btn${sortOrder === "newest" ? " cmyt-sort-btn--active" : ""}`}
                onClick={() => setSortOrder("newest")}
              >
                <svg
                  width="13"
                  height="13"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M3 4h13M3 8h9M3 12h5M17 4v16M17 20l-4-4M17 20l4-4" />
                </svg>
                Newest
              </button>

              <button
                type="button"
                className={`cmyt-sort-btn${sortOrder === "oldest" ? " cmyt-sort-btn--active" : ""}`}
                onClick={() => setSortOrder("oldest")}
              >
                <svg
                  width="13"
                  height="13"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M3 4h13M3 8h9M3 12h5M17 4v16M17 4l-4 4M17 4l4 4" />
                </svg>
                Oldest
              </button>
            </div>
          </div>
        </div>

        {/* STATUS FILTER TABS */}
        <div className="cmyt-tabs">
          {STATUS_KEYS.map((k) => {
            const count = k === "all" ? tickets.length : tickets.filter((t) => normalizeStatus(t.status) === k).length;
            return (
              <button
                key={k}
                type="button"
                className={`cmyt-tab${filterStatus === k ? " cmyt-tab--active" : ""}`}
                onClick={() => setFilterStatus(k)}
              >
                {STATUS_LABELS[k]}
                {count > 0 && <span className="cmyt-tab-count">{count}</span>}
              </button>
            );
          })}
        </div>

        {/* TICKET LIST */}
        {loading ? (
          <div className="cmyt-list">
            {[1, 2, 3].map((i) => (
              <div key={i} className="cs-card cmyt-skeleton-card">
                <div className="cs-skeleton-line" style={{ width: "35%", height: 12, marginBottom: 10 }} />
                <div className="cs-skeleton-line" style={{ width: "65%", height: 18, marginBottom: 14 }} />
                <div className="cs-skeleton-line" style={{ width: "45%", height: 12 }} />
              </div>
            ))}
          </div>
        ) : error ? (
          <div className="cmyt-empty">
            <svg
              width="44"
              height="44"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.4"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="cmyt-empty-icon"
            >
              <circle cx="12" cy="12" r="10" />
              <path d="M12 8v4M12 16h.01" />
            </svg>
            <p className="cmyt-empty-title">Couldn&apos;t load tickets</p>
            <p className="cmyt-empty-sub">{error}</p>
          </div>
        ) : displayedTickets.length === 0 ? (
          <div className="cmyt-empty">
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.3"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="cmyt-empty-icon"
            >
              <path d="M2 9a1 1 0 0 1 1-1h18a1 1 0 0 1 1 1v1.5a1.5 1.5 0 0 0 0 3V15a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-1.5a1.5 1.5 0 0 0 0-3V9z" />
              <path d="M9 12h6M9 15h4" />
            </svg>
            <p className="cmyt-empty-title">
              {filterStatus === "all" && !searchQuery ? "No tickets yet" : "No tickets match"}
            </p>
            <p className="cmyt-empty-sub">
              {filterStatus === "all" && !searchQuery
                ? "Your submitted tickets will appear here."
                : "Try adjusting your filters or search."}
            </p>
            {filterStatus !== "all" && (
              <button
                type="button"
                className="cs-btn cs-btn-ghost"
                style={{ marginTop: 14 }}
                onClick={() => {
                  setFilterStatus("all");
                  setSearchQuery("");
                }}
              >
                Clear filters
              </button>
            )}
          </div>
        ) : (
          <div className="cmyt-list">
            {displayedTickets.map((t, idx) => (
              <div
                key={t.ticketId || idx}
                className="cs-card cmyt-ticket-card"
                role="button"
                tabIndex={0}
                onClick={() => navigate(`/customer/ticket/${t.ticketId}`)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") navigate(`/customer/ticket/${t.ticketId}`);
                }}
                style={{ animationDelay: `${idx * 0.04}s` }}
              >
                <div className="cmyt-ticket-toprow">
                  <span className="cmyt-ticket-id">{t.ticketId}</span>
                  <span className="cmyt-ticket-sep">·</span>
                  <span className="cmyt-ticket-type">{t.ticketType || t.type}</span>
                  <span style={{ flex: 1 }} />
                  <span className={`cs-status cs-status--${normalizeStatus(t.status)}`}>
                    <span className="cs-status-dot" />
                    {t.status}
                  </span>
                  <span className="cs-priority">{t.priority}</span>
                </div>

                <h3 className="cmyt-ticket-subject">{t.subject || t.description?.subject || "Untitled Ticket"}</h3>

                <div className="cmyt-ticket-footer">
                  <span className="cmyt-ticket-date">
                    <svg
                      width="11"
                      height="11"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <circle cx="12" cy="12" r="10" />
                      <path d="M12 6v6l4 2" />
                    </svg>
                    {formatTimeAgo(t.updatedAt || t.issueDate)}
                  </span>
                  <span className="cmyt-view-cta">
                    View details
                    <svg
                      width="13"
                      height="13"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M5 12h14M13 6l6 6-6 6" />
                    </svg>
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      {/* LOGOUT MODAL */}
      {showLogoutConfirm && (
        <div className="cmyt-modal-overlay">
          <div className="cmyt-modal">
            <p>Are you sure you want to log out?</p>
            <div className="cmyt-modal-btns">
              <button type="button" className="cs-btn cs-btn-primary" onClick={confirmLogout}>
                Log out
              </button>
              <button type="button" className="cs-btn cs-btn-ghost" onClick={() => setShowLogoutConfirm(false)}>
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      <footer className="cs-footer">
        <img src={novaLogo} alt="InnovaAI" className="cs-footer-logo" />
        <p className="cs-footer-copy">© 2026 InnovaAI</p>
      </footer>
    </div>
  );
}