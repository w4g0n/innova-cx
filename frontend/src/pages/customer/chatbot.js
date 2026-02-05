import { useState, useRef, useEffect } from "react";

export default function useNovaChatbot({ onGoToForm } = {}) {
  const listRef = useRef(null);

  // stages: start | inquiry | done
  const [stage, setStage] = useState("start");
  const [hasChosenType, setHasChosenType] = useState(false);
  const [text, setText] = useState("");
  const [messages, setMessages] = useState([]);

  // ---------- GREETING ----------
  useEffect(() => {
    setMessages([
      {
        id: `b-${Date.now()}`,
        from: "bot",
        text: "Hi! I’m Nova. How can I help you today?",
      },
    ]);
  }, []);

  // ---------- HELPERS ----------
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

  // ---------- BACKEND CALL ----------
  const chatbotBaseUrl =
    import.meta.env.VITE_CHATBOT_BASE_URL || "http://localhost:8001";

  const sendToChatbot = async (message) => {
    const res = await fetch(`${chatbotBaseUrl}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        mode: "inquiry",
      }),
    });

    if (!res.ok) {
      throw new Error("Chatbot API failed");
    }

    const data = await res.json();
    return data.reply;
  };

  // ---------- TYPE SELECT ----------
  const handleSelect = (type) => {
    setHasChosenType(true);

    if (type === "complaint") {
      pushBot("Opening the complaint form below…");
      setStage("complaint");
      onGoToForm?.("Complaint");
      return;
    }

    if (type === "inquiry") {
      pushBot("Sure — what can I help you with?");
      setStage("inquiry");
    }
  };

  // ---------- SEND ----------
  const handleSend = async (value) => {
    const t = value.trim();
    if (!t || stage !== "inquiry") return;

    pushUser(t);
    setText("");

    const typingId = `b-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      { id: typingId, from: "bot", text: "…" },
    ]);

    try {
      const reply = await sendToChatbot(t);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === typingId ? { ...m, text: reply } : m
        )
      );
    } catch (err) {
      console.error(err);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === typingId
            ? { ...m, text: "Sorry — the chatbot service is unavailable." }
            : m
        )
      );
    }
  };

  return {
    listRef,
    messages,
    text,
    setText,
    stage,
    hasChosenType,
    handleSelect,
    handleSend,
  };
}
