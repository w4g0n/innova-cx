import { useState, useRef, useEffect } from "react";
import { sendChatMessage } from "../../services/api";

const SESSION_KEY = "chatbot_session_id";

export default function useNovaChatbot({ onGoToForm, onTicketCreated } = {}) {
  const listRef = useRef(null);
  const initialMessage = () => [
    {
      id: `b-${Date.now()}`,
      from: "bot",
      text: "Hi! I'm Nova. How can I help you today?",
    },
  ];

  const [text, setText] = useState("");
  const [messages, setMessages] = useState(initialMessage);
  const [sessionId, setSessionId] = useState(() => {
    try {
      return localStorage.getItem(SESSION_KEY) || null;
    } catch {
      return null;
    }
  });

  useEffect(() => {
    try {
      if (sessionId) localStorage.setItem(SESSION_KEY, sessionId);
      else localStorage.removeItem(SESSION_KEY);
    } catch {
      // ignore storage errors
    }
  }, [sessionId]);

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
    return {
      reply: data?.response || data?.reply || "",
      buttons: data?.show_buttons || [],
      responseType: data?.response_type || "",
    };
  };

  const handleSend = async (value) => {
    const t = value.trim();
    if (!t) return;

    pushUser(t);
    setText("");

    const typingId = `b-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      { id: typingId, from: "bot", typing: true },
    ]);

    try {
      const { reply, buttons, responseType } = await sendToChatbot(t);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === typingId
            ? { ...m, typing: false, text: reply, buttons }
            : m
        )
      );

      if (responseType === "ticket_created" && onTicketCreated) {
        const match = reply.match(/ticket ID is (CX-[A-Za-z0-9_-]+)/i);
        onTicketCreated({ ticketId: match ? match[1] : null, replyText: reply });
      }

      if (responseType === "go_to_form" && onGoToForm) {
        onGoToForm();
      }
    } catch (err) {
      console.error(err);
      setMessages((prev) =>
        prev.map((m) =>
          m.id === typingId
            ? { ...m, typing: false, text: "Sorry — the chatbot service is unavailable." }
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
