import { useNavigate } from "react-router-dom";
import novaLogo from "../assets/nova-logo.png";
import dccBg from "../assets/dcc-bg.png";
import "./PublicLanding.css";

const FEATURES = [
  {
    icon: "🧠",
    title: "Sentiment Analysis",
    desc: "Our AI reads the emotional tone of every complaint in real time, ensuring the most distressed customers are never left waiting.",
  },
  {
    icon: "🎯",
    title: "Smart Prioritisation",
    desc: "Tickets are automatically ranked by urgency and customer value so your team always works on what matters most.",
  },
  {
    icon: "🎙️",
    title: "Audio Intelligence",
    desc: "Voice complaints are transcribed and analysed instantly — capturing nuance that text alone can miss.",
  },
  {
    icon: "⚡",
    title: "Instant Resolution",
    desc: "AI-suggested resolutions cut average handling time dramatically, freeing your team for complex cases.",
  },
];

const STATS = [
  { value: "40%", label: "Faster resolution" },
  { value: "3×", label: "Complaint throughput" },
  { value: "98%", label: "Triage accuracy" },
];

export default function PublicLanding() {
  const navigate = useNavigate();

  return (
    <div className="pl-root">
      {/* ─── HERO ─────────────────────────────────────────────── */}
      <section
        className="pl-hero"
        style={{ backgroundImage: `url(${dccBg})` }}
      >
        <div className="pl-hero-overlay" />

        {/* NAV */}
        <nav className="pl-nav">
          <img src={novaLogo} alt="InnovaCX" className="pl-nav-logo" />

          <button
            className="pl-nav-login"
            onClick={() => navigate("/login")}
          >
            Log In
          </button>
        </nav>

        {/* HERO CONTENT */}
        <div className="pl-hero-body">
          <div className="pl-hero-eyebrow">Dubai CommerCity · AI-Powered CX</div>

          <h1 className="pl-hero-headline">
            <span className="pl-word pl-word--1">Transforming</span>
            <span className="pl-word pl-word--2">Customer</span>
            <span className="pl-word pl-word--3">Experience</span>
          </h1>

          <p className="pl-hero-sub">
            InnovaCX uses sentiment analysis, audio intelligence, and machine
            learning to route and resolve complaints faster than ever — so every
            customer feels heard.
          </p>

          <div className="pl-hero-actions">
            <button
              className="pl-btn-primary"
              onClick={() => navigate("/login")}
            >
              Get Started
            </button>
            <button
              className="pl-btn-ghost"
              onClick={() => navigate("/about")}
            >
              About Us
            </button>
          </div>

          {/* NOVA CTA */}
          <button
            className="pl-nova-pill"
            onClick={() => navigate("/login")}
            title="Chat with Nova — log in first"
          >
            <span className="pl-nova-dot" />
            <span>Chat with Nova AI</span>
            <span className="pl-nova-arrow">→</span>
          </button>
        </div>

        {/* FLOATING STATS */}
        <div className="pl-stats">
          {STATS.map((s, i) => (
            <div key={i} className="pl-stat" style={{ animationDelay: `${i * 0.15}s` }}>
              <span className="pl-stat-value">{s.value}</span>
              <span className="pl-stat-label">{s.label}</span>
            </div>
          ))}
        </div>

        {/* SCROLL HINT */}
        <div className="pl-scroll-hint">
          <span className="pl-scroll-line" />
        </div>
      </section>

      {/* ─── FEATURES ─────────────────────────────────────────── */}
      <section className="pl-features">
        <div className="pl-section-label">What We Do</div>
        <h2 className="pl-section-title">AI that works as hard as your team</h2>
        <p className="pl-section-sub">
          Four intelligent layers that ensure no complaint falls through the cracks.
        </p>

        <div className="pl-feature-grid">
          {FEATURES.map((f, i) => (
            <div key={i} className="pl-feature-card" style={{ animationDelay: `${i * 0.1}s` }}>
              <div className="pl-feature-icon">{f.icon}</div>
              <h3 className="pl-feature-title">{f.title}</h3>
              <p className="pl-feature-desc">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ─── FOOTER ───────────────────────────────────────────── */}
      <footer className="pl-footer">
        <img src={novaLogo} alt="InnovaCX" className="pl-footer-logo" />
        <div className="pl-footer-links">
          <button className="pl-footer-link" onClick={() => navigate("/about")}>About Us</button>
          <button className="pl-footer-link" onClick={() => navigate("/login")}>Log In</button>
        </div>
        <p className="pl-footer-copy">© 2026 Dubai CommerCity · InnovaCX</p>
      </footer>
    </div>
  );
}
