import { useMemo, useRef, useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./CustomerLanding.css";
import dccLogo from "../../assets/dcc-logo.jpeg";

export default function CustomerLanding() {
  const navigate = useNavigate();

  const [isOpen, setIsOpen] = useState(false);
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

  const [messages, setMessages] = useState(() => [
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
    setMessages((prev) => {
      const copy = [...prev];
      if (copy[0]?.id === "m1") {
        copy[0] = {
          ...copy[0],
          text: `Hi ${nameFromEmail}! I’m Nova. How can I help you today?`,
        };
      }
      return copy;
    });
  }, [nameFromEmail]);

  useEffect(() => {
    const el = listRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, isOpen]);

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
        setTimeout(() => goToForm("Complaint"), 250);
        return;
      }
      pushBot(
        "Okay — please describe the complaint in one or two sentences. Include key details (location, time, what happened)."
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
      "Thanks — I can help with that. If you want to submit a tracked request, you can also use the form."
    );
  };

  return (
    <div className="dccWrap">
      {/* TOP NAV */}
      <header className="dccNav">
        <div className="dccNavLeft">
          <img className="dccLogoImg" src={dccLogo} alt="Dubai CommerCity" />
        </div>

        <nav className="dccNavCenter" aria-label="Primary">
          <button type="button" className="dccNavLink">
            Our Facilities
          </button>
          <button type="button" className="dccNavLink">
            Digital Ecosystem
          </button>
          <button type="button" className="dccNavLink">
            Newsroom
          </button>
          <button type="button" className="dccNavLink">
            About
          </button>
          <button type="button" className="dccNavLink">
            Contact Us
          </button>
          <button type="button" className="dccNavLink">
            Login
          </button>
        </nav>

        <div className="dccNavRight">
          <button type="button" className="dccIconBtn" aria-label="Search">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path
                d="M10.5 18a7.5 7.5 0 1 1 0-15 7.5 7.5 0 0 1 0 15Z"
                stroke="currentColor"
                strokeWidth="1.9"
              />
              <path
                d="M16.5 16.5 21 21"
                stroke="currentColor"
                strokeWidth="1.9"
                strokeLinecap="round"
              />
            </svg>
          </button>

          <button type="button" className="dccCtaBtn">
            Set up a Business
          </button>
        </div>
      </header>

      {/* MAIN PANEL */}
      <main className="dccMain">
        <section className="dccPanel">
          <div className="dccPanelInner">
            <div className="dccLeft">
              <p className="dccLeftText">
                Our team is here to guide you through
                <br />
                the process. Get in touch today to
                <br />
                discover how Dubai CommerCity can
                <br />
                help you establish and expand your
                <br />
                business with ease
              </p>
            </div>

            <div className="dccRight">
              <div className="dccGrid">
                <button type="button" className="dccTile">
                  <div className="dccTileTitle">The Setup Process</div>
                  <div className="dccTileNum">01</div>
                </button>

                <button type="button" className="dccTile">
                  <div className="dccTileTitle">Business Licenses</div>
                  <div className="dccTileNum">02</div>
                </button>

                <button type="button" className="dccTile">
                  <div className="dccTileTitle">FAQ</div>
                  <div className="dccTileNum">03</div>
                </button>

                <button type="button" className="dccTile">
                  <div className="dccTileTitle">Contact</div>
                  <div className="dccTileNum">04</div>
                </button>
              </div>
            </div>
          </div>

          <div className="dccBottomCtas">
            <button type="button" className="dccBottomBtn">
              Compare Options
            </button>
            <button type="button" className="dccBottomBtn">
              Enquiry Now
            </button>
          </div>
        </section>
      </main>

      {/* Chatbot widget button */}
      <button
        type="button"
        className="novaWidgetLauncher"
        onClick={() => setIsOpen(true)}
        aria-label="Open Nova Chat"
        title="Open Nova Chat"
      >
        <span className="novaWidgetDot" />
        Chat with Nova
      </button>

      {/* Popup widget */}
      {isOpen && (
        <div className="novaWidget">
          <div className="novaWidgetHeader">
            <div className="novaWidgetHeaderLeft">
              <div className="novaAvatar" />
              <div className="novaHeaderText">
                <div className="novaHeaderTitle">Nova</div>
                <div className="novaHeaderSub">AI Support Assistant</div>
              </div>
            </div>

            <div className="novaWidgetHeaderRight">
              <button
                type="button"
                className="novaIconBtn"
                onClick={() => navigate("/customer/chatbot")}
                aria-label="Expand"
                title="Expand to full page"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <path
                    d="M14 3h7v7"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                  <path
                    d="M10 21H3v-7"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                  <path
                    d="M21 3l-7 7"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                  <path
                    d="M3 21l7-7"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                </svg>
              </button>

              <button
                type="button"
                className="novaIconBtn"
                onClick={() => setIsOpen(false)}
                aria-label="Close"
                title="Close"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <path
                    d="M6 6l12 12M18 6 6 18"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                  />
                </svg>
              </button>
            </div>
          </div>

          <div className="novaWidgetBody">
            <div className="novaChatList" ref={listRef}>
              {messages.map((m) => (
                <div
                  key={m.id}
                  className={
                    m.from === "user" ? "novaMsg novaMsg--user" : "novaMsg novaMsg--bot"
                  }
                >
                  <div className="novaBubble">{m.text}</div>
                </div>
              ))}
            </div>

            {!hasChosenType && (
              <div className="novaQuickRow">
                <div className="novaQuickHint">Choose one to start:</div>
                <div className="novaQuickBtns">
                  <button
                    type="button"
                    className="novaQuickBtn"
                    onClick={() => handleSelect("complaint")}
                  >
                    Complaint
                  </button>
                  <button
                    type="button"
                    className="novaQuickBtn"
                    onClick={() => handleSelect("inquiry")}
                  >
                    Inquiry
                  </button>
                </div>
              </div>
            )}

            <form className="novaComposer" onSubmit={handleSend}>
              <input
                className="novaInput"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder="Type a message…"
              />
              <button type="submit" className="novaSendBtn">
                Send
              </button>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
