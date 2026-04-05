import { useEffect, useRef, useState, useCallback } from "react";
import { apiUrl } from "../../config/apiBase";
import { getCsrfToken } from "../../services/api";
import { sanitizeText } from "../../pages/customer/sanitize";
import "./TicketChat.css";

/**
 * TicketChat — shared by CustomerTicketDetails & ComplaintDetails
 *
 * Props:
 *   ticketId   — the ticket ID string
 *   role       — "customer" | "employee"
 *   authHeader — function that returns the fetch headers object
 *   disabled   — (optional) bool — lock input when ticket is resolved
 */

const QUICK_REPLIES_EMPLOYEE = [
  "We have received your complaint and will resolve the issue within 24–48 hours.",
  "Your ticket has been escalated to the relevant team. We will update you shortly.",
  "We are currently investigating the issue. Thank you for your patience.",
  "Your issue has been resolved. Please let us know if you need further assistance.",
  "A specialist will contact you within 1–2 business days.",
];

function formatTime(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function Avatar({ role, initials }) {
  return (
    <div className={`tc-avatar tc-avatar--${role}`} aria-hidden="true">
      {role === "employee" ? (
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
          <circle cx="12" cy="7" r="4" />
        </svg>
      ) : (
        <span>{initials || "C"}</span>
      )}
    </div>
  );
}

export default function TicketChat({ ticketId, role, authHeader, disabled, paused = false }) {
  const [messages, setMessages]       = useState([]);
  const [text, setText]               = useState("");
  const [sending, setSending]         = useState(false);
  const [error, setError]             = useState("");
  const [showQuick, setShowQuick]     = useState(false);
  const [loadingMsgs, setLoadingMsgs] = useState(true);

  const listRef    = useRef(null);
  const inputRef   = useRef(null);
  const pollRef    = useRef(null);

  /* ── fetch messages ─────────────────────────────────────────── */
  const fetchMessages = useCallback(async (silent = false) => {
    if (!silent) setLoadingMsgs(true);
    try {
      const base = role === "employee" ? "/api/employee/tickets" : "/api/customer/tickets";
      const res = await fetch(
        apiUrl(`${base}/${encodeURIComponent(ticketId)}/messages`),
        { headers: authHeader() }
      );
      if (!res.ok) throw new Error("Failed");
      const data = await res.json();
      setMessages(data.messages || []);
    } catch {
      // silently ignore poll errors
    } finally {
      if (!silent) setLoadingMsgs(false);
    }
  }, [ticketId, role, authHeader]);

  // Initial load — runs once on mount / ticket change
  useEffect(() => {
    fetchMessages(false);
  }, [fetchMessages]);

  // Polling — stops while a modal is open, resumes when it closes
  useEffect(() => {
    if (paused) return;
    pollRef.current = setInterval(() => fetchMessages(true), 5000);
    return () => clearInterval(pollRef.current);
  }, [fetchMessages, paused]);

  /* ── scroll to bottom on new messages ─────────────────────── */
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [messages]);

  /* ── send message ───────────────────────────────────────────── */
  const send = async (content = sanitizeText(text.trim(), 5000)) => {
    if (!content || sending || disabled) return;
    setError("");
    setSending(true);
    setShowQuick(false);

    // Optimistic update
    const optimistic = {
      _id:       `opt-${Date.now()}`,
      senderRole: role,
      body:      content,
      createdAt: new Date().toISOString(),
      _optimistic: true,
    };
    setMessages(prev => [...prev, optimistic]);
    setText("");

    try {
      const base = role === "employee" ? "/api/employee/tickets" : "/api/customer/tickets";
      const csrf = await getCsrfToken();
      const res = await fetch(
        apiUrl(`${base}/${encodeURIComponent(ticketId)}/messages`),
        {
          method: "POST",
          headers: {
            ...authHeader(),
            "Content-Type": "application/json",
            ...(csrf ? { "X-CSRF-Token": csrf } : {}),
          },
          body: JSON.stringify({ body: content }),
        }
      );
      if (!res.ok) throw new Error("Failed to send message.");
      await fetchMessages(true);
    } catch (e) {
      setError(e.message || "Could not send message.");
      // Remove optimistic bubble on failure
      setMessages(prev => prev.filter(m => !m._optimistic));
    } finally {
      setSending(false);
    }
  };

  const handleKey = (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); }
  };

  /* ── group messages by sender runs ─────────────────────────── */
  const grouped = messages.reduce((acc, msg, i) => {
    const prev = messages[i - 1];
    const sameRun = prev && prev.senderRole === msg.senderRole;
    if (!sameRun) acc.push([]);
    acc[acc.length - 1].push(msg);
    return acc;
  }, []);

  return (
    <div className="tc-root">
      {/* Header */}
      <div className="tc-header">
        <div className="tc-header-left">
          <div className="tc-header-icon">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
          </div>
          <span className="tc-header-title">Ticket Conversation</span>
        </div>
      </div>

      {/* Message list */}
      <div className="tc-list" ref={listRef}>
        {loadingMsgs ? (
          <div className="tc-state-center">
            <div className="tc-spinner"/>
            <span>Loading conversation…</span>
          </div>
        ) : messages.length === 0 ? (
          <div className="tc-state-center">
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"
              strokeLinejoin="round" style={{ opacity: 0.3 }}>
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
            </svg>
            <span>No messages yet.{role === "customer" ? " Send a follow-up below." : " Respond to the customer below."}</span>
          </div>
        ) : (
          grouped.map((run, ri) => {
            const isOwn = run[0].senderRole === role;
            const isEmp = run[0].senderRole === "employee";
            return (
              <div key={ri} className={`tc-run ${isOwn ? "tc-run--own" : "tc-run--other"}`}>

                <div className="tc-bubbles">
                  {!isOwn && (
                    <span className="tc-sender-label">
                      {isEmp ? "Support Agent" : "Customer"}
                    </span>
                  )}
                  {run.map((msg, bi) => (
                    <div key={msg._id || bi}
                      className={`tc-bubble ${isOwn ? "tc-bubble--own" : "tc-bubble--other"} ${msg._optimistic ? "tc-bubble--sending" : ""}`}
                    >
                      <span className="tc-bubble-text">{msg.body}</span>
                    </div>
                  ))}
                  <span className="tc-time">{formatTime(run[run.length - 1].createdAt)}</span>
                </div>

              </div>
            );
          })
        )}

        {sending && (
          <div className="tc-run tc-run--own">
            <div className="tc-bubbles">
              <div className="tc-bubble tc-bubble--own tc-bubble--typing">
                <span className="tc-dot-anim"><span/><span/><span/></span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Quick-reply chips (employee only) */}
      {role === "employee" && showQuick && (
        <div className="tc-quick-tray">
          <div className="tc-quick-label">Quick replies</div>
          <div className="tc-quick-chips">
            {QUICK_REPLIES_EMPLOYEE.map((qr, i) => (
              <button
                key={i}
                type="button"
                className="tc-quick-chip"
                onClick={() => send(qr)}
              >
                {qr}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="tc-error">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
            <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/>
            <line x1="12" y1="16" x2="12.01" y2="16"/>
          </svg>
          {error}
        </div>
      )}

      {/* Input bar */}
      <div className={`tc-input-bar ${disabled ? "tc-input-bar--disabled" : ""}`}>
        {role === "employee" && !disabled && (
          <button
            type="button"
            className={`tc-quick-btn ${showQuick ? "tc-quick-btn--active" : ""}`}
            onClick={() => setShowQuick(p => !p)}
            title="Quick replies"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
              stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/>
            </svg>
          </button>
        )}

        <textarea
          ref={inputRef}
          className="tc-textarea"
          rows={1}
          placeholder={
            disabled
              ? "This ticket is resolved — conversation is closed."
              : role === "customer"
              ? "Send a follow-up message…"
              : "Respond to customer…"
          }
          value={text}
          disabled={disabled || sending}
          onChange={e => setText(e.target.value)}
          onKeyDown={handleKey}
        />

        <button
          type="button"
          className="tc-send-btn"
          disabled={!text.trim() || sending || disabled}
          onClick={() => send()}
          title="Send"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
    </div>
  );
}