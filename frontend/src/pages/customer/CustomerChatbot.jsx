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
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);
  const [isRecording, setIsRecording] = useState(false);

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
  const [hasChosenType, setHasChosenType] = useState(false);
  const [text, setText] = useState("");

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

  // ===============================
  // Selection logic
  // ===============================
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
    }
  };

  // ===============================
  // Send message (FINAL TEXT ONLY)
  // ===============================
  const handleSend = (e) => {
    e.preventDefault();

    const t = text.trim();
    if (!t) return;

    pushUser(t);
    setText("");

    if (stage === "complaintChoice") {
      if (t.toLowerCase().includes("form")) {
        pushBot("No problem — taking you to the complaint form now.");
        setTimeout(() => goToForm("Complaint"), 350);
        return;
      }

      pushBot(
        "Okay — please describe the complaint in one or two sentences. Include any key details."
      );
      setStage("start");
      return;
    }

    if (stage === "inquiry") {
      pushBot(
        "Thanks — for this demo, I’ll log your inquiry and suggest using the form if you want a tracked ticket."
      );
      setStage("start");
      return;
    }

    pushBot(
      "Thanks — I can help with that. If you want to submit a tracked request, you can also use “Fill a form instead”."
    );
  };

  // ===============================
  // Mic / Whisper integration
  // ===============================
  const handleMicClick = async () => {
    if (!isRecording) {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      chunksRef.current = [];
      const recorder = new MediaRecorder(stream, {
        mimeType: "audio/mp4"
      });
      mediaRecorderRef.current = recorder;

      recorder.ondataavailable = (e) => {
        chunksRef.current.push(e.data);
      };

      recorder.onstop = async () => {
        const blob = new Blob(chunksRef.current, { type: "audio/mp4" });

        const formData = new FormData();
        formData.append("audio", blob, "mic.mp4");

        const res = await fetch("http://localhost:3001/transcribe", {
          method: "POST",
          body: formData,
        });

        const data = await res.json();
        setText(data.transcript); // editable draft
      };

      recorder.start();
      setIsRecording(true);
      return;
    }

    mediaRecorderRef.current.stop();
    setIsRecording(false);
  };

  // ===============================
  // JSX
  // ===============================
  return (
    <Layout role="customer">
      <div className="custChatPage">
        <div className="custChatTop">
          <PageHeader title="Chatbot" subtitle="Chat with Nova or submit a form anytime." />

          <div className="custChatTopActions">
            <button className="softPillBtn" onClick={() => navigate("/customer")}>
              Back to Home
            </button>
            <button className="softPillBtn" onClick={() => goToForm()}>
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
                  <button className="custQuickBtn" onClick={() => handleSelect("complaint")}>
                    Complaint
                  </button>
                  <button className="custQuickBtn" onClick={() => handleSelect("inquiry")}>
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
              <button
                type="button"
                className={`custMicBtn ${isRecording ? "recording" : ""}`}
                onClick={handleMicClick}
                aria-label="Record audio"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <path d="M12 14a3 3 0 0 0 3-3V6a3 3 0 0 0-6 0v5a3 3 0 0 0 3 3Z" stroke="currentColor" strokeWidth="1.8" />
                  <path d="M19 11a7 7 0 0 1-14 0" stroke="currentColor" strokeWidth="1.8" />
                  <path d="M12 18v3" stroke="currentColor" strokeWidth="1.8" />
                  <path d="M8 21h8" stroke="currentColor" strokeWidth="1.8" />
                </svg>
              </button>

              <textarea
                className="custInput"
                value={text}
                rows={1}
                placeholder="Type or speak your message…"
                onChange={(e) => {
                  setText(e.target.value);
                  e.target.style.height = "auto";
                  e.target.style.height = `${e.target.scrollHeight}px`;
                }}
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
