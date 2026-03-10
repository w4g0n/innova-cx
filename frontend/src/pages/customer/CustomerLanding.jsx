import React, { useMemo, useRef, useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import "./CustomerLanding.css";
import novaLogo from "../../assets/nova-logo.png";
import CustomerFillForm from "./CustomerFillForm";
import useNovaChatbot from "./chatbot.js";
import { apiUrl } from "../../config/apiBase";
import { getInitialsFromEmail } from "../../utils/userDisplay";
import { getToken} from "../../utils/auth";
import { useTheme, ThemeToggleBtn } from "./CustomerTheme";

export default function CustomerLanding() {
  const navigate = useNavigate();

// 3 quick actions — Settings removed (profile only), spans full grid width
const QUICK_ACTIONS = [
  {
    action: "nova",
    title: "Chat with Nova",
    desc: "Get instant help from our AI assistant",
    accent: "#c084fc",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
        <circle cx="9" cy="10" r=".8" fill="currentColor" stroke="none"/>
        <circle cx="12" cy="10" r=".8" fill="currentColor" stroke="none"/>
        <circle cx="15" cy="10" r=".8" fill="currentColor" stroke="none"/>
      </svg>
    ),
  },
  {
    action: "tickets",
    title: "My Tickets",
    desc: "View and track all your submitted tickets",
    accent: "#818cf8",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="2" y="5" width="20" height="14" rx="2"/>
        <path d="M16 2v6M8 2v6M2 10h20"/>
        <path d="M7 15h4M7 18h2"/>
      </svg>
    ),
  },
  {
    action: "form",
    title: "Fill a Form",
    desc: "Submit a new support request",
    accent: "#e879f9",
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="12" y1="18" x2="12" y2="12"/>
        <line x1="9" y1="15" x2="15" y2="15"/>
      </svg>
    ),
  },
];

  // ── Theme ─────────────────────────────────────────────────────────────────
  const [theme, toggleTheme] = useTheme();

  const [embeddedFormType, setEmbeddedFormType] = useState("Complaint");

  const {
    listRef,
    messages,
    text,
    setText,
    handleSend,
    resetSession,
  } = useNovaChatbot({
    onGoToForm: (type) => {
      resetSession();
      setEmbeddedFormType(type || "Complaint");
      if (!isOpen) setIsOpen(true);
      setNovaView("form");
      setIsExpanded(true);
    },
  });

  const profileRef = useRef(null);
  const notifRef = useRef(null);
  const loadingTimeoutRef = useRef(null);

  // ── Nova chat widget state ──────────────────────────────────────────────
  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [showCloseConfirm, setShowCloseConfirm] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  // ── Fill-Form widget state ──────────────────────────────────────────────
  const [formOpen, setFormOpen] = useState(false);
  const [formExpanded, setFormExpanded] = useState(false);
  const [showFormCloseConfirm, setShowFormCloseConfirm] = useState(false);

  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);

  const [novaView, setNovaView] = useState("chat");

  const [user] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("user")) || {};
    } catch {
      return {};
    }
  });
  const [notifications, setNotifications] = useState([]);
  const [recentTicket, setRecentTicket] = useState(null);
  const [ticketLoading, setTicketLoading] = useState(true);

  const hasUsableSubject = useCallback((ticket) => {
    const subject = (ticket?.subject || ticket?.description?.subject || "").trim();
    return subject.length > 0;
  }, []);

  const fetchRecentTicket = useCallback(async () => {
    try {
      const token = getToken();
      const res = await fetch(apiUrl("/api/customer/mytickets"), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        const tickets = data.tickets || [];
        // Backend already returns ORDER BY created_at DESC.
        const mostRecent = tickets[0] || null;
        setRecentTicket(mostRecent);
        // Only keep loading if subject is missing AND we haven't hit the 4s cap yet.
        // The cap is enforced by loadingTimeoutRef set at call-site.
        if (!mostRecent || hasUsableSubject(mostRecent)) {
          setTicketLoading(false);
          if (loadingTimeoutRef.current) clearTimeout(loadingTimeoutRef.current);
        }
        return;
      }
      setRecentTicket(null);
      setTicketLoading(false);
    } catch {
      setRecentTicket(null);
      setTicketLoading(false);
    }
  }, [hasUsableSubject]);

  useEffect(() => {
    const timer = setTimeout(() => {
      void fetchRecentTicket();
    }, 0);
    // Hard cap: never show skeleton for more than 4 seconds regardless of subject
    loadingTimeoutRef.current = setTimeout(() => setTicketLoading(false), 4000);
    return () => {
      clearTimeout(timer);
      if (loadingTimeoutRef.current) clearTimeout(loadingTimeoutRef.current);
    };
  }, [fetchRecentTicket]);

  useEffect(() => {
    if (!recentTicket || hasUsableSubject(recentTicket)) return undefined;
    const timer = setTimeout(() => {
      fetchRecentTicket();
    }, 1200);
    return () => clearTimeout(timer);
  }, [recentTicket, hasUsableSubject, fetchRecentTicket]);

  const handleTicketSubmitted = async () => {
    setTicketLoading(true);
    await fetchRecentTicket();
  };

  useEffect(() => {
    async function fetchNotifications() {
      try {
        const token = getToken();
        const res = await fetch(apiUrl("/api/customer/notifications"), {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setNotifications(data.notifications || []);
        } else {
          setNotifications([]);
        }
      } catch {
        setNotifications([]);
      }
    }
    fetchNotifications();
  }, []);

  const initialsFromEmail = useMemo(
    () => getInitialsFromEmail(user?.email, "U"),
    [user]
  );

  const firstName = useMemo(() => {
    const email = (user?.email || "").trim();
    const name = user?.name || user?.full_name || user?.fullName || "";
    if (name) return name.split(" ")[0];
    if (!email.includes("@")) return "there";
    const raw = email.split("@")[0].replace(/[._\-\d]+/g, " ").trim();
    if (!raw) return "there";
    return raw.split(" ")[0].charAt(0).toUpperCase() + raw.split(" ")[0].slice(1);
  }, [user]);

  const greeting = useMemo(() => {
    const h = new Date().getHours();
    if (h < 12) return "Good morning";
    if (h < 17) return "Good afternoon";
    return "Good evening";
  }, []);

  const unreadCount = useMemo(
    () => (Array.isArray(notifications) ? notifications.filter((n) => !n.read).length : 0),
    [notifications]
  );

  const closeAllPopovers = () => {
    setProfileMenuOpen(false);
    setNotifOpen(false);
  };

  useEffect(() => {
    const onMouseDown = (e) => {
      const t = e.target;
      if (profileRef.current && !profileRef.current.contains(t)) setProfileMenuOpen(false);
      if (notifRef.current && !notifRef.current.contains(t)) setNotifOpen(false);
    };
    const onKeyDown = (e) => { if (e.key === "Escape") closeAllPopovers(); };
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, []);

  useEffect(() => {
    if (!isOpen || novaView !== "chat") return;
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, isOpen, isExpanded, novaView, listRef]);

  // ── Nova widget handlers ───────────────────────────────────────────────
  const handleClose = () => setShowCloseConfirm(true);
  const confirmClose = () => {
    setShowCloseConfirm(false);
    setNovaView("chat");
    setIsOpen(false);
    setIsExpanded(false);
  };
  const toggleExpand = () => {
    setIsExpanded((prev) => { if (prev) setNovaView("chat"); return !prev; });
  };
  const minimizeWidget = () => { setIsOpen(false); setIsExpanded(false); };

  // ── Fill Form widget handlers ──────────────────────────────────────────
  const openFormWidget = () => {
    closeAllPopovers();
    setFormOpen(true);
  };
  const handleFormClose = () => setShowFormCloseConfirm(true);
  const confirmFormClose = () => {
    setShowFormCloseConfirm(false);
    setFormOpen(false);
    setFormExpanded(false);
  };
  const toggleFormExpand = () => setFormExpanded((prev) => !prev);
  const minimizeFormWidget = () => { setFormOpen(false); setFormExpanded(false); };

  const openSettings = () => { closeAllPopovers(); navigate("/customer/settings"); };
  const handleLogout = () => { closeAllPopovers(); setShowLogoutConfirm(true); };
  const confirmLogout = () => {
    resetSession();
    setIsOpen(false);
    setIsExpanded(false);
    setNovaView("chat");
    localStorage.removeItem("user");
    localStorage.removeItem("token");
    localStorage.removeItem("temp_token");
    localStorage.removeItem("access_token");
    navigate("/");
  };

  const toggleNotifications = async () => {
    setProfileMenuOpen(false);
    setNotifOpen((prev) => !prev);
    if (!notifOpen) {
      try {
        const token = getToken();
        const res = await fetch(apiUrl("/api/customer/notifications?mark_read=true"), {
          method: "GET",
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
      } catch (err) {
        console.error("Error marking notifications as read:", err);
      }
    }
  };

  const handleQuickAction = (action) => {
    closeAllPopovers();
    if (action === "nova")          setIsOpen(true);
    else if (action === "tickets")  navigate("/customer/mytickets");
    else if (action === "form")     openFormWidget();
  };

  const formatTimeAgo = (isoString) => {
    if (!isoString) return "";
    const now = new Date();
    const date = new Date(isoString);
    const diff = Math.floor((now - date) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
    return date.toLocaleDateString();
  };

  // ── Voice input for Nova ───────────────────────────────────────────────
  const speechRef = useRef(null);
  const [voiceActive, setVoiceActive] = useState(false);
  const [voiceDraft, setVoiceDraft] = useState("");
  const [voiceBusy, setVoiceBusy] = useState(false);

  const startVoice = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) { alert("Voice input isn't supported in this browser. Try Chrome."); return; }
    setVoiceDraft(""); setVoiceBusy(false); setVoiceActive(true);
    const rec = new SR();
    rec.lang = "en-US"; rec.interimResults = true; rec.continuous = false;
    rec.onresult = (event) => {
      let interim = "", finalText = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const chunk = event.results[i][0]?.transcript || "";
        if (event.results[i].isFinal) finalText += chunk; else interim += chunk;
      }
      setVoiceDraft((finalText || interim || "").trim());
    };
    rec.onerror = () => { setVoiceActive(false); setVoiceBusy(false); };
    rec.onend = () => { setVoiceBusy(false); };
    speechRef.current = rec;
    try { rec.start(); } catch (err) { console.debug(err); }
  };
  const cancelVoice = () => {
    try { speechRef.current?.stop?.(); } catch { /* ignore */ }
    setVoiceActive(false); setVoiceBusy(false); setVoiceDraft("");
  };
  const confirmVoice = () => {
    const t = (voiceDraft || "").trim();
    if (!t) { cancelVoice(); return; }
    setText((prev) => (prev ? `${prev} ${t}` : t));
    cancelVoice();
  };

  return (
    <div className="cl-dashboard pl-root">

      {/* ─── TOPBAR ────────────────────────────────────────────── */}
      <header className="cl-topbar">
        <div className="cl-topbar-left">
          <img src={novaLogo} alt="InnovaAI" className="cl-topbar-logo" />
          <div className="cl-topbar-divider" />
          {/* Removed "Dubai CommerCity" — replaced with InnovaAI */}
          <span className="cl-topbar-portal">Customer Portal</span>
        </div>

        <div className="cl-topbar-right">
          {/* Light / Dark Mode Toggle */}
          <ThemeToggleBtn theme={theme} onToggle={toggleTheme} />

          {/* Notifications */}
          <div className="navAction" ref={notifRef}>
            <button
              type="button"
              className={`cl-icon-btn ${notifOpen ? "is-active" : ""}`}
              aria-label="Notifications"
              onClick={toggleNotifications}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
                <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
              </svg>
              {unreadCount > 0 && (
                <span className="notifBadge" aria-label={`${unreadCount} notifications`}>
                  {unreadCount}
                </span>
              )}
            </button>

            {notifOpen && (
              <div className="navPopover" role="menu" aria-label="Notifications">
                <div className="navPopoverHeader">Notifications</div>
                <div className="navPopoverList">
                  {notifications.length === 0 ? (
                    <div className="navPopoverEmpty">No notifications yet</div>
                  ) : (
                    notifications.map((n) => (
                      <div key={n.id} className={`navPopoverItem ${n.read ? "" : "unread"}`}>
                        <div className="navPopoverItemHeader">
                          <div className="navPopoverItemTitle">{n.title || n.type || "Notification"}</div>
                          {n.createdAt && <div className="navPopoverItemTime">{formatTimeAgo(n.createdAt)}</div>}
                        </div>
                        <div className="navPopoverItemMeta">{n.message || ""}</div>
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
              className={`cl-avatar-btn ${profileMenuOpen ? "is-active" : ""}`}
              aria-label="Profile menu"
              onClick={() => { setNotifOpen(false); setProfileMenuOpen((v) => !v); }}
            >
              <span className="cl-avatar-initials">{initialsFromEmail}</span>
              <span className="cl-avatar-name">{firstName}</span>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round">
                <path d="M6 9l6 6 6-6"/>
              </svg>
            </button>

            {profileMenuOpen && (
              <div className="navDropdown" role="menu" aria-label="Profile">
                <button type="button" className="navDropdownItem" onClick={openSettings}>Settings</button>
                <div className="navDropdownDivider" />
                <button type="button" className="navDropdownItem danger" onClick={handleLogout}>Log out</button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* ─── MAIN ──────────────────────────────────────────────── */}
      <main className="cl-main">

        {/* GREETING HERO — bigger headline */}
        <section className="cl-greeting-section">
          <div className="cl-greeting-bg" aria-hidden="true">
            <div className="cl-greeting-neb cl-greeting-neb1" />
            <div className="cl-greeting-neb cl-greeting-neb2" />
          </div>

          <div className="cl-greeting-content">
            <div className="cl-greeting-eyebrow">
              <span className="cl-live-dot" />
              InnovaAI · Customer Portal
            </div>
            {/* Bigger greeting text */}
            <h1 className="cl-greeting-headline">
              {greeting},<br />
              <span className="cl-greeting-name">{firstName}.</span>
            </h1>
            <p className="cl-greeting-sub">
              Welcome back to your InnovaAI dashboard. How can we help you today?
            </p>
            {/* Removed small My Tickets + Chat with Nova buttons per request */}
          </div>

          <div className="cl-greeting-badge">
            <div className="cl-greeting-badge-inner">
              <span className="cl-greeting-badge-icon">✦</span>
              <span>Nova AI is online</span>
            </div>
          </div>
        </section>

        {/* QUICK ACTIONS */}
        <section className="cl-section">
          <div className="cl-section-header">
            <div>
              <h2 className="cl-section-title">Quick Actions</h2>
              <p className="cl-section-sub">Everything you need, one tap away</p>
            </div>
          </div>
          <div className="cl-quick-grid">
            {QUICK_ACTIONS.map((q) => (
              <button
                key={q.action}
                type="button"
                className="cl-quick-card"
                style={{ "--qc": q.accent }}
                onClick={() => handleQuickAction(q.action)}
              >
                <div className="cl-quick-card-glow" />
                <div className="cl-quick-icon">{q.icon}</div>
                <div className="cl-quick-body">
                  <div className="cl-quick-title">{q.title}</div>
                  <div className="cl-quick-desc">{q.desc}</div>
                </div>
                <div className="cl-quick-footer">
                  <svg className="cl-quick-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 12h14M13 6l6 6-6 6"/>
                  </svg>
                </div>
              </button>
            ))}
          </div>
        </section>

        {/* RECENT TICKET */}
        <section className="cl-section cl-section--ticket">
          <div className="cl-section-header">
            <div>
              <h2 className="cl-section-title">Most Recent Ticket</h2>
              <p className="cl-section-sub">Latest activity on your account</p>
            </div>
            <button type="button" className="cl-view-all-btn" onClick={() => navigate("/customer/mytickets")}>
              View all
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
            </button>
          </div>

          {ticketLoading ? (
            <div className="cl-ticket-skeleton">
              <div className="cl-skeleton-line cl-skeleton-line--wide" />
              <div className="cl-skeleton-line cl-skeleton-line--med" />
              <div className="cl-skeleton-line cl-skeleton-line--narrow" />
            </div>
          ) : !recentTicket ? (
            <div className="cl-ticket-empty">
              <div className="cl-ticket-empty-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M2 9a1 1 0 0 1 1-1h18a1 1 0 0 1 1 1v1.5a1.5 1.5 0 0 0 0 3V15a1 1 0 0 1-1 1H3a1 1 0 0 1-1-1v-1.5a1.5 1.5 0 0 0 0-3V9z"/>
                  <path d="M9 12h6M9 15h4"/>
                </svg>
              </div>
              <p className="cl-ticket-empty-title">No tickets yet</p>
              <p className="cl-ticket-empty-sub">Your submitted tickets will appear here.</p>
              <button className="cl-btn-primary" style={{ marginTop: "16px" }} onClick={openFormWidget}>
                Submit your first ticket
              </button>
            </div>
          ) : (
            <div
              className="cl-ticket-card"
              onClick={() => navigate(`/customer/ticket/${recentTicket.ticketId}`)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") navigate(`/customer/ticket/${recentTicket.ticketId}`); }}
            >
              <div className="cl-ticket-toprow">
                <span className="cl-ticket-id">{recentTicket.ticketId}</span>
                <span className="cl-ticket-dot">·</span>
                <span className="cl-ticket-type">{recentTicket.ticketType || recentTicket.type}</span>
                <span className="cl-ticket-dot">·</span>
                <span className={`cl-ticket-status cl-status--${(recentTicket.status || "").toLowerCase().replace(/\s+/g, "")}`}>
                  <span className="cl-status-dot" />
                  {recentTicket.status}
                </span>
                <span className="cl-ticket-dot cl-ticket-dot--spacer" />
                <span className="cl-ticket-priority">{recentTicket.priority}</span>
              </div>

              <h3 className="cl-ticket-subject">{recentTicket.subject || recentTicket.description?.subject}</h3>

              {recentTicket.updates && recentTicket.updates.length > 0 ? (
                <div className="cl-updates-feed">
                  <div className="cl-updates-label">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
                    Activity
                  </div>
                  <div className="cl-updates-list">
                    {recentTicket.updates.slice(-3).reverse().map((u, i) => {
                      const typeMap = {
                        system: { dot: "#a855f7", tag: "AI" },
                        status_change: { dot: "#4ade80", tag: "Status" },
                        priority_change: { dot: "#fb923c", tag: "Priority" },
                      };
                      const tone = typeMap[u.type] || { dot: "rgba(147,51,234,.5)", tag: "Update" };
                      return (
                        <div key={i} className="cl-update-row">
                          <span className="cl-update-dot" style={{ background: tone.dot }} />
                          <span className="cl-update-tag" style={{ color: tone.dot }}>{tone.tag}</span>
                          <span className="cl-update-msg">{u.message || u.text}</span>
                          {u.date && <span className="cl-update-time">{formatTimeAgo(u.date)}</span>}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : (
                <div className="cl-updates-feed cl-updates-feed--empty">
                  <span className="cl-updates-label">
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
                    No activity yet — our team is reviewing your ticket.
                  </span>
                </div>
              )}

              <div className="cl-ticket-footer">
                <span className="cl-ticket-date">Submitted {recentTicket.issueDate || recentTicket.date}</span>
                <span className="cl-ticket-cta">
                  View full details
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M5 12h14M13 6l6 6-6 6"/></svg>
                </span>
              </div>
            </div>
          )}
        </section>
      </main>

      {/* ─── FOOTER ────────────────────────────────────────────── */}
      <footer className="cl-footer">
        <img src={novaLogo} alt="InnovaAI" className="cl-footer-logo" />
        <div className="cl-footer-links">
          <button className="cl-footer-link" onClick={() => navigate("/customer/mytickets")}>My Tickets</button>
          <button className="cl-footer-link" onClick={() => navigate("/customer/settings")}>Settings</button>
        </div>
        {/* Removed Dubai CommerCity */}
        <p className="cl-footer-copy">© 2026 InnovaAI</p>
      </footer>

      {/* ─── NOVA CHAT WIDGET ──────────────────────────────────── */}
      {isOpen && (
        <div className={`novaWidget ${isExpanded ? "expanded" : ""} open`}>
          <div className="novaWidgetHeader">
            <div className="novaWidgetHeaderLeft">
              <div className="novaAvatar" />
              <div>
                <div className="novaHeaderTitle">Nova</div>
                <div className="novaHeaderSub">AI Support Assistant</div>
              </div>
            </div>
            <div className="novaWidgetHeaderRight">
              <button type="button" className="novaIconBtn" onClick={toggleExpand} aria-label={isExpanded ? "Exit fullscreen" : "Fullscreen"}>
                {isExpanded ? (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M9 3H3v6M15 3h6v6M21 15v6h-6M3 15v6h6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M14 3h7v7M10 21H3v-7M21 3l-7 7M3 21l7-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>
                )}
              </button>
              <button type="button" className="novaIconBtn" onClick={minimizeWidget} aria-label="Minimize">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M6 11H18V13H6V11Z" fill="currentColor"/></svg>
              </button>
              <button type="button" className="novaIconBtn" onClick={handleClose} aria-label="Close">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg>
              </button>
            </div>
          </div>

          <div className={`novaWidgetBody ${novaView === "form" ? "novaWidgetBody--form" : ""}`}>
            {novaView === "form" ? (
              <div className="novaFormHost">
                <CustomerFillForm
                  embedded
                  initialType={embeddedFormType}
                  onCancel={() => setNovaView("chat")}
                  onSubmitted={handleTicketSubmitted}
                />
              </div>
            ) : (
              <>
                <div className="novaChatList" ref={listRef}>
                  {messages.map((m) => (
                    <div key={m.id} className={`novaMsg ${m.from === "user" ? "novaMsg--user" : "novaMsg--bot"}`}>
                      <div className="novaBubble">
                        {m.typing ? (
                          <div className="novaTyping"><span /><span /><span /></div>
                        ) : m.text}
                      </div>
                      {!m.typing && m.buttons?.length > 0 && (
                        <div className="novaQuickRow">
                          {m.buttons.map((btn) => (
                            <button
                              key={btn}
                              onClick={() =>
                                handleSend(
                                  btn === "create_ticket"
                                    ? "I want to create a ticket"
                                    : btn === "track_ticket"
                                    ? "I want to track a ticket"
                                    : btn
                                )
                              }
                            >
                              {btn === "create_ticket"
                                ? "Create a ticket"
                                : btn === "track_ticket"
                                ? "Track a ticket"
                                : btn}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>

                <div className="novaComposerWrap">
                  {voiceActive && (
                    <div className="novaVoiceBar">
                      <div className="novaVoiceLeft">
                        <div className="novaVoiceText">
                          {voiceBusy ? "Transcribing…" : voiceDraft.trim() ? "Review & insert" : "Listening…"}
                        </div>
                        <div className="novaWaves" aria-hidden="true">
                          <span className="novaWave"/><span className="novaWave"/><span className="novaWave"/><span className="novaWave"/><span className="novaWave"/>
                        </div>
                      </div>
                      <div className="novaVoiceActions">
                        <button type="button" className="novaVoiceIconBtn" onClick={cancelVoice} disabled={voiceBusy} aria-label="Cancel">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/></svg>
                        </button>
                        <button type="button" className="novaVoiceIconBtn confirm" onClick={confirmVoice} disabled={voiceBusy} aria-label="Insert">
                          <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M20 6L9 17l-5-5" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"/></svg>
                        </button>
                      </div>
                    </div>
                  )}
                  <form className="novaComposer" onSubmit={(e) => { e.preventDefault(); handleSend(text); setText(""); }}>
                    <button type="button" className={`novaMicBtn ${voiceActive ? "active" : ""}`} onClick={() => voiceActive ? cancelVoice() : startVoice()} aria-label="Voice">
                      <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                        <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3Z" fill="currentColor" opacity=".95"/>
                        <path d="M19 11a7 7 0 0 1-14 0" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
                        <path d="M12 18v3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
                      </svg>
                    </button>
                    <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Type a message…"/>
                    <button type="submit">Send</button>
                  </form>
                </div>
              </>
            )}
          </div>

          {showCloseConfirm && (
            <div className="novaCloseModal">
              <div className="novaCloseModalContent">
                <p>Are you sure you want to close the chat?</p>
                <div className="novaCloseModalBtns">
                  <button onClick={confirmClose}>Yes, close</button>
                  <button onClick={() => setShowCloseConfirm(false)}>Keep chatting</button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ─── FILL FORM WIDGET (same style as Nova, opens bottom-right) ── */}
      {formOpen && (
        <div
          className={`novaWidget ${formExpanded ? "expanded" : ""} open`}
          style={!formExpanded && isOpen ? { right: "558px" } : {}}
        >
          {/* Header */}
          <div className="novaWidgetHeader">
            <div className="novaWidgetHeaderLeft">
              <div className="novaAvatar" style={{ background: "linear-gradient(135deg,rgba(232,121,249,.4),rgba(109,40,217,.6))" }}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ color: "rgba(255,255,255,.85)" }}>
                  <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                  <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                </svg>
              </div>
              <div>
                <div className="novaHeaderTitle">Fill a Form</div>
                <div className="novaHeaderSub">Submit a new request</div>
              </div>
            </div>
            <div className="novaWidgetHeaderRight">
              <button type="button" className="novaIconBtn" onClick={toggleFormExpand} aria-label={formExpanded ? "Exit fullscreen" : "Fullscreen"}>
                {formExpanded ? (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M9 3H3v6M15 3h6v6M21 15v6h-6M3 15v6h6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>
                ) : (
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M14 3h7v7M10 21H3v-7M21 3l-7 7M3 21l7-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/></svg>
                )}
              </button>
              <button type="button" className="novaIconBtn" onClick={minimizeFormWidget} aria-label="Minimize">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M6 11H18V13H6V11Z" fill="currentColor"/></svg>
              </button>
              <button type="button" className="novaIconBtn" onClick={handleFormClose} aria-label="Close">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/></svg>
              </button>
            </div>
          </div>

          {/* Body */}
          <div className="novaWidgetBody novaWidgetBody--form">
            <div className="novaFormHost">
              <CustomerFillForm
                embedded
                initialType="Complaint"
                onCancel={confirmFormClose}
                onSubmitted={handleTicketSubmitted}
              />
            </div>
          </div>

          {showFormCloseConfirm && (
            <div className="novaCloseModal">
              <div className="novaCloseModalContent">
                <p>Close the form? Your progress will be lost.</p>
                <div className="novaCloseModalBtns">
                  <button onClick={confirmFormClose}>Yes, close</button>
                  <button onClick={() => setShowFormCloseConfirm(false)}>Keep editing</button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ─── LOGOUT CONFIRM ────────────────────────────────────── */}
      {showLogoutConfirm && (
        <div className="novaCloseModal">
          <div className="novaCloseModalContent">
            <p>Are you sure you want to log out?</p>
            <div className="novaCloseModalBtns">
              <button onClick={confirmLogout}>Log out</button>
              <button onClick={() => setShowLogoutConfirm(false)}>Cancel</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
