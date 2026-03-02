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
      desc: "Our system analyzes every ticket using natural language processing and sentiment detection to identify urgent cases and bring the most critical issues to the top automatically.",
    },
    {
      icon: "🎙️",
      title: "Audio & Sentiment Analysis",
      desc: "Customer voice calls can be transcribed and analyzed for sentiment, giving support agents useful context before they begin handling the case.",
    },
    {
      icon: "⚡",
      title: "Instant Escalation",
      desc: "High-priority tickets are automatically flagged and routed to the appropriate team, helping reduce delays and improve response times.",
    },
    {
      icon: "📊",
      title: "Live Analytics Dashboard",
      desc: "Managers can view real-time insights into ticket volume, team performance, and customer sentiment through a centralized dashboard.",
    },
    {
      icon: "🔗",
      title: "Seamless Integration",
      desc: "InnovaCX can integrate with existing CRM, helpdesk, or e-commerce platforms, allowing businesses to incorporate the system into their current workflows.",
    },
    {
      icon: "🔒",
      title: "Enterprise-Grade Security",
      desc: "Customer data is protected through encryption, role-based access control, and detailed audit logs to support secure and responsible data handling.",
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
            InnovaCX is an AI-powered customer experience platform developed by InnovaAI - a team of
            engineers and designers focused on improving how businesses connect with their customers. 
            By combining natural language processing, sentiment analysis, and intelligent routing, the platform 
            helps businesses quickly identify important customer issues, prioritize urgent cases, and ensure that no complaint is overlooked.

          </p>
          <p className="au-mission-body">
            Operating within the Dubai CommerCity ecosystem, InnovaCX supports e-commerce businesses, 
            logistics providers, and retail brands by helping their customer support teams manage complaints
            more efficiently. The platform acts as an AI assistant that works alongside support teams to analyze 
            incoming issues, highlight urgent cases, and help ensure that customers receive timely responses.
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
            <h2 className="au-section-title">Turn Support Costs Into a Competitive Advantage</h2>
            <p className="au-roi-body">
              Inefficient customer support can lead to lost customers, wasted agent time, and poor reviews.
              InnovaCX helps businesses manage support more intelligently by identifying important issues faster
              and organizing incoming requests more effectively.
            </p>
            <ul className="au-roi-list">
              <li><span className="au-roi-bullet" />Identify and prioritize the cases that matter most before they escalate.</li>
              <li><span className="au-roi-bullet" />Automated ticket analysis and routing minimize manual sorting.</li>
              <li><span className="au-roi-bullet" />Support teams can focus on solving problems instead of managing queues.</li>
              <li><span className="au-roi-bullet" />Faster responses and better prioritization lead to more consistent support experiences.</li>
              <li><span className="au-roi-bullet" />Handle growing ticket volumes without proportionally increasing support staff.</li>
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
          Submit a ticket, chat with Nova, or explore the dashboard — your team’s new AI assistant is ready to help.
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
