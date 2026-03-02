import React, { useMemo, useRef, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "../PublicLanding.css";
import "./CustomerLanding.css";
import novaLogo from "../../assets/nova-logo.png";
import dccBg from "../../assets/dcc-bg.png";
import CustomerFillForm from "./CustomerFillForm";
import useNovaChatbot from "./chatbot.js";
import { apiUrl } from "../../config/apiBase";
import { getInitialsFromEmail } from "../../utils/userDisplay";
import { getToken, getUser } from "../../utils/auth";

const FEATURES = [
  {
    icon: "🧠",
    title: "Sentiment Analysis",
    desc: "Our AI reads the emotional tone of every complaint in real time, ensuring the most distressed customers are never left waiting.",
  },
  {
    icon: "🎯",
    title: "Smart Prioritisation",
    desc: "Tickets are automatically ranked by urgency and customer value so your team always works on what matters most.",
  },
  {
    icon: "🎙️",
    title: "Audio Intelligence",
    desc: "Voice complaints are transcribed and analysed instantly — capturing nuance that text alone can miss.",
  },
  {
    icon: "⚡",
    title: "Instant Resolution",
    desc: "AI-suggested resolutions cut average handling time dramatically, freeing your team for complex cases.",
  },
];

const STATS = [
  { value: "40%", label: "Faster resolution" },
  { value: "3×", label: "Complaint throughput" },
  { value: "98%", label: "Triage accuracy" },
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
  const [showNewChatConfirm, setShowNewChatConfirm] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);

  const [novaView, setNovaView] = useState("chat");

  const [user] = useState(() => getUser() || {});
  const [notifications, setNotifications] = useState([]);

  // Fetch notifications from API
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

  const handleNewChat = () => setShowNewChatConfirm(true);

  const confirmNewChat = () => {
    setShowNewChatConfirm(false);
    setNovaView("chat");
    resetSession();
  };

  const openHistory = () => {
    closeAllPopovers();
    navigate("/customer/mytickets");
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
    navigate("/login");
  };

  const toggleNotifications = async () => {
    setProfileMenuOpen(false);
    setNotifOpen((prev) => {
      const next = !prev;
      return next;
    });

    if (!notifOpen) {
      try {
        const token = getToken();
        const res = await fetch(
          apiUrl("/api/customer/notifications?mark_read=true"),
          {
            method: "GET",
            headers: { Authorization: `Bearer ${token}` },
          }
        );
        if (res.ok) {
          setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
        } else {
          console.error("Failed to mark notifications as read");
        }
      } catch (err) {
        console.error("Error marking notifications as read:", err);
      }
    }
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
    if (!SR) {
      alert("Voice input isn't supported in this browser. Try Chrome.");
      return;
    }

    setVoiceDraft("");
    setVoiceBusy(false);
    setVoiceActive(true);

    const rec = new SR();
    rec.lang = "en-US";
    rec.interimResults = true;
    rec.continuous = false;

    rec.onresult = (event) => {
      let interim = "";
      let finalText = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const chunk = event.results[i][0]?.transcript || "";
        if (event.results[i].isFinal) finalText += chunk;
        else interim += chunk;
      }
      const merged = (finalText || interim || "").trim();
      setVoiceDraft(merged);
    };

    rec.onerror = () => {
      setVoiceActive(false);
      setVoiceBusy(false);
    };

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

    try {
      rec.start();
    } catch (err) {
      console.debug("Speech recognition failed to start:", err);
    }
  };

  const cancelVoice = () => {
    try {
      speechRef.current?.stop?.();
    } catch (err) {
      console.debug("Speech recognition stop failed:", err);
    }
    setVoiceActive(false);
    setVoiceBusy(false);
    setVoiceDraft("");
  };

  const confirmVoice = () => {
    const t = (voiceDraft || "").trim();
    if (!t) {
      cancelVoice();
      return;
    }
    setText((prev) => (prev ? `${prev} ${t}` : t));
    cancelVoice();
  };

  const formatTimeAgo = (isoString) => {
    if (!isoString) return "";
    const now = new Date();
    const date = new Date(isoString);
    const diff = Math.floor((now - date) / 1000);

    if (diff < 60) return `${diff} sec${diff !== 1 ? "s" : ""} ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    if (diff < 604800) return `${Math.floor(diff / 86400)}d ago`;
    return date.toLocaleDateString();
  };

  return (
    <div className="customer-landing-page pl-root">

      {/* ─── HERO ─────────────────────────────────────────────── */}
      <section
        className="pl-hero"
        style={{ backgroundImage: `url(${dccBg})` }}
      >
        <div className="pl-hero-overlay" />

        {/* NAV */}
        <nav className="pl-nav">
          <img src={novaLogo} alt="InnovaCX" className="pl-nav-logo" />

          <div className="pl-nav-links">
            <button
              className="pl-nav-link"
              onClick={() => navigate("/customer/about")}
            >
              About Us
            </button>
          </div>

          {/* Authenticated nav actions */}
          <div className="nav-actions">
            {/* Notifications bell */}
            <div className="navAction" ref={notifRef}>
              <button
                type="button"
                className={`navIconButton ${notifOpen ? "isOpen" : ""}`}
                aria-label="Notifications"
                onClick={toggleNotifications}
              >
                <svg
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                  <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                </svg>

                {unreadCount > 0 && (
                  <span
                    className="notifBadge"
                    aria-label={`${unreadCount} notifications`}
                  >
                    {unreadCount}
                  </span>
                )}
              </button>

              {notifOpen && (
                <div
                  className="navPopover"
                  role="menu"
                  aria-label="Notifications"
                >
                  <div className="navPopoverHeader">Notifications</div>
                  <div className="navPopoverList">
                    {notifications.length === 0 ? (
                      <div className="navPopoverEmpty">No notifications</div>
                    ) : (
                      notifications.map((n) => (
                        <div
                          key={n.id}
                          className={`navPopoverItem ${n.read ? "" : "unread"}`}
                        >
                          <div className="navPopoverItemHeader">
                            <div className="navPopoverItemTitle">
                              {n.title || n.type || "Notification"}
                            </div>
                            {n.createdAt && (
                              <div className="navPopoverItemTime">
                                {formatTimeAgo(n.createdAt)}
                              </div>
                            )}
                          </div>
                          <div className="navPopoverItemMeta">
                            {n.message || ""}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Profile avatar */}
            <div className="navAction" ref={profileRef}>
              <button
                type="button"
                className={`navIconButton navProfileButton ${profileMenuOpen ? "isOpen" : ""}`}
                aria-label="Profile menu"
                onClick={() => {
                  setNotifOpen(false);
                  setProfileMenuOpen((v) => !v);
                }}
              >
                <span className="navAvatarCircle" aria-hidden="true">
                  {initialsFromEmail}
                </span>
              </button>

              {profileMenuOpen && (
                <div className="navDropdown" role="menu" aria-label="Profile">
                  <button
                    type="button"
                    className="navDropdownItem"
                    onClick={openHistory}
                  >
                    My Tickets
                  </button>
                  <button
                    type="button"
                    className="navDropdownItem"
                    onClick={openSettings}
                  >
                    Settings
                  </button>
                  <div className="navDropdownDivider" />
                  <button
                    type="button"
                    className="navDropdownItem danger"
                    onClick={handleLogout}
                  >
                    Logout
                  </button>
                </div>
              )}
            </div>
          </div>
        </nav>

        {/* HERO CONTENT */}
        <div className="pl-hero-body">
          <div className="pl-hero-eyebrow">Dubai CommerCity · AI-Powered CX</div>

          <h1 className="pl-hero-headline">
            <span className="pl-word pl-word--1">Transforming</span>
            <span className="pl-word pl-word--2">Customer</span>
            <span className="pl-word pl-word--3">Experience</span>
          </h1>

          <p className="pl-hero-sub">
            InnovaCX uses sentiment analysis, audio intelligence, and machine
            learning to route and resolve complaints faster than ever — so every
            customer feels heard.
          </p>

          <div className="pl-hero-actions">
            <button
              className="pl-btn-primary"
              onClick={() => navigate("/customer/mytickets")}
            >
              My Tickets
            </button>
            <button
              className="pl-btn-ghost"
              onClick={() => navigate("/customer/about")}
            >
              Learn More
            </button>
          </div>

          {/* NOVA CTA */}
          <button
            className="pl-nova-pill"
            onClick={() => setIsOpen(true)}
            title="Chat with Nova AI"
          >
            <span className="pl-nova-dot" />
            <span>Chat with Nova AI</span>
            <span className="pl-nova-arrow">→</span>
          </button>
        </div>

        {/* FLOATING STATS */}
        <div className="pl-stats">
          {STATS.map((s, i) => (
            <div
              key={i}
              className="pl-stat"
              style={{ animationDelay: `${i * 0.15}s` }}
            >
              <span className="pl-stat-value">{s.value}</span>
              <span className="pl-stat-label">{s.label}</span>
            </div>
          ))}
        </div>

        {/* SCROLL HINT */}
        <div className="pl-scroll-hint">
          <span className="pl-scroll-line" />
          <span className="pl-scroll-text">Scroll</span>
        </div>
      </section>

      {/* ─── FEATURES ─────────────────────────────────────────── */}
      <section className="pl-features">
        <div className="pl-section-label">What We Do</div>
        <h2 className="pl-section-title">AI that works as hard as your team</h2>
        <p className="pl-section-sub">
          Four intelligent layers that ensure no complaint falls through the
          cracks.
        </p>

        <div className="pl-feature-grid">
          {FEATURES.map((f, i) => (
            <div
              key={i}
              className="pl-feature-card"
              style={{ animationDelay: `${i * 0.1}s` }}
            >
              <div className="pl-feature-icon">{f.icon}</div>
              <h3 className="pl-feature-title">{f.title}</h3>
              <p className="pl-feature-desc">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ─── CTA STRIP ────────────────────────────────────────── */}
      <section className="pl-cta-strip">
        <div className="pl-cta-inner">
          <h2 className="pl-cta-headline">Need help? We've got you.</h2>
          <p className="pl-cta-sub">
            Chat with Nova, submit a complaint, or track your existing tickets —
            all in one place.
          </p>
          <button
            className="pl-btn-primary pl-btn-large"
            onClick={() => setIsOpen(true)}
          >
            Chat with Nova
          </button>
        </div>
      </section>

      {/* ─── FOOTER ───────────────────────────────────────────── */}
      <footer className="pl-footer">
        <img src={novaLogo} alt="InnovaCX" className="pl-footer-logo" />
        <div className="pl-footer-links">
          <button
            className="pl-footer-link"
            onClick={() => navigate("/customer/about")}
          >
            About Us
          </button>
          <button
            className="pl-footer-link"
            onClick={() => navigate("/customer/mytickets")}
          >
            My Tickets
          </button>
          <button
            className="pl-footer-link"
            onClick={() => navigate("/customer/settings")}
          >
            Settings
          </button>
        </div>
        <p className="pl-footer-copy">© 2026 Dubai CommerCity · InnovaCX</p>
      </footer>

      {/* ─── NOVA WIDGET LAUNCHER ─────────────────────────────── */}
      {!isOpen && (
        <button className="novaWidgetLauncher" onClick={() => setIsOpen(true)}>
          <span className="novaWidgetDot" /> Chat with Nova
        </button>
      )}

      {/* ─── NOVA WIDGET ──────────────────────────────────────── */}
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
              <button
                type="button"
                className={`novaTextBtn ${novaView === "form" ? "active" : ""}`}
                onClick={toggleFormInChat}
              >
                Fill a form
              </button>
              <button
                type="button"
                className="novaTextBtn"
                onClick={handleNewChat}
              >
                New chat
              </button>

              <button
                type="button"
                className="novaIconBtn"
                onClick={toggleExpand}
                aria-label={isExpanded ? "Exit fullscreen" : "Enter fullscreen"}
              >
                {isExpanded ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                    <path
                      d="M9 3H3v6M15 3h6v6M21 15v6h-6M3 15v6h6"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                    <path
                      d="M14 3h7v7M10 21H3v-7M21 3l-7 7M3 21l7-7"
                      stroke="currentColor"
                      strokeWidth="1.8"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                )}
              </button>

              <button
                type="button"
                className="novaIconBtn"
                onClick={minimizeWidget}
                aria-label="Minimize"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <path d="M6 11H18V13H6V11Z" fill="currentColor" />
                </svg>
              </button>

              <button
                type="button"
                className="novaIconBtn"
                onClick={() => {
                  setNovaView("chat");
                  setIsOpen(false);
                  setIsExpanded(false);
                }}
                aria-label="Close"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <path
                    d="M6 6l12 12M18 6 6 18"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            </div>
          </div>

          <div
            className={`novaWidgetBody ${
              novaView === "form" ? "novaWidgetBody--form" : ""
            }`}
          >
            {novaView === "form" ? (
              <div className="novaFormHost">
                <CustomerFillForm
                  embedded
                  initialType={embeddedFormType}
                  onCancel={() => setNovaView("chat")}
                />
              </div>
            ) : (
              <>
                <div className="novaChatList" ref={listRef}>
                  {messages.map((m) => (
                    <div
                      key={m.id}
                      className={`novaMsg ${
                        m.from === "user" ? "novaMsg--user" : "novaMsg--bot"
                      }`}
                    >
                      <div className="novaBubble">
                        {m.typing ? (
                          <div className="novaTyping">
                            <span />
                            <span />
                            <span />
                          </div>
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
                          {voiceBusy
                            ? "Transcribing…"
                            : voiceDraft.trim()
                            ? "Review & insert"
                            : "Listening…"}
                        </div>
                        <div className="novaWaves" aria-hidden="true">
                          <span className="novaWave" />
                          <span className="novaWave" />
                          <span className="novaWave" />
                          <span className="novaWave" />
                          <span className="novaWave" />
                        </div>
                      </div>

                      <div className="novaVoiceActions">
                        <button
                          type="button"
                          className="novaVoiceIconBtn cancel"
                          onClick={cancelVoice}
                          aria-label="Cancel recording"
                          disabled={voiceBusy}
                        >
                          <svg
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            aria-hidden="true"
                          >
                            <path
                              d="M6 6l12 12M18 6 6 18"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                            />
                          </svg>
                        </button>

                        <button
                          type="button"
                          className="novaVoiceIconBtn confirm"
                          onClick={confirmVoice}
                          aria-label="Insert transcript"
                          disabled={voiceBusy}
                        >
                          <svg
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            aria-hidden="true"
                          >
                            <path
                              d="M20 6L9 17l-5-5"
                              stroke="currentColor"
                              strokeWidth="2.4"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            />
                          </svg>
                        </button>
                      </div>
                    </div>
                  )}

                  <form
                    className="novaComposer"
                    onSubmit={(e) => {
                      e.preventDefault();
                      handleSend(text);
                      setText("");
                    }}
                  >
                    <button
                      type="button"
                      className={`novaMicBtn ${voiceActive ? "active" : ""}`}
                      aria-label="Voice input"
                      onClick={() => {
                        if (voiceActive) cancelVoice();
                        else startVoice();
                      }}
                    >
                      <svg
                        width="22"
                        height="22"
                        viewBox="0 0 24 24"
                        fill="none"
                        aria-hidden="true"
                      >
                        <path
                          d="M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3Z"
                          fill="currentColor"
                          opacity="0.95"
                        />
                        <path
                          d="M19 11a7 7 0 0 1-14 0"
                          stroke="currentColor"
                          strokeWidth="1.8"
                          strokeLinecap="round"
                        />
                        <path
                          d="M12 18v3"
                          stroke="currentColor"
                          strokeWidth="1.8"
                          strokeLinecap="round"
                        />
                      </svg>
                    </button>

                    <input
                      value={text}
                      onChange={(e) => setText(e.target.value)}
                      placeholder="Type a message…"
                    />

                    <button type="submit">Send</button>
                  </form>
                </div>

                {showNewChatConfirm && (
                  <div className="novaCloseModal">
                    <div className="novaCloseModalContent">
                      <p>Are you sure you want to start a new chat?</p>
                      <div className="novaCloseModalBtns">
                        <button onClick={confirmNewChat}>Yes</button>
                        <button onClick={() => setShowNewChatConfirm(false)}>
                          No
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}

      {/* ─── LOGOUT CONFIRM MODAL ─────────────────────────────── */}
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
