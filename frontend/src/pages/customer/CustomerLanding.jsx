import React, { useMemo, useRef, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "../PublicLanding.css";
import "./CustomerLanding.css";
import novaLogo from "../../assets/nova-logo.png";
import CustomerFillForm from "./CustomerFillForm";
import useNovaChatbot from "./chatbot.js";
import { apiUrl } from "../../config/apiBase";
import { getInitialsFromEmail } from "../../utils/userDisplay";
import { getToken, getUser } from "../../utils/auth";

const QUICK_ACTIONS = [
  {
    icon: "✦",
    title: "Chat with Nova",
    desc: "Get instant help from our AI assistant",
    action: "nova",
    accent: "#c084fc",
  },
  {
    icon: "📋",
    title: "My Tickets",
    desc: "View and track all your submitted tickets",
    action: "tickets",
    accent: "#818cf8",
  },
  {
    icon: "✏️",
    title: "Create a Ticket",
    desc: "File a new complaint or inquiry",
    action: "form",
    accent: "#e879f9",
  },
  {
    icon: "⚙️",
    title: "Settings",
    desc: "Manage your account preferences",
    action: "settings",
    accent: "#a855f7",
  },
];



export default function CustomerLanding() {
  const navigate = useNavigate();

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

  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [showCloseConfirm, setShowCloseConfirm] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);

  const [novaView, setNovaView] = useState("chat");

  const [user] = useState(() => getUser() || {});
  const [notifications, setNotifications] = useState([]);
  const [recentTicket, setRecentTicket] = useState(null);
  const [ticketLoading, setTicketLoading] = useState(true);

  useEffect(() => {
    async function fetchRecentTicket() {
      try {
        const token = getToken();
        const res = await fetch(apiUrl("/api/customer/mytickets"), {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          const tickets = data.tickets || [];
          // Most recently updated ticket
          const sorted = [...tickets].sort((a, b) =>
            new Date(b.updatedAt || b.issueDate) - new Date(a.updatedAt || a.issueDate)
          );
          setRecentTicket(sorted[0] || null);
        }
      } catch {
        setRecentTicket(null);
      } finally {
        setTicketLoading(false);
      }
    }
    fetchRecentTicket();
  }, []);

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

  // Derive a friendly first name from email
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
    () =>
      Array.isArray(notifications)
        ? notifications.filter((n) => !n.read).length
        : 0,
    [notifications]
  );

  const closeAllPopovers = () => {
    setProfileMenuOpen(false);
    setNotifOpen(false);
  };

  useEffect(() => {
    const onMouseDown = (e) => {
      const t = e.target;
      if (profileRef.current && !profileRef.current.contains(t))
        setProfileMenuOpen(false);
      if (notifRef.current && !notifRef.current.contains(t))
        setNotifOpen(false);
    };
    const onKeyDown = (e) => {
      if (e.key === "Escape") closeAllPopovers();
    };
    document.addEventListener("mousedown", onMouseDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onMouseDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [listRef]);

  useEffect(() => {
    if (!isOpen) return;
    if (novaView !== "chat") return;
    if (listRef.current)
      listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, isOpen, isExpanded, novaView, listRef]);

  const handleClose = () => setShowCloseConfirm(true);

  const confirmClose = () => {
    setShowCloseConfirm(false);
    setNovaView("chat");
    setIsOpen(false);
    setIsExpanded(false);
  };

  const openSettings = () => {
    closeAllPopovers();
    navigate("/customer/settings");
  };

  const handleLogout = () => {
    closeAllPopovers();
    setShowLogoutConfirm(true);
  };

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
        const res = await fetch(
          apiUrl("/api/customer/notifications?mark_read=true"),
          { method: "GET", headers: { Authorization: `Bearer ${token}` } }
        );
        if (res.ok) {
          setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
        }
      } catch (err) {
        console.error("Error marking notifications as read:", err);
      }
    }
  };

  const handleQuickAction = (action) => {
    closeAllPopovers();
    if (action === "nova") { setIsOpen(true); }
    else if (action === "tickets") { navigate("/customer/mytickets"); }
    else if (action === "form") { navigate("/customer/fill-form"); }
    else if (action === "settings") { navigate("/customer/settings"); }
  };

  const toggleFormInChat = () => {
    closeAllPopovers();
    if (!isOpen) setIsOpen(true);
    setNovaView((prev) => {
      const next = prev === "form" ? "chat" : "form";
      if (next === "form") resetSession();
      return next;
    });
  };

  const toggleExpand = () => {
    setIsExpanded((prev) => {
      const next = !prev;
      if (!next) setNovaView("chat");
      return next;
    });
  };

  const minimizeWidget = () => {
    setIsOpen(false);
    setIsExpanded(false);
  };

  const speechRef = useRef(null);
  const [voiceActive, setVoiceActive] = useState(false);
  const [voiceDraft, setVoiceDraft] = useState("");
  const [voiceBusy, setVoiceBusy] = useState(false);

  const getSpeechRecognition = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SR) return null;
    return SR;
  };

  const startVoice = () => {
    const SR = getSpeechRecognition();
    if (!SR) { alert("Voice input isn't supported in this browser. Try Chrome."); return; }
    setVoiceDraft("");
    setVoiceBusy(false);
    setVoiceActive(true);
    const rec = new SR();
    rec.lang = "en-US";
    rec.interimResults = true;
    rec.continuous = false;
    rec.onresult = (event) => {
      let interim = "", finalText = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const chunk = event.results[i][0]?.transcript || "";
        if (event.results[i].isFinal) finalText += chunk;
        else interim += chunk;
      }
      setVoiceDraft((finalText || interim || "").trim());
    };
    rec.onerror = () => { setVoiceActive(false); setVoiceBusy(false); };
    rec.onend = () => {
      setVoiceBusy(false);
      setTimeout(() => {
        setVoiceActive((prev) => {
          if (!voiceDraft.trim()) return false;
          return prev;
        });
      }, 0);
    };
    speechRef.current = rec;
    try { rec.start(); } catch (err) { console.debug("Speech recognition failed to start:", err); }
  };

  const cancelVoice = () => {
    try { speechRef.current?.stop?.(); } catch (err) { console.debug(err); }
    setVoiceActive(false);
    setVoiceBusy(false);
    setVoiceDraft("");
  };

  const confirmVoice = () => {
    const t = (voiceDraft || "").trim();
    if (!t) { cancelVoice(); return; }
    setText((prev) => (prev ? `${prev} ${t}` : t));
    cancelVoice();
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

  return (
    <div className="cl-dashboard pl-root">

      {/* ─── TOPBAR ────────────────────────────────────────────── */}
      <header className="cl-topbar">
        <div className="cl-topbar-left">
          <img src={novaLogo} alt="InnovaCX" className="cl-topbar-logo" />
          <div className="cl-topbar-divider" />
          <span className="cl-topbar-portal">Customer Portal</span>
        </div>

        <div className="cl-topbar-right">
          {/* Notifications */}
          <div className="navAction" ref={notifRef}>
            <button
              type="button"
              className={`cl-icon-btn ${notifOpen ? "is-active" : ""}`}
              aria-label="Notifications"
              onClick={toggleNotifications}
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                <path d="M13.73 21a2 2 0 0 1-3.46 0" />
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
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
                <path d="M6 9l6 6 6-6" />
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

      {/* ─── MAIN CONTENT ──────────────────────────────────────── */}
      <main className="cl-main">

        {/* GREETING HERO */}
        <section className="cl-greeting-section">
          <div className="cl-greeting-bg" aria-hidden="true">
            <div className="cl-greeting-neb cl-greeting-neb1" />
            <div className="cl-greeting-neb cl-greeting-neb2" />
          </div>

          <div className="cl-greeting-content">
            <div className="cl-greeting-eyebrow">
              <span className="cl-live-dot" />
              Dubai CommerCity · Customer Portal
            </div>
            <h1 className="cl-greeting-headline">
              {greeting},<br />
              <span className="cl-greeting-name">{firstName}.</span>
            </h1>
            <p className="cl-greeting-sub">
              Welcome back to your InnovaCX dashboard. How can we help you today?
            </p>

            <div className="cl-greeting-actions">
              <button
                className="cl-btn-primary"
                onClick={() => navigate("/customer/mytickets")}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/><rect x="9" y="3" width="6" height="4" rx="1"/></svg>
                My Tickets
              </button>
              <button
                className="cl-btn-ghost"
                onClick={() => setIsOpen(true)}
              >
                <span className="cl-nova-dot-sm" />
                Chat with Nova
              </button>
            </div>
          </div>

          <div className="cl-greeting-badge">
            <div className="cl-greeting-badge-inner">
              <span className="cl-greeting-badge-icon">✦</span>
              <span className="cl-greeting-badge-text">Nova AI is online</span>
            </div>
          </div>
        </section>

        {/* QUICK ACTIONS */}
        <section className="cl-section">
          <div className="cl-section-header">
            <h2 className="cl-section-title">Quick Actions</h2>
            <p className="cl-section-sub">Everything you need, one tap away</p>
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
                  <svg className="cl-quick-arrow" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                    <path d="M5 12h14M13 6l6 6-6 6" />
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
            <button
              type="button"
              className="cl-view-all-btn"
              onClick={() => navigate("/customer/mytickets")}
            >
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
              <div className="cl-ticket-empty-icon">🎫</div>
              <p className="cl-ticket-empty-title">No tickets yet</p>
              <p className="cl-ticket-empty-sub">Your submitted tickets will appear here.</p>
              <button className="cl-btn-primary" style={{marginTop: "16px"}} onClick={() => navigate("/customer/fill-form")}>
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
              {/* Top row: ID · type · status */}
              <div className="cl-ticket-toprow">
                <span className="cl-ticket-id">{recentTicket.ticketId}</span>
                <span className="cl-ticket-dot">·</span>
                <span className="cl-ticket-type">{recentTicket.ticketType || recentTicket.type}</span>
                <span className="cl-ticket-dot">·</span>
                <span className={`cl-ticket-status cl-status--${(recentTicket.status || "").toLowerCase().replace(/\s+/g,"")}`}>
                  <span className="cl-status-dot" />
                  {recentTicket.status}
                </span>
                <span className="cl-ticket-dot cl-ticket-dot--spacer">·</span>
                <span className="cl-ticket-priority cl-priority--${(recentTicket.priority||'medium').toLowerCase()}">
                  {recentTicket.priority}
                </span>
              </div>

              {/* Subject */}
              <h3 className="cl-ticket-subject">{recentTicket.subject || recentTicket.description?.subject || "Untitled ticket"}</h3>

              {/* Updates feed */}
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
                      const tone = typeMap[u.type] || { dot: "rgba(255,255,255,.25)", tag: "Update" };
                      return (
                        <div key={i} className="cl-update-row">
                          <span className="cl-update-dot" style={{ background: tone.dot }} />
                          <span className="cl-update-tag" style={{ color: tone.dot }}>{tone.tag}</span>
                          <span className="cl-update-msg">{u.message || u.text}</span>
                          {u.date && (
                            <span className="cl-update-time">{formatTimeAgo(u.date)}</span>
                          )}
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

              {/* Footer */}
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
        <img src={novaLogo} alt="InnovaCX" className="cl-footer-logo" />
        <div className="cl-footer-links">
          <button className="cl-footer-link" onClick={() => navigate("/customer/mytickets")}>My Tickets</button>
          <button className="cl-footer-link" onClick={() => navigate("/customer/settings")}>Settings</button>
        </div>
        <p className="cl-footer-copy">© 2026 Dubai CommerCity · InnovaCX</p>
      </footer>

      {/* ─── NOVA WIDGET ───────────────────────────────────────── */}
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
              <button type="button" className={`novaTextBtn ${novaView === "form" ? "active" : ""}`} onClick={toggleFormInChat}>
                Fill a form
              </button>
              <button type="button" className="novaIconBtn" onClick={toggleExpand} aria-label={isExpanded ? "Exit fullscreen" : "Enter fullscreen"}>
                {isExpanded ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                    <path d="M9 3H3v6M15 3h6v6M21 15v6h-6M3 15v6h6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                    <path d="M14 3h7v7M10 21H3v-7M21 3l-7 7M3 21l7-7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                )}
              </button>
              <button type="button" className="novaIconBtn" onClick={minimizeWidget} aria-label="Minimize">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M6 11H18V13H6V11Z" fill="currentColor" /></svg>
              </button>
              <button type="button" className="novaIconBtn" onClick={handleClose} aria-label="Close">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
              </button>
            </div>
          </div>

          <div className={`novaWidgetBody ${novaView === "form" ? "novaWidgetBody--form" : ""}`}>
            {novaView === "form" ? (
              <div className="novaFormHost">
                <CustomerFillForm embedded initialType={embeddedFormType} onCancel={() => setNovaView("chat")} />
              </div>
            ) : (
              <>
                <div className="novaChatList" ref={listRef}>
                  {messages.map((m) => (
                    <div key={m.id} className={`novaMsg ${m.from === "user" ? "novaMsg--user" : "novaMsg--bot"}`}>
                      <div className="novaBubble">
                        {m.typing ? (
                          <div className="novaTyping"><span /><span /><span /></div>
                        ) : (
                          m.text
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                <div className="novaComposerWrap">
                  {voiceActive && (
                    <div className={`novaVoiceBar ${voiceBusy ? "isBusy" : ""}`}>
                      <div className="novaVoiceLeft">
                        <div className="novaVoiceText">
                          {voiceBusy ? "Transcribing…" : voiceDraft.trim() ? "Review & insert" : "Listening…"}
                        </div>
                        <div className="novaWaves" aria-hidden="true">
                          <span className="novaWave" /><span className="novaWave" /><span className="novaWave" /><span className="novaWave" /><span className="novaWave" />
                        </div>
                      </div>
                      <div className="novaVoiceActions">
                        <button type="button" className="novaVoiceIconBtn cancel" onClick={cancelVoice} aria-label="Cancel recording" disabled={voiceBusy}>
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /></svg>
                        </button>
                        <button type="button" className="novaVoiceIconBtn confirm" onClick={confirmVoice} aria-label="Insert transcript" disabled={voiceBusy}>
                          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M20 6L9 17l-5-5" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" /></svg>
                        </button>
                      </div>
                    </div>
                  )}

                  <form className="novaComposer" onSubmit={(e) => { e.preventDefault(); handleSend(text); setText(""); }}>
                    <button type="button" className={`novaMicBtn ${voiceActive ? "active" : ""}`} aria-label="Voice input" onClick={() => { if (voiceActive) cancelVoice(); else startVoice(); }}>
                      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                        <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3Z" fill="currentColor" opacity="0.95" />
                        <path d="M19 11a7 7 0 0 1-14 0" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                        <path d="M12 18v3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                      </svg>
                    </button>
                    <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Type a message…" />
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