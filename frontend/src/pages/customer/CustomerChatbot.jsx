import { useEffect, useMemo, useRef, useState } from "react";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import { useNavigate } from "react-router-dom";
import "./CustomerChatbot.css";

export default function CustomerChatbot() {
  const navigate = useNavigate();
  const listRef = useRef(null);

  // ===============================
  // Whisper / Audio state
  // ===============================
  // ===============================
  // User info
  // ===============================
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
    const raw = email.split("@")[0] || "";
    const cleaned = raw.replace(/[._-]+/g, " ").trim();
    if (!cleaned) return "there";
    return cleaned
      .split(" ")
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");
  }, [user]);

  // ===============================
  // Chat state
  // ===============================
  const [stage, setStage] = useState("start"); 
  // start | inquiry | complaintChoice | done

  const [hasChosenType, setHasChosenType] = useState(false);
  const [text, setText] = useState("");

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
  }, [messages]);

  // ===============================
  // Helpers
  // ===============================
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

  // ===============================
  // Selection logic
  // ===============================
  const handleSelect = (type) => {
    setHasChosenType(true);

    if (type === "complaint") {
      pushBot(
        "Got it. You can submit the complaint here in chat, or you can fill a form instead. Which do you prefer?"
      );
      setStage("complaintChoice");
      return;
    }

    if (type === "inquiry") {
      pushBot("Sure — what can I help you with?");
      setStage("inquiry");
    }
  };

  // ===============================
  // CHATBOT API (Inquiry only)
  // ===============================
  const sendToChatbot = async (message) => {
    const res = await fetch("http://chatbot:8000/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        mode: "inquiry",
      }),
    });

    if (!res.ok) throw new Error("Chatbot API failed");

    const data = await res.json();
    return data.reply;
  };

  // ===============================
  // Send message
  // ===============================
  const handleSend = async (e) => {
    e.preventDefault();

    if (stage === "done") return;

    const t = text.trim();
    if (!t) return;

    pushUser(t);
    setText("");

    // ---------- INQUIRY (BACKEND ONLY) ----------
    if (stage === "inquiry") {
      try {
        pushBot("…");

        const realReply = await sendToChatbot(t);
        setMessages((prev) => [
          ...prev.slice(0, -1),
          {
            id: `b-${Date.now()}`,
            from: "bot",
            text: realReply,
          },
        ]);
      } catch (err) {
        console.error(err);
        pushBot("Sorry — the chatbot service is unavailable right now.");
      }
      return;
    }

    // ---------- COMPLAINT ----------
    if (stage === "complaintChoice") {
      if (t.toLowerCase().includes("form")) {
        pushBot("No problem — taking you to the complaint form now.");
        setTimeout(() => goToForm("Complaint"), 500);
        setStage("done");
        return;
      }

      pushBot(
        "Thanks for the details. Please submit this complaint using the form so it can be tracked properly."
      );
      setTimeout(() => goToForm("Complaint"), 700);
      setStage("done");
    }
  };

  // ===============================
  // JSX
  // ===============================
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
            {!hasChosenType && (
              <div className="custQuickTop">
                <div className="custQuickTopHint">
                  Choose one to get started:
                </div>
                <div className="custQuickTopBtns">
                  <button onClick={() => handleSelect("complaint")}>
                    Complaint
                  </button>
                  <button onClick={() => handleSelect("inquiry")}>
                    Inquiry
                  </button>
                </div>
              </div>
            )}

            <div className="custChatList" ref={listRef}>
              {messages.map((m) => (
                <div key={m.id} className={`custMsg custMsg--${m.from}`}>
                  <div className="custMsg__bubble">{m.text}</div>
                </div>
              ))}
            </div>

            <form className="custComposer" onSubmit={handleSend}>
              <textarea
                className="custInput"
                value={text}
                placeholder="Type or speak your message…"
                onChange={(e) => setText(e.target.value)}
                disabled={stage === "done"}
              />
              <button
                type="submit"
                className="primaryPillBtn"
                disabled={stage === "done"}
              >
                Send
              </button>
            </form>
          </div>
        </section>
      </div>
    </Layout>
  );
}
