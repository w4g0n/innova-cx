import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import TicketConfirmPopup from "../../components/common/TicketConfirmPopup";
import { useNavigate } from "react-router-dom";
import { sendChatMessage } from "../../services/api";
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

const SESSION_KEY = "chatbot_session_id";

export default function CustomerChatbot() {
  const navigate = useNavigate();
  const listRef = useRef(null);

  const user = useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem("user") || "{}");
    } catch {
      // If localStorage has bad JSON / is unavailable, fall back safely
      return {};
    }
  }, []);

  const userId = user?.id || "";

  const nameFromEmail = useMemo(() => {
    const email = (user?.email || "").trim();
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

  const [chatSessionId, setChatSessionId] = useState(() => {
    try {
      return localStorage.getItem(SESSION_KEY) || null;
    } catch {
      // localStorage may be blocked/unavailable in some browsers or privacy modes
      return null;
    }
  });

  useEffect(() => {
    try {
      if (chatSessionId) localStorage.setItem(SESSION_KEY, chatSessionId);
      else localStorage.removeItem(SESSION_KEY);
    } catch {
      // ignore storage write errors (e.g., blocked storage)
    }
  }, [chatSessionId]);

  const [actionButtons, setActionButtons] = useState([]);
  const [messages, setMessages] = useState([
    { id: "m1", from: "bot", text: `Hi ${nameFromEmail}! I'm Nova. How can I help you today?` },
  ]);

  const [ticketPopup, setTicketPopup] = useState(null);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, actionButtons]);

  const pushUser = (t) => {
    setMessages((prev) => [...prev, { id: `u-${Date.now()}`, from: "user", text: t }]);
  };

  const pushBot = useCallback((t) => {
    setMessages((prev) => [...prev, { id: `b-${Date.now()}`, from: "bot", text: t }]);
  }, []);

  const goToForm = (prefillType) => {
    navigate(
      prefillType
        ? `/customer/fill-form?type=${encodeURIComponent(prefillType)}`
        : "/customer/fill-form"
    );
  };

  const initSession = useCallback(async () => {
    const initData = await sendChatMessage("__init__", { userId, sessionId: null });
    const newSid = initData?.session_id || null;
    if (newSid) setChatSessionId(newSid);
    return newSid;
  }, [userId]);

  const sendToChatbot = useCallback(
    async (message) => {
      let sid = chatSessionId;
      if (!sid) sid = await initSession();

      try {
        const data = await sendChatMessage(message, { userId, sessionId: sid });
        if (data?.session_id && data.session_id !== sid) setChatSessionId(data.session_id);
        return data;
      } catch (err) {
        if (
          err?.message?.includes("500") ||
          err?.message?.includes("404") ||
          err?.message?.includes("not found")
        ) {
          const newSid = await initSession();
          const data = await sendChatMessage(message, { userId, sessionId: newSid });
          if (data?.session_id && data.session_id !== newSid) setChatSessionId(data.session_id);
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

      // Add typing placeholder
      setMessages((prev) => [...prev, { id: `typing-${Date.now()}`, from: "bot", text: "", isTyping: true }]);

      const data = await sendToChatbot(message);
      const botText = data?.response || data?.reply || "I could not generate a response.";

      // Replace typing placeholder with real bot response
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { id: `b-${Date.now()}`, from: "bot", text: botText },
      ]);

      setActionButtons(Array.isArray(data?.show_buttons) ? data.show_buttons : []);

      if (data?.response_type === "ticket_created") {
        const ticketIdMatch = botText.match(/ticket ID is (CX-[A-Za-z0-9_-]+)/i);
        setTicketPopup({
          ticketId: ticketIdMatch ? ticketIdMatch[1] : null,
          isInquiry: false,
          replyText: botText,
        });
      }
    },
    [sendToChatbot] // pushUser comes from state setter, pushBot not used here
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
                {/* Renamed "Open Form" → "Agent Pipeline" */}
                <button onClick={() => goToForm("Complaint")}>Agent Pipeline</button>
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
                  <button key={btn} disabled={sending} onClick={() => handleActionButton(btn)}>
                    {BUTTON_TEXT[btn] || btn}
                  </button>
                ))}
              </div>
            )}

            <form className="custComposer" onSubmit={handleSend}>
              <textarea
                className="custInput"
                value={text}
                placeholder="Type your message..."
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend(e);
                  }
                }}
                disabled={sending}
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
    </Layout>
  );
}
