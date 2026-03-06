import { useState, useRef } from "react";
import { sendChatMessage } from "../../services/api";

export default function useNovaChatbot() {
  const listRef = useRef(null);
  const initialMessage = () => [
    {
      id: `b-${Date.now()}`,
      from: "bot",
      text: "Hi! I’m Nova. How can I help you today?",
    },
  ];

  const [text, setText] = useState("");
  const [messages, setMessages] = useState(initialMessage);
  const [sessionId, setSessionId] = useState(null);

  const user = (() => {
    try {
      return JSON.parse(localStorage.getItem("user") || "{}");
    } catch {
      return {};
    }
  })();
  // Support legacy/new user object shapes so chatbot always uses
  // the same identity that ticket APIs expect.
  const userId = user?.id || user?.user_id || user?.userId || "";

  const resetSession = () => {
    setText("");
    setMessages(initialMessage());
    setSessionId(null);
  };

  const pushUser = (t) => {
    setMessages((prev) => [
      ...prev,
      { id: `u-${Date.now()}`, from: "user", text: t },
    ]);
  };

  const sendToChatbot = async (message) => {
    if (!userId) {
      throw new Error("Missing authenticated user id for chatbot session");
    }
    let sid = sessionId;
    if (!sid) {
      const initData = await sendChatMessage("__init__", {
        userId,
        sessionId: null,
      });
      sid = initData?.session_id || null;
      if (sid) {
        setSessionId(sid);
      }
    }

    const data = await sendChatMessage(message, {
      userId,
      sessionId: sid,
    });
    if (data?.session_id && data.session_id !== sid) {
      setSessionId(data.session_id);
    }
    return data?.response || data?.reply || "";
  };

  const handleSend = async (value) => {
    const t = value.trim();
    if (!t) return;

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
    handleSend,
    resetSession,
  };
}
