import { useState, useRef, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useTheme, ThemeToggleBtn } from "./CustomerTheme";
import { getUser, getToken } from "../../utils/auth";
import { getInitialsFromEmail } from "../../utils/userDisplay";
import { apiUrl } from "../../config/apiBase";
import novaLogo from "../../assets/nova-logo.png";
import {
  sanitizeText,
  sanitizeId,
  sanitizeSearchQuery,
  formatTimeAgo,
} from "./sanitize";
import "./CustomerHistory.css";

const STATUS_KEYS = ["all", "open", "inprogress", "assigned", "resolved", "overdue"];
const STATUS_LABELS = {
  all:        "All",
  open:       "Open",
  inprogress: "In Progress",
  assigned:   "Assigned",
  resolved:   "Resolved",
  overdue:    "Overdue",
};

// Allowlist for sort order values — never trust user-controlled state directly in sort logic
const ALLOWED_SORT_ORDERS = ["newest", "oldest"];

function normalizeStatus(s = "") {
  return s.toLowerCase().replace(/[\s_-]+/g, "");
}

/**
 * Safely normalise a ticket field from the API for display.
 * All ticket data comes from the server — sanitize before rendering.
 */
function safeTicketField(val, maxLen = 200) {
  return sanitizeText(val, maxLen);
}

export default function CustomerMyTickets() {
  const navigate = useNavigate();
  const [theme, toggleTheme] = useTheme();
  const [user] = useState(() => getUser() || {});
  const profileRef = useRef(null);
  const notifRef   = useRef(null);

  const [tickets,      setTickets]      = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState(null);

  const [filterStatus, setFilterStatus] = useState("all");
  const [searchQuery,  setSearchQuery]  = useState("");
  const [sortOrder,    setSortOrder]    = useState("newest");

  const [profileMenuOpen,    setProfileMenuOpen]    = useState(false);
  const [notifOpen,          setNotifOpen]          = useState(false);
  const [notifications,      setNotifications]      = useState([]);
  const [showLogoutConfirm,  setShowLogoutConfirm]  = useState(false);

  // Sanitize user-derived display values
  const initials    = getInitialsFromEmail(user?.email, "U");
  const displayName = useMemo(() => {
    const name  = sanitizeText(user?.name || user?.full_name || "", 100);
    if (name) return name.split(" ")[0];
    const email = sanitizeText(user?.email || "", 254)
      .split("@")[0]
      .replace(/[._\-\d]+/g, " ")
      .trim();
    if (!email) return "User";
    return (
      email.split(" ")[0].charAt(0).toUpperCase() + email.split(" ")[0].slice(1)
    );
  }, [user]);

  const unreadCount = useMemo(
    () => notifications.filter((n) => !n.read).length,
    [notifications]
  );

  // Fetch tickets
  useEffect(() => {
    async function load() {
      try {
        const token = getToken();
        const res   = await fetch(apiUrl("/api/customer/mytickets"), {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) throw new Error("Failed to load tickets.");
        const data = await res.json();
        setTickets(Array.isArray(data.tickets) ? data.tickets : []);
      } catch (e) {
        console.error(e);
        // Use a fixed message — never render raw error.message which can contain
        // server-side stack traces or injection payloads
        setError("Unable to load your tickets. Please try again later.");
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
        const res   = await fetch(apiUrl("/api/customer/notifications"), {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setNotifications(Array.isArray(data.notifications) ? data.notifications : []);
        }
      } catch {
        // ignore notification fetch errors (non-critical)
      }
    }
    loadNotifs();
  }, []);

  // Click-outside to close popovers
  useEffect(() => {
    const handler = (e) => {
      if (profileRef.current && !profileRef.current.contains(e.target))
        setProfileMenuOpen(false);
      if (notifRef.current && !notifRef.current.contains(e.target))
        setNotifOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Filtered + sorted tickets
  const displayedTickets = useMemo(() => {
    let list = [...tickets];

    if (filterStatus !== "all") {
      list = list.filter((t) => normalizeStatus(t.status) === filterStatus);
    }

    // sanitizeSearchQuery caps length at 200 and trims
    if (searchQuery.trim()) {
      const q = sanitizeSearchQuery(searchQuery).toLowerCase();
      list = list.filter(
        (t) =>
          safeTicketField(t.ticketId).toLowerCase().includes(q) ||
          safeTicketField(t.subject || t.description?.subject).toLowerCase().includes(q) ||
          safeTicketField(t.status).toLowerCase().includes(q) ||
          safeTicketField(t.ticketType || t.type).toLowerCase().includes(q)
      );
    }

    // Validate sort order against allowlist before using it in comparator
    const order = ALLOWED_SORT_ORDERS.includes(sortOrder) ? sortOrder : "newest";
    list.sort((a, b) => {
      const da = new Date(a.updatedAt || a.issueDate || 0);
      const db = new Date(b.updatedAt || b.issueDate || 0);
      return order === "newest" ? db - da : da - db;
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
    } catch {
      // ignore mark-read errors (non-critical)
    }
  };

  const dismissNotification = async (notifId) => {
    // Optimistically remove from list immediately
    setNotifications((prev) => prev.filter((n) => n.id !== notifId));
    // Mark as read on the backend (best-effort)
    try {
      const token = getToken();
      await fetch(
        apiUrl("/api/customer/notifications?mark_read=true"),
        { headers: { Authorization: `Bearer ${token}` } }
      );
    } catch { /* non-critical */ }
  };

  const handleLogout = () => {
    setProfileMenuOpen(false);
    setShowLogoutConfirm(true);
  };

  const confirmLogout = () => {
    ["user", "token", "temp_token", "access_token"].forEach((k) =>
      localStorage.removeItem(k)
    );
    navigate("/");
  };

  return (
    <div className="cs-page cmyt-page">
      {/* TOPBAR */}
      <header className="cs-topbar">
        <div className="cs-topbar-left">
          <img
            src={novaLogo}
            alt="InnovaAI"
            className="cs-topbar-logo cs-topbar-logo--clickable"
            onClick={() => navigate("/customer")}
            style={{ cursor: "pointer" }}
          />
          <div className="cs-topbar-divider" />
          <span className="cs-topbar-label">My Tickets</span>
          <button
            type="button"
            className="cs-back-btn"
            aria-label="Back to dashboard"
            onClick={() => navigate("/customer")}
          >
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

        <div className="cs-topbar-right">
          <ThemeToggleBtn theme={theme} onToggle={toggleTheme} />

          {/* Notifications */}
          <div className="navAction" ref={notifRef}>
            <button
              type="button"
              className={`cl-icon-btn${notifOpen ? " is-active" : ""}`}
              aria-label="Notifications"
              aria-haspopup="true"
              aria-expanded={notifOpen}
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
              {unreadCount > 0 && (
                <span className="notifBadge">
                  {unreadCount > 9 ? "9+" : unreadCount}
                </span>
              )}
            </button>

            {notifOpen && (
              <div className="navPopover" role="menu" aria-label="Notifications">
                <div className="navPopoverHeader">Notifications</div>
                <div className="navPopoverList">
                  {notifications.length === 0 ? (
                    <div className="navPopoverEmpty">No notifications</div>
                  ) : (
                    notifications.map((n, i) => (
                      <div
                        key={n.id || i}
                        className={`navPopoverItem${n.read ? "" : " unread"}`}
                      >
                        <div className="navPopoverItemHeader">
                          {/* Sanitize server-supplied notification fields before rendering */}
                          <span className="navPopoverItemTitle">
                            {sanitizeText(n.title || "Update", 100)}
                          </span>
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span className="navPopoverItemTime">
                              {formatTimeAgo(n.timestamp || n.createdAt)}
                            </span>
                            <button
                              type="button"
                              onClick={(e) => { e.stopPropagation(); dismissNotification(n.id); }}
                              style={{
                                background: "transparent", border: "none", cursor: "pointer",
                                color: "var(--muted)", display: "flex", alignItems: "center",
                                padding: "2px", borderRadius: 4, lineHeight: 1,
                                transition: "color .15s",
                              }}
                              onMouseEnter={(e) => e.currentTarget.style.color = "var(--text)"}
                              onMouseLeave={(e) => e.currentTarget.style.color = "var(--muted)"}
                              aria-label="Dismiss notification"
                            >
                              <svg width="12" height="12" viewBox="0 0 24 24" fill="none">
                                <path d="M18 6 6 18M6 6l12 12" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/>
                              </svg>
                            </button>
                          </div>
                        </div>
                        <div className="navPopoverItemMeta">
                          {sanitizeText(n.message || n.body || "", 300)}
                        </div>
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
              aria-label="Account menu"
              aria-haspopup="true"
              aria-expanded={profileMenuOpen}
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
              <div className="navDropdown" role="menu">
                <button
                  type="button"
                  className="navDropdownItem"
                  role="menuitem"
                  onClick={() => navigate("/customer/settings")}
                >
                  Settings
                </button>
                <div className="navDropdownDivider" />
                <button
                  type="button"
                  className="navDropdownItem danger"
                  role="menuitem"
                  onClick={handleLogout}
                >
                  Log out
                </button>
              </div>
            )}
          </div>
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
          <p className="cs-page-sub">
            All your submitted requests, ordered by most recent activity.
          </p>
        </div>
      </section>

      {/* MAIN */}
      <main className="cs-main">
        {/* TOOLBAR */}
        <div className="cmyt-toolbar">
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
              onChange={(e) => {
                // sanitizeSearchQuery enforced at filter time; cap input here too
                const v = e.target.value;
                if (v.length <= 200) setSearchQuery(v);
              }}
              maxLength={200}
            />

            {searchQuery && (
              <button
                type="button"
                className="cmyt-search-clear"
                aria-label="Clear search"
                onClick={() => setSearchQuery("")}
              >
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
            <div className="cmyt-sort-group">
              {ALLOWED_SORT_ORDERS.map((order) => (
                <button
                  key={order}
                  type="button"
                  className={`cmyt-sort-btn${sortOrder === order ? " cmyt-sort-btn--active" : ""}`}
                  onClick={() => setSortOrder(order)}
                >
                  {order === "newest" ? (
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M3 4h13M3 8h9M3 12h5M17 4v16M17 20l-4-4M17 20l4-4" />
                    </svg>
                  ) : (
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M3 4h13M3 8h9M3 12h5M17 4v16M17 4l-4 4M17 4l4 4" />
                    </svg>
                  )}
                  {order.charAt(0).toUpperCase() + order.slice(1)}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* STATUS FILTER TABS */}
        <div className="cmyt-tabs">
          {STATUS_KEYS.map((k) => {
            const count =
              k === "all"
                ? tickets.length
                : tickets.filter((t) => normalizeStatus(t.status) === k).length;
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
            {/* error is set from a fixed internal string — never raw network error text */}
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
              {filterStatus === "all" && !searchQuery
                ? "No tickets yet"
                : "No tickets match"}
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
            {displayedTickets.map((t, idx) => {
              // Sanitize all ticket fields from the API before rendering
              const ticketId  = sanitizeId(t.ticketId, 48);
              const subject   = safeTicketField(t.subject || t.description?.subject || "Untitled Ticket", 200);
              const status    = safeTicketField(t.status, 40);
              const priority  = safeTicketField(t.priority, 20);
              const ticketType = safeTicketField(t.ticketType || t.type, 60);
              const statusKey = normalizeStatus(status);

              return (
                <div
                  key={ticketId || idx}
                  className="cs-card cmyt-ticket-card"
                  role="button"
                  tabIndex={0}
                  aria-label={`View ticket ${ticketId}: ${subject}`}
                  onClick={() => navigate(`/customer/ticket/${encodeURIComponent(ticketId)}`)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ")
                      navigate(`/customer/ticket/${encodeURIComponent(ticketId)}`);
                  }}
                  style={{ animationDelay: `${idx * 0.04}s` }}
                >
                  <div className="cmyt-ticket-toprow">
                    <span className="cmyt-ticket-id">{ticketId}</span>
                    <span className="cmyt-ticket-sep">·</span>
                    <span className="cmyt-ticket-type">{ticketType}</span>
                    <span style={{ flex: 1 }} />
                    <span className={`cs-status cs-status--${statusKey}`}>
                      <span className="cs-status-dot" />
                      {status}
                    </span>
                    <span className="cs-priority">{priority}</span>
                  </div>

                  <h3 className="cmyt-ticket-subject">{subject}</h3>

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
                      {/* formatTimeAgo validates the date value before use */}
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
              );
            })}
          </div>
        )}
      </main>

      {/* LOGOUT MODAL */}
      {showLogoutConfirm && (
        <div
          className="novaCloseModal"
          role="dialog"
          aria-modal="true"
          aria-label="Confirm logout"
          onClick={() => setShowLogoutConfirm(false)}
        >
          <div
            className="novaCloseModalContent"
            onClick={(e) => e.stopPropagation()}
          >
            <p>Are you sure you want to log out?</p>
            <div className="novaCloseModalBtns">
              <button onClick={confirmLogout}>Log out</button>
              <button onClick={() => setShowLogoutConfirm(false)}>Cancel</button>
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