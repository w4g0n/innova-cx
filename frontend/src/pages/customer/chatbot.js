import { useState, useRef } from "react";
import { sendChatMessage } from "../../services/api";

export default function useNovaChatbot({ onGoToForm } = {}) {
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

  const resetSession = () => {
    setText("");
    setMessages(initialMessage());
  };

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

  const sendToChatbot = async (message) => {
    const data = await sendChatMessage(message, "inquiry");
    return data.reply;
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
