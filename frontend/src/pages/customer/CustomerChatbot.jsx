import { useEffect, useMemo, useRef, useState } from "react";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import { useNavigate } from "react-router-dom";
import { sendChatMessage } from "../../services/api";
import "./CustomerChatbot.css";

const BUTTON_TEXT = {
  create_ticket: "Create a Ticket",
  track_ticket: "Track My Ticket",
};

const BUTTON_MESSAGE = {
  create_ticket: "I want to create a new ticket",
  track_ticket: "I want to follow up on an existing ticket",
};

export default function CustomerChatbot() {
  const navigate = useNavigate();
  const listRef = useRef(null);

  const user = useMemo(() => {
    try {
      return JSON.parse(localStorage.getItem("user") || "{}");
    } catch {
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
  const [chatSessionId, setChatSessionId] = useState(null);
  const [actionButtons, setActionButtons] = useState([]);
  const [messages, setMessages] = useState([
    {
      id: "m1",
      from: "bot",
      text: `Hi ${nameFromEmail}! I’m Nova. How can I help you today?`,
    },
  ]);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, actionButtons]);

  const pushUser = (t) => {
    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, from: "user", text: t },
    ]);
  };

  const pushBot = (t) => {
    setMessages((prev) => [
      ...prev,
      { id: `b-${Date.now()}`, from: "bot", text: t },
    ]);
  };

  const goToForm = (prefillType) => {
    if (prefillType) {
      navigate(`/customer/fill-form?type=${encodeURIComponent(prefillType)}`);
      return;
    }
    navigate("/customer/fill-form");
  };

  const sendToChatbot = async (message) => {
    let sid = chatSessionId;
    if (!sid) {
      const initData = await sendChatMessage("__init__", {
        userId,
        sessionId: null,
      });
      sid = initData?.session_id || null;
      if (sid) {
        setChatSessionId(sid);
      }
    }

    const data = await sendChatMessage(message, {
      userId,
      sessionId: sid,
    });
    if (data?.session_id && data.session_id !== sid) {
      setChatSessionId(data.session_id);
    }
    return data;
  };

  const sendAndRender = async (message) => {
    pushUser(message);
    pushBot("…");

    const data = await sendToChatbot(message);
    const botText = data?.response || data?.reply || "I could not generate a response.";
    setMessages((prev) => [
      ...prev.slice(0, -1),
      {
        id: `b-${Date.now()}`,
        from: "bot",
        text: botText,
      },
    ]);
    setActionButtons(Array.isArray(data?.show_buttons) ? data.show_buttons : []);
  };

  const handleSelect = async (type) => {
    try {
      const message =
        type === "complaint"
          ? "I want to create a new ticket"
          : "I want to follow up on an existing ticket";
      await sendAndRender(message);
    } catch (err) {
      console.error(err);
      pushBot("Sorry — the chatbot service is unavailable right now.");
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    const t = text.trim();
    if (!t) return;

    setText("");
    try {
      await sendAndRender(t);
    } catch (err) {
      console.error(err);
      pushBot("Sorry — the chatbot service is unavailable right now.");
    }
  };

  const handleActionButton = async (button) => {
    const message = BUTTON_MESSAGE[button];
    if (!message) return;
    try {
      await sendAndRender(message);
    } catch (err) {
      console.error(err);
      pushBot("Sorry — the chatbot service is unavailable right now.");
    }
  };

  return (
    <Layout role="customer">
      <div className="custChatPage">
        <div className="custChatTop">
          <PageHeader
            title="Chatbot"
            subtitle="Chat with Nova or submit a form anytime."
          />
        </div>

        <section className="custChatShellV2">
          <div className="custChatPanelV2">
            <div className="custQuickTop">
              <div className="custQuickTopHint">Quick start:</div>
              <div className="custQuickTopBtns">
                <button onClick={() => handleSelect("complaint")}>Create Ticket</button>
                <button onClick={() => handleSelect("inquiry")}>Track Ticket</button>
                <button onClick={() => goToForm("Complaint")}>Open Form</button>
              </div>
            </div>

            <div className="custChatList" ref={listRef}>
              {messages.map((m) => (
                <div key={m.id} className={`custMsg custMsg--${m.from}`}>
                  <div className="custMsg__bubble">{m.text}</div>
                </div>
              ))}
            </div>

            {actionButtons.length > 0 && (
              <div className="custQuickTopBtns" style={{ marginTop: 10 }}>
                {actionButtons.map((btn) => (
                  <button key={btn} onClick={() => handleActionButton(btn)}>
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
              />
              <button type="submit" className="primaryPillBtn">
                Send
              </button>
            </form>
          </div>
        </section>
      </div>
    </Layout>
  );
}
