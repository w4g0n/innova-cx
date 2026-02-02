import React, { useMemo, useRef, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./CustomerLanding.css";
import dccLogo from "../../assets/dcc-logo.png";
import CustomerFillForm from "./CustomerFillForm";

export default function CustomerLanding() {
  const navigate = useNavigate();

  const clusters = [
    { title: "Business", desc: "Flexible office & workspace options" },
    { title: "Logistics", desc: "Advanced warehousing & delivery solutions" },
    { title: "Social", desc: "Restaurants, cafes & amenities" },
  ];

  const listRef = useRef(null);
  const profileRef = useRef(null);
  const notifRef = useRef(null);

  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [showCloseConfirm, setShowCloseConfirm] = useState(false);
  const [stage, setStage] = useState("start");
  const [hasChosenType, setHasChosenType] = useState(false);
  const [text, setText] = useState("");
  const [messages, setMessages] = useState([]);

  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);

  // ✅ toggle between chat and embedded form
  const [novaView, setNovaView] = useState("chat"); // "chat" | "form"

  const user = useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem("user") || "{}");
    } catch {
      return {};
    }
  }, []);

  const nameFromEmail = useMemo(() => {
    const email = (user?.email || "").trim();
    if (!email.includes("@")) return "there";
    const raw = email.split("@")[0];
    const cleaned = raw.replace(/[._-]+/g, " ").trim();
    if (!cleaned) return "there";
    return cleaned
      .split(" ")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
  }, [user]);

  const initialsFromEmail = useMemo(() => {
    const email = (user?.email || "").trim();
    if (!email.includes("@")) return "U";
    const raw = email.split("@")[0] || "";
    const parts = raw.replace(/[._-]+/g, " ").trim().split(" ").filter(Boolean);
    if (parts.length === 0) return "U";
    if (parts.length === 1) return (parts[0][0] || "U").toUpperCase();
    return `${(parts[0][0] || "U").toUpperCase()}${(parts[1][0] || "").toUpperCase()}`;
  }, [user]);

  // ✅ Notifications state (demo now, real API later)
  const [notifications, setNotifications] = useState([
    { id: "n1", title: "Your complaint has been received", meta: "Just now", read: false },
    { id: "n2", title: "Ticket #1042 is now In Progress", meta: "2h ago", read: false },
    { id: "n3", title: "We responded to your inquiry", meta: "Yesterday", read: true },
  ]);

  const unreadCount = useMemo(
    () => notifications.filter((n) => !n.read).length,
    [notifications]
  );

  const closeAllPopovers = () => {
    setProfileMenuOpen(false);
    setNotifOpen(false);
  };

  // Close popovers on outside click / Esc
  useEffect(() => {
    const onMouseDown = (e) => {
      const t = e.target;
      if (profileRef.current && !profileRef.current.contains(t)) setProfileMenuOpen(false);
      if (notifRef.current && !notifRef.current.contains(t)) setNotifOpen(false);
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
  }, []);

  // ---------- INITIAL MESSAGES ----------
  const startChatMessages = () => {
    const id1 = `bot-${Date.now()}`;
    const id2 = `bot-${Date.now() + 1}`;
    setMessages([{ id: id1, from: "bot", text: "", typing: true }]);
    setTimeout(() => {
      setMessages([
        { id: id1, from: "bot", text: `Hi ${nameFromEmail}! I’m Nova. How can I help you today?`, typing: false },
        { id: id2, from: "bot", text: "Would you like to file a complaint or do you have an inquiry?", typing: false },
      ]);
      setStage("chooseType");
      setHasChosenType(false);
    }, 800);
  };

  // eslint-disable-next-line react-hooks/set-state-in-effect -- TODO: review - setState in useEffect, consider restructuring
  useEffect(() => startChatMessages(), [nameFromEmail]);

  // ---------- AUTO SCROLL ----------
  useEffect(() => {
    if (!isOpen) return;
    if (novaView !== "chat") return;
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, isOpen, isExpanded, novaView]);

  // ---------- CHAT HELPERS ----------
  const pushUser = (msg) => {
    setMessages((prev) => [...prev, { id: `user-${Date.now()}`, from: "user", text: msg, typing: false }]);
  };

  const pushBot = (msg, delay = 800) => {
    const typingId = `bot-${Date.now()}`;
    setMessages((prev) => [...prev, { id: typingId, from: "bot", text: "", typing: true }]);
    setTimeout(() => {
      setMessages((prev) =>
        prev.map((m) => (m.id === typingId ? { ...m, text: msg, typing: false } : m))
      );
    }, delay);
  };

  const goToForm = (type) => {
    const url = type ? `/customer/fill-form?type=${encodeURIComponent(type)}` : "/customer/fill-form";
    window.location.href = url;
  };

  const handleSelect = (type) => {
    setHasChosenType(true);
    if (type === "complaint") {
      pushUser("I want to raise a complaint.");
      pushBot("Got it. You can submit the complaint here in chat, or fill a form instead. Which do you prefer?");
      setStage("complaintChoice");
    }
    if (type === "inquiry") {
      pushUser("I want to raise an inquiry.");
      pushBot("Sure — tell me your question and I’ll try to help right away.");
      setStage("inquiry");
    }
  };

  const handleSend = (e) => {
    e.preventDefault();
    const value = text.trim();
    if (!value) return;
    pushUser(value);
    setText("");

    if (stage === "complaintChoice") {
      if (value.toLowerCase().includes("form")) {
        pushBot("No problem — taking you to the complaint form now.");
        setTimeout(() => goToForm("Complaint"), 250);
      } else {
        pushBot("Okay — please describe the complaint in one or two sentences. Include key details.");
      }
      setStage("start");
      return;
    }

    if (stage === "inquiry") {
      pushBot("Thanks — for this demo, I’ll log your inquiry. Would you like to submit a form for tracking?");
      setStage("start");
      return;
    }

    pushBot("Thanks — I can help with that.");
  };

  const handleClose = () => setShowCloseConfirm(true);

  const confirmClose = () => {
    setShowCloseConfirm(false);
    setIsOpen(false);
    setIsExpanded(false);
    setNovaView("chat");
    setMessages([]);
    setStage("start");
    startChatMessages();
  };

  const openHistory = () => {
    closeAllPopovers();
    navigate("/customer/history");
  };

  const openSettings = () => {
    closeAllPopovers();
    navigate("/customer/settings");
  };

  const handleLogout = () => {
    closeAllPopovers();
    localStorage.removeItem("user");
    navigate("/");
  };

  const toggleNotifications = () => {
    setProfileMenuOpen(false);
    setNotifOpen((v) => {
      const next = !v;
      // mark as read when opened
      if (next) {
        setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
      }
      return next;
    });
  };

  // ✅ show form inside expanded widget only
  const toggleFormInChat = () => {
    closeAllPopovers();

    if (!isOpen) setIsOpen(true);
    if (!isExpanded) setIsExpanded(true);

    setNovaView((prev) => (prev === "form" ? "chat" : "form"));
  };

  const toggleExpand = () => {
    setIsExpanded((prev) => {
      const next = !prev;
      // if shrinking, ensure we’re not on form
      if (!next) setNovaView("chat");
      return next;
    });
  };

  return (
    <div className="customer-landing-page">
      {/* --- MAIN CONTENT --- */}
      <div className="main-content">
        {/* NAVBAR */}
        <nav className="navbar">
          <div className="logo">
            <img src={dccLogo} alt="Dubai CommerCity" />
          </div>

          <ul className="nav-links">
            <li><a href="#">Our Facilities</a></li>
            <li><a href="#">Digital Ecosystem</a></li>
            <li><a href="#">About</a></li>
            <li><a href="#">Newsroom</a></li>
            <li><a href="#">Contact</a></li>
          </ul>

          <div className="nav-actions">
            {/* Notifications */}
            <div className="navAction" ref={notifRef}>
              <button
                type="button"
                className={`navIconButton ${notifOpen ? "isOpen" : ""}`}
                aria-label="Notifications"
                onClick={toggleNotifications}
              >
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                  <path
                    d="M12 22a2.25 2.25 0 0 0 2.2-1.8h-4.4A2.25 2.25 0 0 0 12 22Zm7-6V11a7 7 0 1 0-14 0v5l-2 2v1h18v-1l-2-2Z"
                    fill="currentColor"
                    opacity="0.95"
                  />
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
                    {notifications.map((n) => (
                      <div key={n.id} className="navPopoverItem">
                        <div className="navPopoverItemTitle">{n.title}</div>
                        <div className="navPopoverItemMeta">{n.meta}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Profile */}
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
                <span className="navAvatarCircle" aria-hidden="true">{initialsFromEmail}</span>
              </button>

              {profileMenuOpen && (
                <div className="navDropdown" role="menu" aria-label="Profile">
                  <button type="button" className="navDropdownItem" onClick={openHistory}>
                    History
                  </button>
                  <button type="button" className="navDropdownItem" onClick={openSettings}>
                    Settings
                  </button>
                  <div className="navDropdownDivider" />
                  <button type="button" className="navDropdownItem danger" onClick={handleLogout}>
                    Logout
                  </button>
                </div>
              )}
            </div>
          </div>
        </nav>

        {/* HERO */}
        <section className="hero">
          <div className="hero-content">
            <div className="hero-title-wrapper">
              <h1 className="hero-title"><span className="hero-static">We are</span></h1>
              <div className="hero-dynamic">
                <div className="hero-dynamic-inner">
                  <span>Dubai CommerCity</span>
                  <span>Leading Business Hub</span>
                  <span>Driving Digital Commerce</span>
                </div>
              </div>
              <div className="hero-line" />
            </div>

            <div className="hero-body">
              <button className="btn-hero">Learn More</button>
              <p className="hero-desc">
                Dubai CommerCity is the first and leading free zone dedicated exclusively
                to digital commerce in the Middle East Africa and South Asia (MEASA) region
              </p>
            </div>
          </div>
        </section>

        {/* CLUSTERS */}
        <section className="clusters">
          {clusters.map((c, i) => (
            <div key={i} className="cluster-card">
              <h3>{c.title}</h3>
              <p>{c.desc}</p>
            </div>
          ))}
        </section>

        {/* FOOTER */}
        <footer className="footer">
          <p>© 2026 Dubai CommerCity</p>
          <div className="footer-links">
            <span>Privacy Policy</span>
            <span>Terms of Use</span>
            <span>Contact</span>
          </div>
        </footer>
      </div>

      {/* --- CHAT WIDGET --- */}
      {!isOpen && (
        <button className="novaWidgetLauncher" onClick={() => setIsOpen(true)}>
          <span className="novaWidgetDot" /> Chat with Nova
        </button>
      )}

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
                className="novaIconBtn"
                onClick={toggleExpand}
                aria-label={isExpanded ? "Minimize" : "Maximize"}
              >
                {isExpanded ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                    <path d="M6 11H18V13H6V11Z" fill="currentColor" />
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
                onClick={() => {
                  // close behaves cleanly regardless of view
                  setNovaView("chat");
                  handleClose();
                }}
                aria-label="Close"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
                </svg>
              </button>
            </div>
          </div>

          <div className={`novaWidgetBody ${novaView === "form" ? "novaWidgetBody--form" : ""}`}>
            {novaView === "form" ? (
              <div className="novaFormHost">
                <CustomerFillForm embedded onCancel={() => setNovaView("chat")} />
              </div>
            ) : (
              <>
                <div className="novaChatList" ref={listRef}>
                  {messages.map((m) => (
                    <div
                      key={m.id}
                      className={`novaMsg ${m.from === "user" ? "novaMsg--user" : "novaMsg--bot"}`}
                    >
                      <div className="novaBubble">
                        {m.typing ? <div className="novaTyping"><span /><span /><span /></div> : m.text}
                      </div>
                    </div>
                  ))}

                  {!hasChosenType && stage === "chooseType" && (
                    <div className="novaQuickRow">
                      <button onClick={() => handleSelect("complaint")}>Complaint</button>
                      <button onClick={() => handleSelect("inquiry")}>Inquiry</button>
                    </div>
                  )}
                </div>

                {hasChosenType && (
                  <form className="novaComposer" onSubmit={handleSend}>
                    <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Type a message…" />
                    <button type="submit">Send</button>
                  </form>
                )}

                {showCloseConfirm && (
                  <div className="novaCloseModal">
                    <div className="novaCloseModalContent">
                      <p>Are you sure you want to end the chat?</p>
                      <div className="novaCloseModalBtns">
                        <button onClick={confirmClose}>Yes</button>
                        <button onClick={() => setShowCloseConfirm(false)}>No</button>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
