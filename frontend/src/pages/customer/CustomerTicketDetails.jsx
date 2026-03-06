import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useTheme, ThemeToggleBtn } from "./CustomerTheme";
import { getUser, authHeader } from "../../utils/auth";
import { getInitialsFromEmail } from "../../utils/userDisplay";
import { apiUrl } from "../../config/apiBase";
import PriorityPill from "../../components/common/PriorityPill";
import novaLogo from "../../assets/nova-logo.png";
import "./CustomerTicketDetails.css";

/* ── helpers ─────────────────────────────────────────────────── */
function formatTicketSource(v) {
  return String(v || "user").toLowerCase() === "chatbot" ? "Chatbot" : "User";
}

function statusTone(s) {
  const k = String(s || "").toLowerCase().replace(/\s+/g, "");
  if (k === "resolved")                     return { color: "#15803d", bg: "rgba(21,128,61,.12)"   };
  if (k === "inprogress")                   return { color: "#b45309", bg: "rgba(180,83,9,.12)"    };
  if (k === "escalated" || k === "overdue") return { color: "#b91c1c", bg: "rgba(185,28,28,.12)"   };
  return                                           { color: "#7c3aed", bg: "rgba(124,58,237,.12)"  };
}

function updateTypeTone(type) {
  const t = String(type || "").toLowerCase();
  if (t === "system")          return { dot: "#7c3aed", bg: "rgba(124,58,237,.1)",  color: "#7c3aed", label: "AI Stage"  };
  if (t === "status_change")   return { dot: "#15803d", bg: "rgba(21,128,61,.1)",   color: "#15803d", label: "Status"   };
  if (t === "priority_change") return { dot: "#b45309", bg: "rgba(180,83,9,.1)",    color: "#b45309", label: "Priority" };
  return                              { dot: "var(--muted)", bg: "var(--surface)",   color: "var(--muted)", label: type || "Update" };
}

const STATUS_STAGES = [
  { id: "open",       label: "Opened"      },
  { id: "inprogress", label: "In Progress" },
  { id: "assigned",   label: "Assigned"    },
  { id: "overdue",    label: "Overdue"     },
  { id: "escalated",  label: "Escalated"   },
  { id: "resolved",   label: "Resolved"    },
];
const STATUS_KEY_IDX = { open:0, inprogress:1, assigned:2, overdue:3, escalated:4, resolved:5 };

function normalizeStatus(s) { return String(s || "").toLowerCase().replace(/\s+/g, ""); }

/* ════════════════════════════════════════════════════════════════ */
export default function CustomerTicketDetails() {
  const navigate  = useNavigate();
  const { id }    = useParams();
  const [theme, toggleTheme] = useTheme();

  const [ticket,  setTicket]  = useState(null);
  const [loading, setLoading] = useState(true);

  const [user] = useState(() => getUser() || {});
  const initials   = getInitialsFromEmail(user?.email, "U");
  const firstName  = (() => {
    const name = user?.name || user?.full_name || "";
    if (name) return name.split(" ")[0];
    const raw = (user?.email || "").split("@")[0].replace(/[._\-\d]+/g, " ").trim();
    if (!raw) return "User";
    return raw.split(" ")[0].charAt(0).toUpperCase() + raw.split(" ")[0].slice(1);
  })();

  const [profileMenuOpen, setProfileMenuOpen] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);
  const profileRef = useRef(null);

  /* fetch ticket */
  useEffect(() => {
    let mounted = true;
    const load = async (silent = false) => {
      if (!silent && mounted) setLoading(true);
      try {
        const res = await fetch(apiUrl(`/api/customer/tickets/${id}`), { headers: authHeader() });
        if (!res.ok) throw new Error("Not found");
        const data = await res.json();
        const t = data.ticket;
        if (!mounted) return;
        setTicket({
          id:          t.ticketId,
          title:       t.description?.subject,
          source:      formatTicketSource(t.ticketSource),
          status:      t.status,
          date:        t.issueDate,
          priority:    t.priority,
          description: t.description?.details,
          updates:     (t.updates || []).map((u) => ({
            date:    u.date ? new Date(u.date).toLocaleString() : "",
            message: u.message,
            type:    u.type,
            author:  u.author || "System",
          })),
        });
      } catch {
        if (mounted) setTicket(null);
      } finally {
        if (!silent && mounted) setLoading(false);
      }
    };
    load(false);
    const poll = setInterval(() => load(true), 5000);
    return () => { mounted = false; clearInterval(poll); };
  }, [id]);

  /* click outside */
  useEffect(() => {
    const handler = (e) => {
      if (profileRef.current && !profileRef.current.contains(e.target)) setProfileMenuOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const confirmLogout = () => {
    ["user","token","temp_token","access_token"].forEach(k => localStorage.removeItem(k));
    navigate("/");
  };

  const tone = statusTone(ticket?.status);
  const stageIdx = STATUS_KEY_IDX[normalizeStatus(ticket?.status)] ?? 0;
  const progress = Math.round((stageIdx / (STATUS_STAGES.length - 1)) * 100);

  return (
    <div className="ctd-page">

      {/* ── TOPBAR ── */}
      <header className="cs-topbar">
        <div className="cs-topbar-left">
          <img src={novaLogo} alt="InnovaAI" className="cs-topbar-logo" />
          <div className="cs-topbar-divider" />
          <span className="cs-topbar-label">Ticket Details</span>
        </div>
        <div className="cs-topbar-right">
          <ThemeToggleBtn theme={theme} onToggle={toggleTheme} />

          {/* Profile */}
          <div className="navAction" ref={profileRef}>
            <button
              type="button"
              className={`cl-avatar-btn${profileMenuOpen ? " is-active" : ""}`}
              onClick={() => setProfileMenuOpen(p => !p)}
            >
              <div className="cl-avatar-initials">{initials}</div>
              <span className="cl-avatar-name">{firstName}</span>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round"><path d="M6 9l6 6 6-6"/></svg>
            </button>
            {profileMenuOpen && (
              <div className="navDropdown">
                <button type="button" className="navDropdownItem" onClick={() => navigate("/customer/settings")}>Settings</button>
                <div className="navDropdownDivider"/>
                <button type="button" className="navDropdownItem danger" onClick={() => { setProfileMenuOpen(false); setShowLogoutConfirm(true); }}>Log out</button>
              </div>
            )}
          </div>

          <button type="button" className="cs-back-btn" onClick={() => navigate("/customer/mytickets")}>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M19 12H5M12 5l-7 7 7 7"/></svg>
            My Tickets
          </button>
        </div>
      </header>

      {/* ── PAGE TITLE ── */}
      <div className="ctd-page-header">
        <div>
          <h1 className="ctd-page-title">Ticket Details</h1>
          <p className="ctd-page-sub">View ticket information, status, and updates.</p>
        </div>
      </div>

      {/* ── CONTENT ── */}
      {loading ? (
        <div className="ctd-loading">
          <div className="ctd-loading-spinner"/>
          <span>Loading ticket...</span>
        </div>
      ) : !ticket ? (
        <div className="ctd-not-found">
          <div className="ctd-not-found-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
              <line x1="10" y1="9" x2="8" y2="9"/>
            </svg>
          </div>
          <h3>Ticket not found</h3>
          <p>We couldn&apos;t find ticket <strong>{id}</strong>.</p>
          <button type="button" className="cs-btn cs-btn-primary" onClick={() => navigate("/customer/mytickets")}>
            Go to My Tickets
          </button>
        </div>
      ) : (
        <div className="ctd-layout">

          {/* LEFT — ticket info */}
          <section className="ctd-card">
            {/* Top row */}
            <div className="ctd-id-row">
              <span className="ctd-mono">{ticket.id}</span>
              <span className="ctd-dot">·</span>
              <span className="ctd-mono">Ticket</span>
              <span className="ctd-dot">·</span>
              <span className="ctd-mono">{ticket.source}</span>
              <span className="ctd-dot">·</span>
              <span className="ctd-status-badge" style={{ color: tone.color, background: tone.bg }}>
                <span className="ctd-status-dot" style={{ background: tone.color }}/>
                {ticket.status}
              </span>
            </div>

            <h2 className="ctd-ticket-title">{ticket.title}</h2>

            <div className="ctd-meta-row">
              <div className="ctd-meta-item">
                <span className="ctd-meta-label">Priority</span>
                <PriorityPill priority={ticket.priority}/>
              </div>
              <div className="ctd-meta-item">
                <span className="ctd-meta-label">Created</span>
                <span className="ctd-meta-value">{ticket.date}</span>
              </div>
            </div>

            <div className="ctd-divider"/>
            <p className="ctd-section-label">Description</p>
            <p className="ctd-description">{ticket.description}</p>
          </section>

          {/* RIGHT — pipeline + activity */}
          <section className="ctd-card">
            <p className="ctd-section-label">Updates</p>

            {/* Status pipeline */}
            <div className="ctd-pipeline">
              <div className="ctd-pipeline-top">
                <div>
                  <div className="ctd-pipeline-eyebrow">Ticket Status</div>
                  <div className="ctd-pipeline-current">{STATUS_STAGES[stageIdx].label}</div>
                </div>
                <div className="ctd-pipeline-frac">
                  <span className="ctd-frac-num">{stageIdx + 1}</span>
                  <span className="ctd-frac-sep">/</span>
                  <span className="ctd-frac-total">{STATUS_STAGES.length}</span>
                </div>
              </div>

              <div className="ctd-track">
                <div className="ctd-track-fill" style={{ width: `${progress}%` }}/>
              </div>

              <div className="ctd-stage-dots">
                {STATUS_STAGES.map((stage, i) => (
                  <div key={stage.id} className="ctd-stage-wrap">
                    <div className={`ctd-stage-dot ${i < stageIdx ? "done" : ""} ${i === stageIdx ? "current" : ""}`}>
                      {i < stageIdx  && <span className="ctd-dot-check">✓</span>}
                      {i === stageIdx && <span className="ctd-dot-pulse"/>}
                    </div>
                    <div className={`ctd-stage-label ${i === stageIdx ? "active" : ""}`}>
                      {stage.label}
                      {i === stageIdx && <span className="ctd-dot-cond">Current</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="ctd-divider ctd-divider--gap"/>
            <p className="ctd-section-label">Activity Log</p>

            {ticket.updates.length === 0 ? (
              <div className="ctd-log-empty">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" style={{ opacity: 0.4 }}>
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
                <div>No activity updates yet.</div>
              </div>
            ) : (
              <div className="ctd-log-list">
                {ticket.updates.map((u, idx) => {
                  const t = updateTypeTone(u.type);
                  return (
                    <div key={idx} className="ctd-log-row">
                      <div className="ctd-log-spine">
                        <div className="ctd-log-dot" style={{ background: t.dot }}/>
                        {idx < ticket.updates.length - 1 && <div className="ctd-log-line"/>}
                      </div>
                      <div className="ctd-log-body">
                        <div className="ctd-log-meta">
                          <span className="ctd-log-author">{u.author}</span>
                          <span className="ctd-log-tag" style={{ background: t.bg, color: t.color }}>{t.label}</span>
                          <span className="ctd-log-date">{u.date}</span>
                        </div>
                        <div className="ctd-log-text">{u.message}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      )}

      {/* ── FOOTER ── */}
      <footer className="cs-footer">
        <img src={novaLogo} alt="InnovaAI" className="cs-footer-logo" />
        <p className="cs-footer-copy">© 2026 InnovaAI</p>
      </footer>

      {/* ── LOGOUT CONFIRM ── */}
      {showLogoutConfirm && (
        <div className="cspw-overlay" onClick={() => setShowLogoutConfirm(false)}>
          <div className="cspw-modal" onClick={e => e.stopPropagation()}>
            <div className="cspw-header">
              <h3 className="cspw-title">Log out?</h3>
              <button type="button" className="cspw-close" onClick={() => setShowLogoutConfirm(false)}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"/></svg>
              </button>
            </div>
            <div style={{ padding: "22px 24px", display: "flex", flexDirection: "column", gap: 20 }}>
              <p style={{ color: "var(--muted)", fontSize: 14, margin: 0 }}>Are you sure you want to log out?</p>
              <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
                <button type="button" className="cs-btn cs-btn-ghost" onClick={() => setShowLogoutConfirm(false)}>Cancel</button>
                <button type="button" className="cs-btn cs-btn-primary" onClick={confirmLogout}>Log out</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}