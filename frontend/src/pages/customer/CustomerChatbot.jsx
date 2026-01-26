import { useEffect, useMemo, useRef, useState } from "react";
import Layout from "../../components/Layout";
import PageHeader from "../../components/common/PageHeader";
import { useNavigate } from "react-router-dom";
import "./CustomerChatbot.css";

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

  const [stage, setStage] = useState("start");
  const [hasChosenType, setHasChosenType] = useState(false);

  const [messages, setMessages] = useState([
    {
      id: "m1",
      from: "bot",
      text: `Hi ${nameFromEmail}! I’m Nova. How can I help you today?`,
      ts: Date.now(),
    },
    {
      id: "m2",
      from: "bot",
      text: "Would you like to file a complaint or do you have an inquiry?",
      ts: Date.now() + 1,
    },
  ]);

  const [text, setText] = useState("");

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages]);

  const pushUser = (t) => {
    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, from: "user", text: t, ts: Date.now() },
    ]);
  };

  const pushBot = (t) => {
    setMessages((prev) => [
      ...prev,
      { id: `b-${Date.now()}`, from: "bot", text: t, ts: Date.now() },
    ]);
  };

  const goToForm = (prefillType) => {
    if (prefillType) {
      navigate(`/customer/fill-form?type=${encodeURIComponent(prefillType)}`);
      return;
    }
    navigate("/customer/fill-form");
  };

  const handleSelect = (type) => {
    setHasChosenType(true);

    if (type === "complaint") {
      pushUser("I want to raise a complaint.");
      pushBot(
        "Got it. You can submit the complaint here in chat, or you can fill a form instead. Which do you prefer?"
      );
      setStage("complaintChoice");
      return;
    }

    if (type === "inquiry") {
      pushUser("I want to raise an inquiry.");
      pushBot("Sure — tell me your question and I’ll try to help right away.");
      setStage("inquiry");
      return;
    }
  };

  const handleSend = (e) => {
    e.preventDefault();
    const t = text.trim();
    if (!t) return;

    pushUser(t);
    setText("");

    if (stage === "complaintChoice") {
      const lower = t.toLowerCase();
      if (lower.includes("form")) {
        pushBot("No problem — taking you to the complaint form now.");
        setTimeout(() => goToForm("Complaint"), 350);
        return;
      }
      pushBot(
        "Okay — please describe the complaint in one or two sentences. Include any key details (location, time, what happened)."
      );
      setStage("start");
      return;
    }

    if (stage === "inquiry") {
      pushBot(
        "Thanks — for this demo, I’ll log your inquiry and suggest using the form if you want a tracked ticket. Would you like to submit a form?"
      );
      setStage("start");
      return;
    }

    pushBot(
      "Thanks — I can help with that. If you want to submit a tracked request, you can also use “Fill a form instead”."
    );
  };

  return (
    <Layout role="customer">
      <div className="custChatPage">
        <div className="custChatTop">
          <PageHeader title="Chatbot" subtitle="Chat with Nova or submit a form anytime." />

          <div className="custChatTopActions">
            <button
              type="button"
              className="softPillBtn"
              onClick={() => navigate("/customer")}
            >
              Back to Home
            </button>

            <button type="button" className="softPillBtn" onClick={() => goToForm()}>
              Fill a form instead
            </button>
          </div>
        </div>

        <section className="custChatShellV2">
          <div className="custChatPanelV2">
            {!hasChosenType && (
              <div className="custQuickTop">
                <div className="custQuickTopHint">Choose one to get started:</div>
                <div className="custQuickTopBtns">
                  <button
                    type="button"
                    className="custQuickBtn"
                    onClick={() => handleSelect("complaint")}
                  >
                    Complaint
                  </button>
                  <button
                    type="button"
                    className="custQuickBtn"
                    onClick={() => handleSelect("inquiry")}
                  >
                    Inquiry
                  </button>
                </div>
              </div>
            )}

            <div className="custChatList" ref={listRef}>
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={m.from === "user" ? "custMsg custMsg--user" : "custMsg custMsg--bot"}
                >
                  <div className="custMsg__bubble">{m.text}</div>
                </div>
              ))}
            </div>

            <form className="custComposer" onSubmit={handleSend}>
              <button
                type="button"
                className="custMicBtn"
                onClick={() => alert("Mic UI is next step (demo).")}
                aria-label="Use microphone"
                title="Use microphone (demo)"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <path
                    d="M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3Z"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
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
                  <path
                    d="M8 21h8"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                </svg>
              </button>

              <input
                className="custInput"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Type your message…"
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
