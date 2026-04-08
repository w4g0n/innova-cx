import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTheme, ThemeToggleBtn } from "./CustomerTheme";
import { getUser, authHeader } from "../../utils/auth";
import { getInitialsFromEmail } from "../../utils/userDisplay";
import { apiUrl } from "../../config/apiBase";
import novaLogo from "../../assets/nova-logo.png";
import TicketChat from "../../components/common/TicketChat";
import { sanitizeText, sanitizeId, formatTimeAgo } from "./sanitize";
import "./CustomerTicketDetails.css";

function formatTicketSource(v) {
  return String(v || "user").toLowerCase() === "chatbot" ? "Chatbot" : "User";
}

function statusTone(s) {
  const k = sanitizeText(s, 40).toLowerCase().replace(/\s+/g, "");
  if (k === "resolved")                     return { color: "#15803d", bg: "rgba(21,128,61,.12)"   };
  if (k === "inprogress")                   return { color: "#b45309", bg: "rgba(180,83,9,.12)"    };
  if (k === "escalated" || k === "overdue") return { color: "#b91c1c", bg: "rgba(185,28,28,.12)"   };
  return                                           { color: "#7c3aed", bg: "rgba(124,58,237,.12)"  };
}

// Base pipeline — Overdue and Escalated are never part of the normal flow.
// They are injected dynamically only when the ticket actually carries that status.
const BASE_STAGES = [
  { id: "open",       label: "Opened"      },
  { id: "assigned",   label: "Assigned"    },
  { id: "inprogress", label: "In Progress" },
  { id: "resolved",   label: "Resolved"    },
];

const EXCEPTION_STAGES = {
  overdue:   { id: "overdue",   label: "Overdue"   },
  escalated: { id: "escalated", label: "Escalated" },
};

// Build the visible stages for a given ticket status.
// If the status is overdue or escalated, splice it in before "Resolved".
function buildStages(status) {
  const k = normalizeStatus(status);
  if (k === "overdue" || k === "escalated") {
    const stages = [...BASE_STAGES];
    // Insert the exception stage before the last step (Resolved)
    stages.splice(stages.length - 1, 0, EXCEPTION_STAGES[k]);
    return stages;
  }
  return BASE_STAGES;
}

function getStageIndex(stages, status) {
  const k = normalizeStatus(status);
  const idx = stages.findIndex((s) => s.id === k);
  return idx === -1 ? 0 : idx;
}

function normalizeStatus(s) {
  return sanitizeText(s, 40).toLowerCase().replace(/\s+/g, "");
}

export default function CustomerTicketDetails() {
  const navigate           = useNavigate();
  const { id: rawId }      = useParams();
  const [theme, toggleTheme] = useTheme();

  // Sanitize the URL param before using it in API calls or rendering
  // Only allow the characters that a real ticket ID can contain
  const id = sanitizeId(rawId, 48);

  const [ticket,  setTicket]  = useState(null);
  const [loading, setLoading] = useState(true);

  const [user] = useState(() => getUser() || {});
  const initials  = getInitialsFromEmail(user?.email, "U");
  const firstName = (() => {
    const name = sanitizeText(user?.name || user?.full_name || "", 100);
    if (name) return name.split(" ")[0];
    const raw = sanitizeText(user?.email || "", 254)
      .split("@")[0]
      .replace(/[._\-\d]+/g, " ")
      .trim();
    if (!raw) return "User";
    return raw.split(" ")[0].charAt(0).toUpperCase() + raw.split(" ")[0].slice(1);
  })();

  const [profileMenuOpen,   setProfileMenuOpen]   = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const [notifications,     setNotifications]     = useState([]);
  const profileRef = useRef(null);

  /* fetch notifications filtered to this ticket's ticket_code */
  useEffect(() => {
    if (!id) return;
    let mounted = true;
    (async () => {
      try {
        const res = await fetch(
          apiUrl("/api/customer/notifications?limit=50"),
          { headers: authHeader() }
        );
        if (!res.ok || !mounted) return;
        const data = await res.json();
        const all = Array.isArray(data.notifications) ? data.notifications : [];
        // Backend returns ticketId as ticket_code (e.g. "CX-123"), id is the URL param
        const forThisTicket = all.filter(
          (n) => sanitizeText(n.ticketId || "", 48) === id
        );
        if (mounted) setNotifications(forThisTicket);
      } catch { /* non-critical */ }
    })();
    return () => { mounted = false; };
  }, [id]);

  /* fetch ticket */
  useEffect(() => {
    // Reject obviously invalid IDs before making a network request
    if (!id) {
      setTicket(null);
      setLoading(false);
      return;
    }

    let mounted = true;

    const load = async (silent = false) => {
      if (!silent && mounted) setLoading(true);
      try {
        const res = await fetch(
          apiUrl(`/api/customer/tickets/${encodeURIComponent(id)}`),
          { headers: authHeader() }
        );
        if (!res.ok) throw new Error("Not found");
        const data = await res.json();
        const t = data.ticket;
        if (!mounted) return;

        setTicket({
          // Sanitize every field from the API before storing in state
          id:          sanitizeId(t.ticketId, 48),
          title:       sanitizeText(t.description?.subject, 200),
          source:      formatTicketSource(t.ticketSource),
          status:      sanitizeText(t.status, 40),
          date:        sanitizeText(t.issueDate, 40),
          priority:    sanitizeText(t.priority, 20),
          description: sanitizeText(t.description?.details, 5000),
          updates: Array.isArray(t.updates)
            ? t.updates.map((u) => ({
                _dateRaw: u.date ?? "",                  // kept for timeline sort
                date:     u.date ? formatTimeAgo(u.date) : "",
                message:  sanitizeText(u.message, 500),
                type:     sanitizeText(u.type, 40),
                author:   sanitizeText(u.author || "System", 100),
              }))
            : [],
        });
      } catch {
        if (mounted) setTicket(null);
      } finally {
        if (!silent && mounted) setLoading(false);
      }
    };

    load(false);
    const poll = setInterval(() => load(true), 5000);
    return () => {
      mounted = false;
      clearInterval(poll);
    };
  }, [id]);

  /* click outside */
  useEffect(() => {
    const handler = (e) => {
      if (profileRef.current && !profileRef.current.contains(e.target))
        setProfileMenuOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const confirmLogout = () => {
    ["user", "token", "temp_token", "access_token"].forEach((k) =>
      localStorage.removeItem(k)
    );
    navigate("/");
  };

  const tone         = statusTone(ticket?.status);
  const pipeStages   = buildStages(ticket?.status ?? "open");
  const stageIdx     = getStageIndex(pipeStages, ticket?.status ?? "open");
  const progress     = Math.round((stageIdx / (pipeStages.length - 1)) * 100);

  // Merge ticket.updates + notifications into one sorted timeline (newest first).
  // Backend returns notification.ticketId as ticket_code and timestamp as "timestamp".
  const timelineEntries = (() => {
    const entries = [];
    (ticket?.updates ?? []).forEach((u) => {
      entries.push({
        kind:    "update",
        author:  u.author,
        tag:     u.type || "",
        text:    u.message,
        dateRaw: u._dateRaw ?? "",
        date:    u.date,
      });
    });
    notifications.forEach((n) => {
      entries.push({
        kind:    "notification",
        author:  sanitizeText(n.sender || n.author || "System", 100),
        tag:     sanitizeText(n.title || "Notification", 100),
        text:    sanitizeText(n.message || n.body || "", 300),
        dateRaw: n.timestamp ?? "",                 // backend field is "timestamp"
        date:    n.timestamp ? formatTimeAgo(n.timestamp) : "",
      });
    });
    entries.sort((a, b) => {
      const da = a.dateRaw ? new Date(a.dateRaw).getTime() : 0;
      const db = b.dateRaw ? new Date(b.dateRaw).getTime() : 0;
      return db - da;
    });
    return entries;
  })();

  return (
    <div className="ctd-page">

      <header className="cs-topbar">
        <div className="cs-topbar-left">
          <img
            src={novaLogo}
            alt="InnovaAI logo"
            className="cs-topbar-logo cs-topbar-logo--clickable"
            role="button"
            tabIndex={0}
            aria-label="Go to dashboard"
            onClick={() => navigate("/customer")}
            onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") navigate("/customer"); }}
            style={{ cursor: "pointer" }}
          />
          <div className="cs-topbar-divider" />
          <span className="cs-topbar-label">Ticket Details</span>
          <button
            type="button"
            className="cs-back-btn"
            aria-label="Back to My Tickets"
            onClick={() => navigate("/customer/mytickets")}
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
            My Tickets
          </button>
        </div>
        <div className="cs-topbar-right">
          <ThemeToggleBtn theme={theme} onToggle={toggleTheme} />

          {/* Profile */}
          <div className="navAction" ref={profileRef}>
            <button
              type="button"
              className={`cl-avatar-btn${profileMenuOpen ? " is-active" : ""}`}
              aria-label="Account menu"
              aria-haspopup="true"
              aria-expanded={profileMenuOpen}
              onClick={() => setProfileMenuOpen((p) => !p)}
            >
              <div className="cl-avatar-initials">{initials}</div>
              <span className="cl-avatar-name">{firstName}</span>
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
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
                  onClick={() => {
                    setProfileMenuOpen(false);
                    setShowLogoutConfirm(true);
                  }}
                >
                  Log out
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      <div className="ctd-page-header">
        <div>
          <h1 className="ctd-page-title">Ticket Details</h1>
          <p className="ctd-page-sub">
            View ticket information, status, and updates.
          </p>
        </div>
      </div>

      {loading ? (
        <div className="ctd-loading">
          <div className="ctd-loading-spinner" />
          <span>Loading ticket...</span>
        </div>
      ) : !ticket ? (
        <div className="ctd-not-found">
          <div className="ctd-not-found-icon">
            <svg
              width="48"
              height="48"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <line x1="16" y1="13" x2="8" y2="13" />
              <line x1="16" y1="17" x2="8" y2="17" />
              <line x1="10" y1="9" x2="8" y2="9" />
            </svg>
          </div>
          <h3>Ticket not found</h3>
          {/* Render the sanitized id — never rawId from the URL */}
          <p>
            We couldn&apos;t find ticket <strong>{id || "unknown"}</strong>.
          </p>
          <button
            type="button"
            className="cs-btn cs-btn-primary"
            onClick={() => navigate("/customer/mytickets")}
          >
            Go to My Tickets
          </button>
        </div>
      ) : (
        <div className="ctd-body">
          <div className="ctd-layout">

            {/* LEFT COLUMN */}
            <div className="ctd-left-col">

              {/* Ticket info card */}
              <section className="ctd-card">
                <div className="ctd-id-row">
                  {/* ticket.id is sanitizeId'd in the fetch handler */}
                  <span className="ctd-mono">{ticket.id}</span>
                  <span className="ctd-dot">·</span>
                  <span className="ctd-mono">Ticket</span>
                  <span className="ctd-dot">·</span>
                  {/* source comes from formatTicketSource — returns only "Chatbot" or "User" */}
                  <span className="ctd-mono">{ticket.source}</span>
                  <span className="ctd-dot">·</span>
                  <span
                    className="ctd-status-badge"
                    style={{ color: tone.color, background: tone.bg }}
                  >
                    <span
                      className="ctd-status-dot"
                      style={{ background: tone.color }}
                    />
                    {ticket.status}
                  </span>
                </div>

                <h2 className="ctd-ticket-title">{ticket.title}</h2>

                <div className="ctd-meta-row">
                  <div className="ctd-meta-item">
                    <span className="ctd-meta-label">Created</span>
                    {/* ticket.date is sanitizeText'd — never a raw ISO string rendered */}
                    <span className="ctd-meta-value">{ticket.date}</span>
                  </div>
                </div>

                <div className="ctd-divider" />
                <div className="ctd-description-block">
                  <p className="ctd-section-label">Description</p>
                  {/* ticket.description is sanitizeText'd at max 5000 chars */}
                  <p className="ctd-description">{ticket.description}</p>
                </div>
              </section>

              {/* Pipeline + activity card */}
              <section className="ctd-card">
                <p className="ctd-section-label">Updates</p>

                {/* Status pipeline */}
                <div className="ctd-pipeline">
                  <div className="ctd-pipeline-top">
                    <div>
                      <div className="ctd-pipeline-eyebrow">Ticket Status</div>
                      <div className="ctd-pipeline-current" aria-live="polite" aria-atomic="true">
                        {pipeStages[stageIdx].label}
                      </div>
                    </div>
                    <div className="ctd-pipeline-frac">
                      <span className="ctd-frac-num">{stageIdx + 1}</span>
                      <span className="ctd-frac-sep">/</span>
                      <span className="ctd-frac-total">{pipeStages.length}</span>
                    </div>
                  </div>

                  <div className="ctd-track">
                    <div
                      className="ctd-track-fill"
                      style={{
                        width: `${progress}%`,
                        ...(
                          (normalizeStatus(ticket.status) === "overdue" || normalizeStatus(ticket.status) === "escalated")
                            ? { background: "linear-gradient(90deg,#991b1b,#b91c1c,#ef4444)" }
                            : {}
                        ),
                      }}
                    />
                  </div>

                  <div className="ctd-stage-dots">
                    {pipeStages.map((stage, i) => (
                      <div key={stage.id} className="ctd-stage-wrap">
                        <div
                          className={`ctd-stage-dot ${i < stageIdx ? "done" : ""} ${i === stageIdx ? "current" : ""}${i === stageIdx && (stage.id === "overdue" || stage.id === "escalated") ? " exception" : ""}`}
                          style={
                            i === stageIdx && (stage.id === "overdue" || stage.id === "escalated")
                              ? { background: "#b91c1c", borderColor: "#b91c1c", boxShadow: "0 0 12px rgba(185,28,28,.45)" }
                              : undefined
                          }
                        >
                          {i < stageIdx  && <span className="ctd-dot-check">✓</span>}
                          {i === stageIdx && <span className="ctd-dot-pulse" />}
                        </div>
                        <div
                          className={`ctd-stage-label ${i === stageIdx ? "active" : ""}`}
                          style={
                            i === stageIdx && (stage.id === "overdue" || stage.id === "escalated")
                              ? { color: "#b91c1c" }
                              : undefined
                          }
                        >
                          {stage.label}
                          {i === stageIdx && (
                            <span className="ctd-dot-cond">Current</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="ctd-divider ctd-divider--gap" />
                <p className="ctd-section-label">Activity</p>
                {timelineEntries.length === 0 ? (
                  <div className="ctd-log-empty">
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: .4 }}>
                      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                      <polyline points="14 2 14 8 20 8" />
                      <line x1="16" y1="13" x2="8" y2="13" />
                      <line x1="16" y1="17" x2="8" y2="17" />
                    </svg>
                    No activity yet
                  </div>
                ) : (
                  <div className="ctd-log-list">
                    {timelineEntries.map((entry, i) => {
                      const isNotif   = entry.kind === "notification";
                      const tagLower  = (entry.tag || "").toLowerCase();
                      const isResolve = tagLower.includes("resolv");
                      const isAlert   = tagLower.includes("escal") || tagLower.includes("overdue");
                      const dotColor  = isAlert   ? "#b91c1c"
                                      : isResolve ? "#15803d"
                                      : isNotif   ? "var(--orchid)"
                                      :             "var(--pink)";
                      const tagBg     = isAlert   ? "rgba(185,28,28,.10)"
                                      : isResolve ? "rgba(21,128,61,.10)"
                                      : isNotif   ? "rgba(109,40,217,.12)"
                                      :             "rgba(147,51,234,.12)";
                      const tagColor  = isAlert   ? "#b91c1c"
                                      : isResolve ? "#15803d"
                                      : isNotif   ? "var(--orchid)"
                                      :             "var(--pink)";
                      const isLast    = i === timelineEntries.length - 1;
                      return (
                        <div key={i} className="ctd-log-row">
                          <div className="ctd-log-spine">
                            <div className="ctd-log-dot" style={{ background: dotColor }} />
                            {!isLast && <div className="ctd-log-line" />}
                          </div>
                          <div className="ctd-log-body">
                            <div className="ctd-log-meta">
                              <span className="ctd-log-author">{entry.author}</span>
                              {entry.tag ? (
                                <span className="ctd-log-tag" style={{ background: tagBg, color: tagColor }}>
                                  {entry.tag}
                                </span>
                              ) : null}
                              {entry.date ? (
                                <span className="ctd-log-date">{entry.date}</span>
                              ) : null}
                            </div>
                            {entry.text ? (
                              <p className="ctd-log-text">{entry.text}</p>
                            ) : null}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>
            </div>

            {/* RIGHT COLUMN */}
            <div className="ctd-right-col">
              <section className="ctd-card ctd-chat-card">
                <div className="ctd-chat-card-header">
                  <div className="ctd-chat-card-icon">
                    <svg
                      width="14"
                      height="14"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                    </svg>
                  </div>
                  <span className="ctd-chat-card-title">Ticket Conversation</span>
                  {normalizeStatus(ticket.status) === "resolved" && (
                    <span className="ctd-chat-resolved-badge">Resolved</span>
                  )}
                </div>
                <TicketChat
                  // ticket.id is already sanitizeId'd
                  ticketId={ticket.id}
                  role="customer"
                  authHeader={authHeader}
                  disabled={normalizeStatus(ticket.status) === "resolved"}
                />
              </section>
            </div>

          </div>
        </div>
      )}

      <footer className="cs-footer">
        <img src={novaLogo} alt="InnovaAI" className="cs-footer-logo" />
        <p className="cs-footer-copy">© 2026 InnovaAI</p>
      </footer>

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
    </div>
  );
}