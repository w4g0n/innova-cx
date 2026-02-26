import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./AboutUs.css";
import novaLogo from "../../assets/nova-logo.png";

/* ─── Animated counter hook ─── */
function useCounter(target, duration = 2000, start = false) {
  const [count, setCount] = useState(0);
  useEffect(() => {
    if (!start) return;
    let startTime = null;
    const step = (timestamp) => {
      if (!startTime) startTime = timestamp;
      const progress = Math.min((timestamp - startTime) / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      setCount(Math.floor(ease * target));
      if (progress < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [start, target, duration]);
  return count;
}

/* ─── Intersection observer hook ─── */
function useInView(threshold = 0.15) {
  const ref = useRef(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setInView(true); },
      { threshold }
    );
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [threshold]);
  return [ref, inView];
}

/* ─── Stat card ─── */
function StatCard({ value, suffix, label, delay, inView }) {
  const count = useCounter(value, 2200, inView);
  return (
    <div className="au-stat-card" style={{ animationDelay: `${delay}ms` }}>
      <div className="au-stat-number">
        {inView ? count.toLocaleString() : 0}{suffix}
      </div>
      <div className="au-stat-label">{label}</div>
    </div>
  );
}

/* ─── Feature card ─── */
function FeatureCard({ icon, title, desc, delay }) {
  const [ref, inView] = useInView();
  return (
    <div
      ref={ref}
      className={`au-feature-card ${inView ? "au-fade-up" : ""}`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="au-feature-icon">{icon}</div>
      <h3 className="au-feature-title">{title}</h3>
      <p className="au-feature-desc">{desc}</p>
    </div>
  );
}

export default function AboutUs() {
  const navigate = useNavigate();

  /* hero text cycle */
  const heroWords = ["Intelligent", "Fast", "Empathetic", "Precise"];
  const [wordIdx, setWordIdx] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setWordIdx((i) => (i + 1) % heroWords.length), 2400);
    return () => clearInterval(id);
  }, []);

  /* sections in-view */
  const [missionRef, missionInView] = useInView();
  const [statsRef, statsInView] = useInView();
  const [whyRef, whyInView] = useInView();
  const [teamRef, teamInView] = useInView();

  /* parallax blob on mouse */
  const [mouse, setMouse] = useState({ x: 0, y: 0 });
  useEffect(() => {
    const move = (e) => setMouse({ x: e.clientX, y: e.clientY });
    window.addEventListener("mousemove", move);
    return () => window.removeEventListener("mousemove", move);
  }, []);

  const features = [
    {
      icon: "🧠",
      title: "AI-Powered Prioritization",
      desc: "Our engine analyses every ticket using NLP and sentiment scoring to surface the most critical cases first — automatically.",
    },
    {
      icon: "🎙️",
      title: "Audio & Sentiment Analysis",
      desc: "Voice calls are transcribed and emotionally scored in real-time, giving agents context before they even pick up.",
    },
    {
      icon: "⚡",
      title: "Instant Escalation",
      desc: "High-severity tickets skip the queue and land with the right team within seconds, slashing resolution time dramatically.",
    },
    {
      icon: "📊",
      title: "Live Analytics Dashboard",
      desc: "Managers get a real-time view of team performance, ticket flow, and customer satisfaction — all in one place.",
    },
    {
      icon: "🔗",
      title: "Seamless Integration",
      desc: "Plugs into your existing CRM, helpdesk, or e-commerce platform with minimal setup and zero downtime.",
    },
    {
      icon: "🔒",
      title: "Enterprise-Grade Security",
      desc: "End-to-end encryption, role-based access, and full audit logs keep your customer data safe and compliant.",
    },
  ];

  const team = [
    { name: "Majid Sharaf" },
    { name: "Hamad Subhi" },
    { name: "Hana Ayad" },
    { name: "Ali Al Maharif" },
    { name: "Yara Saab" },
    { name: "Leen Naser" },
    { name: "Rami Alassi" },
  ];

  return (
    <div className="au-page">
      {/* ── Navbar ── */}
      <nav className="au-nav">
        <div className="au-nav-logo" onClick={() => navigate("/customer")} role="button" tabIndex={0}>
          <img src={novaLogo} alt="InnovaAI" />
        </div>
        <button className="au-back-btn" onClick={() => navigate("/customer")}>
          ← Back to Home
        </button>
      </nav>

      {/* ── Hero ── */}
      <section className="au-hero">
        {/* animated blobs */}
        <div
          className="au-blob au-blob-1"
          style={{ transform: `translate(${mouse.x * 0.012}px, ${mouse.y * 0.012}px)` }}
        />
        <div
          className="au-blob au-blob-2"
          style={{ transform: `translate(${-mouse.x * 0.008}px, ${-mouse.y * 0.008}px)` }}
        />
        <div className="au-blob au-blob-3" />

        <div className="au-hero-content">
          <div className="au-hero-badge">InnovaCX · Dubai CommerCity</div>
          <h1 className="au-hero-title">
            Customer Support,<br />
            <span className="au-hero-accent">
              <span key={wordIdx} className="au-word-spin">{heroWords[wordIdx]}</span>
            </span>
          </h1>
          <p className="au-hero-sub">
            We built InnovaCX to transform how businesses handle customer support —
            replacing guesswork with intelligence, and delays with instant action.
          </p>
          <div className="au-hero-ctas">
            <a href="#mission" className="au-cta-primary">Discover Our Mission</a>
            <a href="#why" className="au-cta-ghost">Why InnovaCX?</a>
          </div>
        </div>

        <div className="au-hero-scroll-hint">
          <span className="au-scroll-dot" />
        </div>
      </section>

      {/* ── Mission ── */}
      <section className="au-section au-mission" id="mission" ref={missionRef}>
        <div className={`au-mission-inner ${missionInView ? "au-fade-up" : ""}`}>
          <div className="au-section-tag">Our Purpose</div>
          <h2 className="au-section-title">Built to Make <em>Every Customer</em> Feel Heard</h2>
          <p className="au-mission-body">
            InnovaCX is an AI-powered customer experience platform developed by InnovaAI — a team of
            engineers and designers passionate about closing the gap between businesses and their customers.
            We combine natural language processing, sentiment analysis, and smart routing to ensure that
            no complaint goes unnoticed and no urgent case gets buried under the noise.
          </p>
          <p className="au-mission-body">
            Operating within the Dubai CommerCity ecosystem, InnovaCX serves e-commerce businesses,
            logistics providers, and retail brands — giving every support team the power of a dedicated
            AI co-pilot working around the clock.
          </p>
        </div>

        <div className="au-mission-visual">
          <div className="au-orbit-ring au-ring-1" />
          <div className="au-orbit-ring au-ring-2" />
          <div className="au-orbit-ring au-ring-3" />
          <div className="au-orbit-center">
            <span>InnovaCX</span>
          </div>
          {["Sentiment", "Audio Analysis", "Text Analysis", "Ticket Prioritization", "SLA Monitoring", "Chatbot"].map((label, i) => (
            <div
              key={label}
              className="au-orbit-node"
              style={{ "--orbit-i": i, "--orbit-total": 6 }}
            >
              {label}
            </div>
          ))}
        </div>
      </section>

      {/* ── Stats ── */}
      <section className="au-section au-stats-section" ref={statsRef}>
        <div className="au-section-tag" style={{ textAlign: "center" }}>By the Numbers</div>
        <h2 className="au-section-title" style={{ textAlign: "center" }}>
          Real Impact, Real Results
        </h2>
        <div className="au-stats-grid">
          <StatCard value={40}  suffix="%" label="Reduction in Average Response Time" delay={0}   inView={statsInView} />
          <StatCard value={3}   suffix="x"  label="Faster Critical Ticket Resolution"  delay={150} inView={statsInView} />
          <StatCard value={87}  suffix="%"  label="Customer Satisfaction Score"        delay={300} inView={statsInView} />
          <StatCard value={60}  suffix="%"  label="Decrease in Ticket Misrouting"      delay={450} inView={statsInView} />
        </div>
        <p className="au-stats-note">
          * Figures based on internal pilot deployments and comparable AI-driven support platforms.
        </p>
      </section>

      {/* ── Features ── */}
      <section className="au-section au-features-section" id="why" ref={whyRef}>
        <div className={`au-features-header ${whyInView ? "au-fade-up" : ""}`}>
          <div className="au-section-tag">What We Do</div>
          <h2 className="au-section-title">Everything Your Support Team Needs</h2>
        </div>
        <div className="au-features-grid">
          {features.map((f, i) => (
            <FeatureCard key={i} {...f} delay={i * 80} />
          ))}
        </div>
      </section>

      {/* ── Why choose / ROI ── */}
      <section className="au-section au-roi-section">
        <div className="au-roi-inner">
          <div className="au-roi-text">
            <div className="au-section-tag">Business Value</div>
            <h2 className="au-section-title">Turn Support Costs Into Revenue Drivers</h2>
            <p className="au-roi-body">
              Poor customer support costs businesses billions every year. Slow responses drive churn,
              misdirected tickets waste agent hours, and unhappy customers leave bad reviews. InnovaCX
              flips the equation.
            </p>
            <ul className="au-roi-list">
              <li><span className="au-roi-bullet" />Reduce churn by resolving high-value customer issues <strong>3× faster</strong></li>
              <li><span className="au-roi-bullet" />Cut operational costs with <strong>automated triage</strong> that replaces manual sorting</li>
              <li><span className="au-roi-bullet" />Boost agent productivity — more tickets closed per shift, <strong>less burnout</strong></li>
              <li><span className="au-roi-bullet" />Deliver <strong>measurable CSAT improvements</strong> within the first 30 days</li>
              <li><span className="au-roi-bullet" />Scale support capacity <strong>without scaling headcount</strong></li>
            </ul>
          </div>
          <div className="au-roi-card">
            <div className="au-roi-card-title">Estimated Annual Savings</div>
            <div className="au-roi-figure">AED 2.4M+</div>
            <div className="au-roi-card-sub">for a mid-size e-commerce operation (500 tickets/day)</div>
            <div className="au-roi-breakdown">
              <div className="au-roi-row"><span>Agent hours saved</span><strong>~18,000 hrs/yr</strong></div>
              <div className="au-roi-row"><span>Churn reduction value</span><strong>~AED 1.1M</strong></div>
              <div className="au-roi-row"><span>Escalation cost avoided</span><strong>~AED 640K</strong></div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Team ── */}
      <section className="au-section au-team-section" ref={teamRef}>
        <div className={`au-features-header ${teamInView ? "au-fade-up" : ""}`}>
          <div className="au-section-tag">The People Behind It</div>
          <h2 className="au-section-title">Meet Team InnovaAI</h2>
        </div>
        <div className="au-team-grid">
          {team.map((member, i) => (
            <div
              key={i}
              className={`au-team-card ${teamInView ? "au-fade-up" : ""}`}
              style={{ animationDelay: `${i * 100}ms` }}
            >
              <div className="au-team-avatar">
                {member.name.split(" ").map((w) => w[0]).join("").slice(0, 2)}
              </div>
              <div className="au-team-name">{member.name}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ── CTA Banner ── */}
      <section className="au-cta-banner">
        <h2 className="au-cta-banner-title">Ready to Experience Smarter Support?</h2>
        <p className="au-cta-banner-sub">
          Submit a ticket, chat with Nova, or explore the dashboard — your team's new AI co-pilot is ready.
        </p>
        <button className="au-cta-primary large" onClick={() => navigate("/customer")}>
          Get Started →
        </button>
      </section>

      {/* ── Footer ── */}
      <footer className="au-footer">
        <p>© 2026 InnovaAI · Dubai CommerCity</p>
        <div className="au-footer-links">
          <span>Privacy Policy</span>
          <span>Terms of Use</span>
          <span>Contact</span>
        </div>
      </footer>
    </div>
  );
}
