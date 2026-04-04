import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import TicketConfirmPopup from "../../components/common/TicketConfirmPopup";
import { useNavigate } from "react-router-dom";
import { sendChatMessage } from "../../services/api";
import { safeParseUser, sanitizeText, sanitizeId } from "./sanitize";
import "./CustomerChatbot.css";

// "Complaint" renamed to "Agent Pipeline"
const BUTTON_TEXT = {
  create_ticket: "Create via Agent Pipeline",
  track_ticket: "Track My Ticket",
  confirm_ticket: "Confirm Ticket",
  edit_ticket: "Edit Details",
};

const BUTTON_MESSAGE = {
  create_ticket: "I want to create a new ticket",
  track_ticket: "I want to follow up on an existing ticket",
  confirm_ticket: "yes",
  edit_ticket: "no",
};

// Allowlist for action button keys returned by the server — never render unknown keys
const ALLOWED_BUTTONS = Object.keys(BUTTON_TEXT);

const SESSION_KEY = "chatbot_session_id";

export default function CustomerChatbot() {
  const navigate = useNavigate();
  const listRef = useRef(null);

  const user = useMemo(() => {
    try {
      // safeParseUser validates structure — rejects arrays / primitives from storage
      return safeParseUser(localStorage.getItem("user"));
    } catch {
      return {};
    }
  }, []);

  const userId = sanitizeId(user?.id, 64);

  const nameFromEmail = useMemo(() => {
    // sanitizeText prevents null-byte / overlong email from reaching split logic
    const email = sanitizeText(user?.email, 254).trim();
    if (!email.includes("@")) return "there";
    const raw = email.split("@")[0] || "";
    const cleaned = raw.replace(/[._-]+/g, " ").trim();
    if (!cleaned) return "there";
    return cleaned
      .split(" ")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
  }, [user]);

  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
  const [showResetConfirm, setShowResetConfirm] = useState(false);

  const [chatSessionId, setChatSessionId] = useState(() => {
    try {
      // Validate that the stored session ID only contains safe characters
      const raw = localStorage.getItem(SESSION_KEY) || null;
      return raw ? sanitizeId(raw, 128) : null;
    } catch {
      return null;
    }
  });

  useEffect(() => {
    try {
      if (chatSessionId) localStorage.setItem(SESSION_KEY, chatSessionId);
      else localStorage.removeItem(SESSION_KEY);
    } catch {
      // ignore storage write errors
    }
  }, [chatSessionId]);

  const [actionButtons, setActionButtons] = useState([]);
  const [messages, setMessages] = useState([
    {
      id: "m1",
      from: "bot",
      // nameFromEmail is already sanitized above
      text: `Hi ${nameFromEmail}! I'm Nova. How can I help you today?`,
    },
  ]);

  const [ticketPopup, setTicketPopup] = useState(null);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, actionButtons]);

  const pushUser = (t) => {
    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, from: "user", text: sanitizeText(t, 5000) },
    ]);
  };

  const pushBot = useCallback((t) => {
    setMessages((prev) => [
      ...prev,
      { id: `b-${Date.now()}`, from: "bot", text: sanitizeText(t, 5000) },
    ]);
  }, []);

  const goToForm = (prefillType) => {
    // sanitizeId prevents path traversal or injection in the query param
    const safeType = prefillType ? sanitizeId(prefillType, 32) : "";
    navigate(
      safeType
        ? `/customer/fill-form?type=${encodeURIComponent(safeType)}`
        : "/customer/fill-form"
    );
  };

  const initSession = useCallback(async () => {
    const initData = await sendChatMessage("__init__", { userId, sessionId: null });
    // Validate the session ID returned by the server before storing
    const newSid = initData?.session_id
      ? sanitizeId(String(initData.session_id), 128)
      : null;
    if (newSid) setChatSessionId(newSid);
    return newSid;
  }, [userId]);

  const sendToChatbot = useCallback(
    async (message) => {
      let sid = chatSessionId;
      if (!sid) sid = await initSession();

      try {
        const data = await sendChatMessage(message, { userId, sessionId: sid });
        if (data?.session_id) {
          const newSid = sanitizeId(String(data.session_id), 128);
          if (newSid && newSid !== sid) setChatSessionId(newSid);
        }
        return data;
      } catch (err) {
        if (
          err?.message?.includes("500") ||
          err?.message?.includes("404") ||
          err?.message?.includes("not found")
        ) {
          const newSid = await initSession();
          const data = await sendChatMessage(message, { userId, sessionId: newSid });
          if (data?.session_id) {
            const validated = sanitizeId(String(data.session_id), 128);
            if (validated && validated !== newSid) setChatSessionId(validated);
          }
          return data;
        }
        throw err;
      }
    },
    [chatSessionId, userId, initSession]
  );

  const sendAndRender = useCallback(
    async (message) => {
      pushUser(message);

      setMessages((prev) => [
        ...prev,
        { id: `typing-${Date.now()}`, from: "bot", text: "", isTyping: true },
      ]);

      const data = await sendToChatbot(message);

      // Sanitize bot response text from the server before rendering
      const rawText = data?.response || data?.reply || "I could not generate a response.";
      const botText = sanitizeText(rawText, 5000);

      setMessages((prev) => [
        ...prev.slice(0, -1),
        { id: `b-${Date.now()}`, from: "bot", text: botText },
      ]);

      // Only allow button keys that exist in our allowlist — discard unknown server-sent keys
      const rawButtons = Array.isArray(data?.show_buttons) ? data.show_buttons : [];
      const safeButtons = rawButtons.filter((b) => ALLOWED_BUTTONS.includes(String(b)));
      setActionButtons(safeButtons);

      if (data?.response_type === "ticket_created") {
        const ticketIdMatch = botText.match(/ticket ID is (CX-[A-Za-z0-9_-]{1,40})/i);
        setTicketPopup({
          // sanitizeId ensures ticketId only contains safe chars before it reaches a URL
          ticketId: ticketIdMatch ? sanitizeId(ticketIdMatch[1], 48) : null,
          isInquiry: false,
          replyText: botText,
        });
      }
    },
    [sendToChatbot]
  );

  const handleSelect = async (type) => {
    if (sending) return;
    setSending(true);

    try {
      const message =
        type === "complaint"
          ? "I want to create a new ticket"
          : "I want to follow up on an existing ticket";

      await sendAndRender(message);
    } catch (err) {
      console.error(err);
      pushBot("Sorry — the service is unavailable right now.");
    } finally {
      setSending(false);
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    const t = text.trim();
    if (!t || sending) return;

    setText("");
    setSending(true);

    try {
      await sendAndRender(t);
    } catch (err) {
      console.error(err);
      pushBot("Sorry — the service is unavailable right now.");
    } finally {
      setSending(false);
    }
  };

  const handleActionButton = async (button) => {
    // Double-check against allowlist at call time (belt-and-suspenders)
    if (!ALLOWED_BUTTONS.includes(button)) return;
    const message = BUTTON_MESSAGE[button];
    if (!message || sending) return;

    setSending(true);
    try {
      await sendAndRender(message);
    } catch (err) {
      console.error(err);
      pushBot("Sorry — the service is unavailable right now.");
    } finally {
      setSending(false);
    }
  };

  const handleResetConfirmed = () => {
    setText("");
    setChatSessionId(null);
    setActionButtons([]);
    setTicketPopup(null);
    setMessages([
      {
        id: `m-${Date.now()}`,
        from: "bot",
        text: `Hi ${nameFromEmail}! I'm Nova. How can I help you today?`,
      },
    ]);
    setShowResetConfirm(false);
  };

  return (
    <Layout role="customer">
      <div className="custChatPage">
        <div className="custChatTop">
          <PageHeader
            title="Nova Chat"
            subtitle="Chat with Nova or submit through the agent pipeline."
          />
        </div>

        <section className="custChatShellV2">
          <div className="custChatPanelV2">
            <div className="custQuickTop">
              <div className="custQuickTopHint">Quick start:</div>
              <div className="custQuickTopBtns">
                <button disabled={sending} onClick={() => handleSelect("complaint")}>
                  New Ticket
                </button>
                <button disabled={sending} onClick={() => handleSelect("inquiry")}>
                  Track Ticket
                </button>
                <button onClick={() => goToForm("Complaint")}>Agent Pipeline</button>
                <button
                  className="softPillBtn"
                  disabled={sending}
                  onClick={() => setShowResetConfirm(true)}
                >
                  New Conversation
                </button>
              </div>
            </div>

            <div className="custChatList" ref={listRef}>
              {messages.map((m) => (
                <div key={m.id} className={`custMsg custMsg--${m.from}`}>
                  <div className="custMsg__bubble">
                    {m.isTyping ? (
                      <span className="custTypingIndicator">
                        <span />
                        <span />
                        <span />
                      </span>
                    ) : (
                      m.text
                    )}
                  </div>
                </div>
              ))}
            </div>

            {actionButtons.length > 0 && (
              <div className="custQuickTopBtns" style={{ margin: "0 18px 12px" }}>
                {actionButtons.map((btn) => (
                  <button
                    key={btn}
                    disabled={sending}
                    onClick={() => handleActionButton(btn)}
                  >
                    {/* BUTTON_TEXT lookup — key is allowlisted, value is a static constant */}
                    {BUTTON_TEXT[btn] || btn}
                  </button>
                ))}
              </div>
            )}

            <form className="custComposer" onSubmit={handleSend}>
              <textarea
                id="chatbot-message"
                name="message"
                className="custInput"
                value={text}
                placeholder="Type your message..."
                onChange={(e) => {
                  // Cap input length client-side before it reaches state or the API
                  const val = e.target.value;
                  if (val.length <= 5000) setText(val);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend(e);
                  }
                }}
                disabled={sending}
                maxLength={5000}
              />
              <button type="submit" className="primaryPillBtn" disabled={sending}>
                Send
              </button>
            </form>
          </div>
        </section>
      </div>

      {ticketPopup && (
        <TicketConfirmPopup
          open
          ticketId={ticketPopup.ticketId}
          isInquiry={ticketPopup.isInquiry}
          replyText={ticketPopup.replyText}
          onClose={() => setTicketPopup(null)}
        />
      )}

      {showResetConfirm && (
        <div className="custConfirmOverlay">
          <div className="custConfirmModal">
            <div className="custConfirmIconWrap">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="1 4 1 10 7 10" />
                <path d="M3.51 15a9 9 0 1 0 .49-3.5" />
              </svg>
            </div>
            <p className="custConfirmTitle">Start a new conversation?</p>
            <p className="custConfirmBody">
              This will clear your current conversation and start fresh. This action cannot be undone.
            </p>
            <div className="custConfirmActions">
              <button
                className="softPillBtn"
                onClick={() => setShowResetConfirm(false)}
              >
                Cancel
              </button>
              <button
                className="primaryPillBtn"
                onClick={handleResetConfirmed}
              >
                Start New
              </button>
            </div>
          </div>
        </div>
      )}
    </Layout>
  );
}