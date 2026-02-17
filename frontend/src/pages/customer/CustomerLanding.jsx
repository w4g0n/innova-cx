import React, { useMemo, useRef, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./CustomerLanding.css";
import dccLogo from "../../assets/dcc-logo.png";
import CustomerFillForm from "./CustomerFillForm";
import useNovaChatbot from "./chatbot.js";
import { getInitialsFromEmail } from "../../utils/userDisplay";

export default function CustomerLanding() {
  const navigate = useNavigate();

  const [embeddedFormType, setEmbeddedFormType] = useState("Complaint");

  const {
    listRef,
    messages,
    text,
    setText,
    stage,
    hasChosenType,
    handleSelect,
    handleSend,
    resetSession,
  } = useNovaChatbot({
    onGoToForm: (type) => {
      resetSession();
      setEmbeddedFormType(type || "Complaint");
      if (!isOpen) setIsOpen(true);
      if (!isExpanded) setIsExpanded(true);
      setNovaView("form");
    },
  });

  const clusters = [
    { title: "Business", desc: "Flexible office & workspace options" },
    { title: "Logistics", desc: "Advanced warehousing & delivery solutions" },
    { title: "Social", desc: "Restaurants, cafes & amenities" },
  ];

  const profileRef = useRef(null);
  const notifRef = useRef(null);

  const [isOpen, setIsOpen] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [showCloseConfirm, setShowCloseConfirm] = useState(false);

  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [notifOpen, setNotifOpen] = useState(false);

  const [novaView, setNovaView] = useState("chat");

  const user = useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem("user") || "{}");
    } catch {
      return {};
    }
  }, []);

  const initialsFromEmail = useMemo(
    () => getInitialsFromEmail(user?.email, "U"),
    [user]
  );

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
  }, [listRef]);

  useEffect(() => {
    if (!isOpen) return;
    if (novaView !== "chat") return;
    if (listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight;
  }, [messages, isOpen, isExpanded, novaView, listRef]);

  const handleClose = () => setShowCloseConfirm(true);

  const confirmClose = () => {
    setShowCloseConfirm(false);
    setIsOpen(false);
    setIsExpanded(false);
    setNovaView("chat");
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
      if (next) {
        setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
      }
      return next;
    });
  };

  const toggleFormInChat = () => {
    closeAllPopovers();

    if (!isOpen) setIsOpen(true);
    if (!isExpanded) setIsExpanded(true);

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
      alert("Voice input isn’t supported in this browser. Try Chrome.");
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

  return (
    <div className="customer-landing-page">
      <div className="main-content">
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
                    My Tickets
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

        <section className="clusters">
          {clusters.map((c, i) => (
            <div key={i} className="cluster-card">
              <h3>{c.title}</h3>
              <p>{c.desc}</p>
            </div>
          ))}
        </section>

        <footer className="footer">
          <p>© 2026 Dubai CommerCity</p>
          <div className="footer-links">
            <span>Privacy Policy</span>
            <span>Terms of Use</span>
            <span>Contact</span>
          </div>
        </footer>
      </div>

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
                      className={`novaMsg ${m.from === "user" ? "novaMsg--user" : "novaMsg--bot"}`}
                    >
                      <div className="novaBubble">
                        {m.typing ? <div className="novaTyping"><span /><span /><span /></div> : m.text}
                      </div>
                    </div>
                  ))}

                  {!hasChosenType && (
                    <div className="novaQuickRow">
                    <button onClick={() => handleSelect("complaint")}>Complaint</button>
                    <button onClick={() => handleSelect("inquiry")}>Inquiry</button>
                  </div>
                )}
                </div>

                {hasChosenType && stage === "inquiry" && (
                  <div className="novaComposerWrap">
                    {voiceActive && (
                      <div className={`novaVoiceBar ${voiceBusy ? "isBusy" : ""}`}>
                        <div className="novaVoiceLeft">
                          <div className="novaVoiceText">
                            {voiceBusy ? "Transcribing…" : (voiceDraft.trim() ? "Review & insert" : "Listening…")}
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
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
                              <path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                            </svg>
                          </button>

                          <button
                            type="button"
                            className="novaVoiceIconBtn confirm"
                            onClick={confirmVoice}
                            aria-label="Insert transcript"
                            disabled={voiceBusy}
                          >
                            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
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
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" aria-hidden="true">
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
