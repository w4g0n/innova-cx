import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./AboutUs.css";
import novaLogo from "../../assets/nova-logo.png";

/* ─── Icons ─── */
const ICONS = {
  mail: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="4" width="20" height="16" rx="2"/>
      <path d="M2 7l10 7 10-7"/>
    </svg>
  ),
  close: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round">
      <path d="M6 6l12 12M18 6 6 18"/>
    </svg>
  ),
};

/* ─────────────────────────────────────────────────
   PIPELINE DATA  (all 14 agents, full info)
───────────────────────────────────────────────── */
const LAYERS = [
  {
    id: "entry", label: "User Entry", color: "#22d3ee", num: "01",
    tagline: "How a request enters the system",
    agents: [
      {
        id: "chatbot",
        name: "Chatbot Agent - Nova", 
        model: "Qwen",
        desc: "Nova - The first touchpoint for every user. Handles inquiries using the knowledge base and seamlessly starts formal ticketing when an issue needs escalation beyond a quick answer.", 
        inputs: ["User message", "Knowledge base context"],
        outputs: ["Direct answer  or ticket handoff"], 
        cond: null,
      },
      {
        id: "transcriber",
        name: "Transcriber Agent",
        model: "Whisper",
        desc: "Converts audio complaint recordings into clean text via live transcription. The user confirms the transcript on-screen before it proceeds, ensuring accuracy before anything is analysed downstream.", 
        inputs: ["Audio recording"],
        outputs: ["Transcribed ticket text"],
        cond: "AUDIO-ONLY",
      },
      {
        id: "ticket-gate",
        name: "Ticket Creation Gate",
        model: "Rule-based",
        desc: "The single entry point for all ticket creation, whether from Nova or the form. Structures the incoming data into a standardised ticket payload, sets Ticket_Status = Open, and fires the orchestration pipeline, for AI processing.", 
        inputs: ["User data + ticket details", "Optional attachment"],
        outputs: ["Ticket payload", "Ticket_Status = Open"],
        cond: null,
      },
    ],
  },
  {
    id: "control", label: "Control Layer", color: "#fb923c", num: "02",
    tagline: "The brain that coordinates everything",
    agents: [
      {
        id: "orchestrator",
        name: "Controller / Orchestrator",
        model: "LangChain",
        desc: "The central nervous system of InnovaCX. Coordinates all downstream agents in the correct sequence using LangChain, passes outputs between them, and returns the completed ticket - with Priority, SLA, department, and assigned employee - to the Ticket Creation Gate.", 
        inputs: ["Ticket payload"],
        outputs: ["Fully enriched execution state"], 
        cond: null,
      },
    ],
  },
  {
    id: "signal", label: "Signal Extraction", color: "#fbbf24", num: "03",
    tagline: "Understanding the complaint content",
    agents: [
      {
        id: "classification",
        name: "Subject Generation Agent",
        model: "DeBERTa NLI",
        desc: "Determines whether the ticket is a complaint or an inquiry so the system can follow the correct workflow.",
        inputs: ["Ticket details"],
        outputs: ["Subject"],
        cond: null,
      },
      {
        id: "classification",
        name: "Classification Agent",
        model: "DeBERTa NLI",
        desc: "Determines whether the ticket is a Complaint or an Inquiry if the type wasn't already specified at submission. Bypassed entirely when the type is already known.",
        inputs: ["Ticket details"],
        outputs: ["Ticket_Type (complaint / inquiry)"],
        cond: "SKIPPED-IF-SET",
      },
      {
        id: "sentiment",
        name: "Sentiment Analysis Agent",
        model: "RoBERTa",
        desc: "Reads the ticket text and produces a continuous sentiment score from −1 to +1, capturing tone, frustration, and urgency cues embedded in the language.",
        inputs: ["Ticket details"],
        outputs: ["Text_Sentiment (−1 to 1)"],
        cond: null,
      },
      {
        id: "audio-analysis",
        name: "Audio Analysis Agent",
        model: "Librosa",
        desc: "Processes the raw audio waveform of voice submissions to extract emotional tone directly from speech - pitch, energy, and zero-crossing rate - producing a sentiment score that text alone cannot capture.", 
        inputs: ["Audio features (energy, pitch, zero-crossing rate)"],
        outputs: ["Audio_Sentiment (−1 to 1)"],
        cond: "AUDIO-ONLY",
      },
      {
        id: "combiner",
        name: "Sentiment Combiner",
        model: "Fusion module",
        desc: "Fuses text and audio sentiment into a single unified score. With audio: (Audio × 0.5) + (Text × 0.5). Without audio: Text_Sentiment is used directly. Output is classified as Negative (< −0.25), Neutral, or Positive (> 0.25).",
        inputs: ["Text_Sentiment", "Audio_Sentiment (if available)"],
        outputs: ["Sentiment_Score (Negative / Neutral / Positive)"],
        cond: "AUDIO-ONLY",
      },
      {
        id: "feature",
        name: "Feature Engineering Agent",
        model: "DeBERTa NLI + DB lookup",
        desc: "The most signal-dense step in the pipeline. Uses a multi-head NLI model to infer five operational labels in parallel from the ticket text, cross-referenced against historical database records for recurrence detection.",
        inputs: ["Ticket details", "Historical ticket records"],
        outputs: ["safety_concern", "issue_severity", "issue_urgency", "business_impact", "is_recurring"],
        cond: null,
      },
    ],
  },
  {
    id: "decision", label: "Decision Layer", color: "#f87171", num: "04",
    tagline: "Turning signals into action",
    agents: [
      {
        id: "priority",
        name: "Prioritization Engine",
        model: "XGBoost",
        desc: "An XGBoost model trained on hard-set priority rules assigns a final Priority level - Critical, High, Medium, or Low - the moment a ticket is created. It never sees raw ticket text; it works entirely from the labels produced upstream. Crucially, it relearns from every employee rescore, so its judgements continuously align with team expectations.", 
        inputs: ["safety_concern", "issue_severity", "issue_urgency", "business_impact", "is_recurring", "Sentiment_Score", "Ticket_Type"],
        outputs: ["Priority (Critical / High / Medium / Low)"],
        cond: null,
      },
      {
        id: "sla",
        name: "SLA Automation", 
        model: "Policy engine",
        desc: "Maps Priority to concrete SLA deadlines. A heartbeat checks SLA status every 5 minutes - at 90% breach, the ticket auto-escalates, status changes to Escalated, and both the manager and employee are notified.", 
        inputs: ["Priority"],
        outputs: ["SLA targets", "Escalation rules", "Ticket_Status = Escalated (if triggered)"],
        cond: null,
      },
      {
        id: "routing",
        name: "Department Routing Agent",
        model: "DeBERTa NLI",
        desc: "A DeBERTa NLI model trained on synthetic tickets assigns a confidence score across all departments. Above 0.7, the ticket is auto-routed. Below that threshold, it goes to the manager approval screen. The model relearns from every manager decision.", 
        inputs: ["Ticket signals"],
        outputs: ["Department assignment", "Auto-routed or manager-reviewed"],
        cond: null,
      },
      {
        id: "assignment",
        name: "Employee Auto-Assignment",
        model: "Weighted algorithm",
        desc: "Once a department is confirmed, a workload-balancing algorithm assigns the ticket to the best available employee. It weights active tickets by priority (Critical = 8, High = 5, Medium = 3, Low = 1) and breaks ties by same-priority count, total tickets, last assignment time, then user ID. SLA tracking starts the moment assignment is complete.",
        inputs: ["Department", "Employee workload data"],
        outputs: ["Assigned employee", "SLA tracking begins"],
        cond: null,
      },
    ],
  },
  {
    id: "learning", label: "Learning Loop", color: "#a3e635", num: "05",
    tagline: "The system that improves with every ticket",
    agents: [
      {
        id: "resolution",
        name: "Suggested Resolution Agent",
        model: "Qwen",
        desc: "Generates a suggested resolution for the assigned employee at the moment of ticket creation. The employee can approve, edit, or reject it. The model learns from every one of those decisions, improving its suggestions over time.", 
        inputs: ["Ticket details", "Priority", "Past resolutions"],
        outputs: ["Suggested resolution steps"],
        cond: null,
      },
      {
        id: "feedback",
        name: "Employee Feedback Loop",
        model: "Continual learning",
        desc: "Closes the loop across the entire pipeline. Employee rescores feed back into the Prioritization Engine. Department corrections retrain the Routing Agent. Resolution edits improve the Suggested Resolution Agent. Every action makes the system sharper.",
        inputs: ["Rescore changes", "Routing corrections", "Resolution edits"],
        outputs: ["Retraining signals for Prioritizer, Router, and Resolver"],
        cond: "OPTIONAL",
      },
    ],
  },
];

const ALL_AGENTS = LAYERS.flatMap(l =>
  l.agents.map(a => ({ ...a, layerId: l.id, layerLabel: l.label, layerColor: l.color }))
);

/* ─────────────────────────────────────────────────
   FEATURES DATA  (SVG icons — no emojis)
───────────────────────────────────────────────── */
const FEATURES = [
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="7" y="7" width="10" height="10" rx="1"/>
        <path d="M7 9H4M7 12H4M7 15H4M17 9h3M17 12h3M17 15h3M9 7V4M12 7V4M15 7V4M9 17v3M12 17v3M15 17v3"/>
      </svg>
    ),
    title: "AI-Powered Prioritization",
    desc: "Our system analyzes every ticket using natural language processing and sentiment detection to identify urgent cases and bring the most critical issues to the top automatically.",
    detail: "An XGBoost Prioritization Engine assigns Critical, High, Medium, or Low priority the moment a ticket is created, working entirely from labels produced by a DeBERTa Feature Engineering Agent (urgency, severity, business impact, safety concern, recurrence) and a RoBERTa Sentiment Analysis Agent. The model relearns from every employee rescore.",
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="9" y="2" width="6" height="12" rx="3"/>
        <path d="M5 10a7 7 0 0 0 14 0M12 19v3M8 22h8"/>
      </svg>
    ),
    title: "Audio & Sentiment Analysis",
    desc: "Customer voice calls can be transcribed and analyzed for sentiment, giving support agents useful context before they begin handling the case.",
    detail: "Voice submissions are transcribed by a Whisper-powered Transcriber Agent. A Librosa-based Audio Analysis Agent then extracts emotional tone directly from the waveform. A Sentiment Combiner fuses the audio and text sentiment scores - weighted 50/50 - into a single signal that feeds directly into prioritization.",
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/>
      </svg>
    ),
    title: "Instant Escalation",
    desc: "High-priority tickets are automatically flagged and routed to the appropriate team, helping reduce delays and improve response times.",
    detail: "Once priority is assigned, an SLA Policy Engine maps it to deadline targets by priority level. A DeBERTa Department Routing Agent then assigns the ticket to the right team and employee,  auto-routing above a 0.7 confidence threshold, or sending to manager review below it. A 5-minute heartbeat monitors SLA breach proximity; at 90%, the ticket auto-escalates and both the manager and employee are notified so urgent cases are never left waiting.",
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="14" width="4" height="7"/>
        <rect x="10" y="9" width="4" height="12"/>
        <rect x="17" y="4" width="4" height="17"/>
      </svg>
    ),
    title: "Live Analytics Dashboard",
    desc: "Managers can view real-time insights into ticket volume, team performance, and customer sentiment through a centralized dashboard.",
    detail: "Managers access a dedicated analytics view with real-time ticket volume, team performance metrics, and sentiment trends. Employees see their personal queue with AI-generated resolution suggestions powered by a Suggested Resolution Agent that applies LLM reasoning and reinforcement learning from past outcomes.",
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
        <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
      </svg>
    ),
    title: "Seamless Integration",
    desc: "InnovaCX can integrate with existing CRM, helpdesk, or e-commerce platforms, allowing businesses to incorporate the system into their current workflows.",
    detail: "InnovaCX exposes a RESTful API secured with JWT authentication, enabling connection to existing CRM, helpdesk, and e-commerce systems. Webhook support allows external platforms to receive ticket events in real time, and the modular architecture ensures new integrations can be added without disrupting existing workflows.",
  },
  {
    icon: (
      <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <rect x="3" y="11" width="18" height="11" rx="2"/>
        <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
      </svg>
    ),
    title: "Enterprise-Grade Security",
    desc: "Customer data is protected through encryption, role-based access control, and detailed audit logs to support secure and responsible data handling.",
    detail: "Access is governed by role-based JWT tokens enforcing separate permissions for Customers, Employees, and Managers. All traffic is encrypted in transit via HTTPS, and every ticket action is recorded in a tamper-evident audit log. Sensitive data handling aligns with standard enterprise data protection practices.",
  },
];

/* ─────────────────────────────────────────────────
   TEAM
───────────────────────────────────────────────── */
const TEAM = [
  { name: "Majid Sharaf",   initials: "MS" },
  { name: "Hamad Subhi",    initials: "HS" },
  { name: "Hana Ayad",      initials: "HA" },
  { name: "Ali Al Maharif", initials: "AM" },
  { name: "Yara Saab",      initials: "YS" },
  { name: "Leen Naser",     initials: "LN" },
  { name: "Rami Alassi",    initials: "RA" },
];

/* ─── Privacy Modal ─── */
function PrivacyModal({ onClose }) {
  return (
    <div className="au-modal-overlay" onClick={onClose}>
      <div className="au-modal" onClick={e => e.stopPropagation()}>
        <button className="au-modal-close" onClick={onClose}>{ICONS.close}</button>
        <div className="au-modal-header">
          <div className="au-modal-tag">Legal</div>
          <h2 className="au-modal-title">Privacy &amp; Security Policy</h2>
          <p className="au-modal-sub">Effective January 1, 2026 · InnovaAI, Dubai CommerCity, UAE</p>
        </div>
        <div className="au-modal-body">
          {[
            { title: "1. Overview", body: "InnovaAI ('we', 'us', 'our') is committed to protecting the privacy and security of all data processed through the InnovaCX platform. This policy describes how we collect, use, store, and protect personal and operational data in accordance with applicable UAE laws and internationally recognised standards." },
            { title: "2. UAE Privacy Law Compliance", body: "InnovaAI operates in full compliance with the UAE Federal Decree-Law No. 45 of 2021 on the Protection of Personal Data (PDPL) and any applicable regulations issued by the UAE Data Office. We also adhere to Dubai International Financial Centre (DIFC) Data Protection Law No. 5 of 2020 where applicable. All data subjects within the UAE have the right to access, correct, delete, and restrict the processing of their personal data." },
            { title: "3. Security Standards", body: "Our security practices are aligned with ISO/IEC 27001 Information Security Management principles. Controls include: TLS 1.2+ encryption in transit (HTTPS enforced), AES-256 encryption at rest for sensitive fields, role-based access control (RBAC) via JWT tokens across all API endpoints with three tiers (Customer, Employee, Manager), and immutable tamper-evident audit logs on every ticket action." },
            { title: "4. Data We Collect", body: "We collect only the data necessary to operate the InnovaCX platform: customer support ticket content (text and audio), user account information, usage and interaction logs, and device or session metadata for security purposes. We do not sell personal data to third parties." },
            { title: "5. Data Retention", body: "Personal data and ticket records are retained for a maximum of 24 months from the date of creation, or as required by UAE law. Audio recordings are retained for 90 days unless subject to a legal hold. Upon expiry, data is securely deleted or anonymised." },
            { title: "6. Breach Notification", body: "In the event of a data breach posing risk to data subjects, InnovaAI will notify affected parties and relevant UAE regulatory authorities within the timeframes required by law, and no later than 72 hours after becoming aware of the breach." },
          ].map(s => (
            <div key={s.title} className="au-modal-section">
              <h3>{s.title}</h3>
              <p>{s.body}</p>
            </div>
          ))}
          <div className="au-modal-section">
            <h3>7. Contact</h3>
            <p>For privacy or security enquiries, or to exercise your data rights:</p>
            <div className="au-modal-contact">
              {ICONS.mail}
              <a href="mailto:innovacx.ai@gmail.com">innovacx.ai@gmail.com</a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────
   STARFIELD CANVAS  (subtle, fixed, behind everything)
───────────────────────────────────────────────── */
function Starfield() {
  const canvasRef = useRef(null);
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    let raf;
    const resize = () => {
      canvas.width  = window.innerWidth;
      canvas.height = window.innerHeight;
    };
    resize();

    const stars = Array.from({ length: 340 }, () => ({
      x:   Math.random(),
      y:   Math.random(),
      r:   Math.random() * 1.3 + 0.15,
      t:   Math.random() * Math.PI * 2,
      spd: Math.random() * 0.012 + 0.003,
      col: Math.random() > 0.82 ? "#c4b5fd"
         : Math.random() > 0.6  ? "#e9d5ff"
         : "#ffffff",
    }));

    const shooters = Array.from({ length: 4 }, (_, i) => ({
      active: false,
      timer:  80 + i * 160 + Math.random() * 200,
      x: 0, y: 0, alpha: 0, len: 0, spd: 0, angle: 0,
    }));

    const draw = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      stars.forEach(s => {
        s.t += s.spd;
        const a = Math.max(0.05, 0.25 + Math.sin(s.t) * 0.48);
        ctx.globalAlpha = a;
        ctx.fillStyle   = s.col;
        ctx.beginPath();
        ctx.arc(s.x * canvas.width, s.y * canvas.height, s.r, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.globalAlpha = 1;

      shooters.forEach(s => {
        s.timer--;
        if (s.timer <= 0 && !s.active) {
          s.active = true; s.alpha = 1;
          s.x     = Math.random() * 0.6;
          s.y     = Math.random() * 0.45;
          s.len   = Math.random() * 160 + 70;
          s.spd   = Math.random() * 5 + 3.5;
          s.angle = Math.PI / 6 + (Math.random() - 0.5) * 0.35;
        }
        if (!s.active) return;
        s.x    += Math.cos(s.angle) * s.spd / canvas.width;
        s.y    += Math.sin(s.angle) * s.spd / canvas.height;
        s.alpha -= 0.014;
        if (s.alpha <= 0 || s.x > 1.05) {
          s.active = false;
          s.timer  = 200 + Math.random() * 400;
          return;
        }
        const sx = s.x * canvas.width, sy = s.y * canvas.height;
        const ex = (s.x - Math.cos(s.angle) * s.len / canvas.width)  * canvas.width;
        const ey = (s.y - Math.sin(s.angle) * s.len / canvas.height) * canvas.height;
        const g  = ctx.createLinearGradient(sx, sy, ex, ey);
        g.addColorStop(0,   "#e9d5ff");
        g.addColorStop(0.4, "#c084fc");
        g.addColorStop(1,   "transparent");
        ctx.save();
        ctx.globalAlpha = s.alpha * 0.75;
        ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(ex, ey);
        ctx.strokeStyle = g; ctx.lineWidth = 1.5; ctx.stroke();
        ctx.beginPath(); ctx.arc(sx, sy, 1.8, 0, Math.PI * 2);
        ctx.fillStyle = "#fff"; ctx.fill();
        ctx.restore();
      });

      raf = requestAnimationFrame(draw);
    };
    draw();
    window.addEventListener("resize", resize);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); };
  }, []);
  return <canvas ref={canvasRef} className="au-starfield" />;
}

/* ─────────────────────────────────────────────────
   SCROLL REVEAL HOOK
───────────────────────────────────────────────── */
function useReveal() {
  useEffect(() => {
    const els = document.querySelectorAll(".au-reveal");
    const obs = new IntersectionObserver(
      entries => entries.forEach(e => { if (e.isIntersecting) e.target.classList.add("visible"); }),
      { threshold: 0.1 }
    );
    els.forEach(el => obs.observe(el));
    return () => obs.disconnect();
  }, []);
}

/* ─────────────────────────────────────────────────
   COUNTER
───────────────────────────────────────────────── */
function Counter({ end, suffix = "", start }) {
  const [v, setV] = useState(0);
  useEffect(() => {
    if (!start) return;
    let cur = 0;
    const step = () => {
      cur += end / 55;
      if (cur >= end) { setV(end); return; }
      setV(Math.floor(cur));
      requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }, [start, end]);
  return <>{v.toLocaleString()}{suffix}</>;
}

/* ─────────────────────────────────────────────────
   FEATURE CARD
───────────────────────────────────────────────── */
function FeatureCard({ icon, title, desc, detail, delay }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="au-feat au-reveal" style={{ "--rd": `${delay}ms` }}>
      <div className="au-feat-icon">{icon}</div>
      <h3 className="au-feat-title">{title}</h3>
      <p className="au-feat-desc">{desc}</p>
      {detail && (
        <>
          <button className="au-feat-toggle" onClick={() => setOpen(o => !o)}>
            {open ? "Show less ↑" : "How we do it ↓"}
          </button>
          {open && <div className="au-feat-detail">{detail}</div>}
        </>
      )}
    </div>
  );
}

/* ─────────────────────────────────────────────────
   PIPELINE SECTION
───────────────────────────────────────────────── */
function Pipeline() {
  const [activeLayer, setActiveLayer] = useState(LAYERS[0].id);
  const [activeAgent, setActiveAgent] = useState(ALL_AGENTS[0]);

  const layer       = LAYERS.find(l => l.id === activeLayer);
  const layerAgents = ALL_AGENTS.filter(a => a.layerId === activeLayer);
  const globalIdx   = ALL_AGENTS.findIndex(a => a.id === activeAgent.id);

  const selectLayer = (id) => {
    setActiveLayer(id);
    const first = ALL_AGENTS.find(a => a.layerId === id);
    if (first) setActiveAgent(first);
  };

  const selectAgent = (agent) => {
    setActiveAgent(agent);
    setActiveLayer(agent.layerId);
  };

  return (
    <section className="au-section" id="pipeline">
      <div className="au-reveal">
        <div className="au-label">How It Works</div>
        <h2 className="au-h2">InnovaCX <em>Agent Pipeline</em></h2>
        <p className="au-pipeline-intro-text">
          InnovaCX runs a 14-agent pipeline across five phases, from the moment a customer
          submits a request to a resolved, learned-from outcome. Select a phase and explore
          each agent&apos;s role, model, inputs, and outputs.
        </p>
      </div>

      {/* Phase tabs */}
      <div className="au-phase-pills au-reveal" style={{ "--rd": "0.1s" }}>
        {LAYERS.map(l => (
          <button
            key={l.id}
            className={`au-phase-pill${activeLayer === l.id ? " active" : ""}`}
            style={{ "--pc": l.color }}
            onClick={() => selectLayer(l.id)}
          >
            <span className="au-phase-pill-num" style={{ color: l.color }}>{l.num}</span>
            <span className="au-phase-pill-dot" style={{ background: l.color }} />
            {l.label}
          </button>
        ))}
      </div>

      {/* Phase tagline */}
      <div className="au-phase-tagline au-reveal" style={{ "--rd": "0.14s" }}>
        <span className="au-phase-tagline-bar" style={{ background: layer.color }} />
        <span style={{ color: layer.color, fontWeight: 700, marginRight: 8 }}>{layer.label}</span>
        <span>{layer.tagline}</span>
      </div>

      {/* Workspace */}
      <div className="au-pipeline-workspace au-reveal" style={{ "--rd": "0.18s" }}>

        {/* Left — agent list */}
        <div className="au-agent-list">
          <div className="au-agent-list-head">
            <div className="au-agent-list-accent" style={{ background: layer.color }} />
            <span className="au-agent-list-name" style={{ color: layer.color }}>{layer.label}</span>
            <span className="au-agent-list-count">
              {layerAgents.length} agent{layerAgents.length !== 1 ? "s" : ""}
            </span>
          </div>

          <div className="au-agent-rows">
            {layerAgents.map((agent, i) => {
              const isActive = activeAgent.id === agent.id;
              const isLast   = i === layerAgents.length - 1;
              return (
                <React.Fragment key={agent.id}>
                  <div className="au-agent-entry">
                    {/* Spine */}
                    <div className="au-agent-spine">
                      <div
                        className="au-agent-spine-dot"
                        style={isActive ? { background: `${layer.color}22`, borderColor: layer.color, boxShadow: `0 0 12px ${layer.color}` } : {}}
                      >
                        <div
                          className="au-agent-spine-dot-inner"
                          style={{ background: layer.color, opacity: isActive ? 1 : 0.4, boxShadow: isActive ? `0 0 6px ${layer.color}` : "none" }}
                        />
                      </div>
                      {!isLast && (
                        <div
                          className="au-agent-spine-line"
                          style={{ background: isActive ? `${layer.color}44` : undefined }}
                        />
                      )}
                    </div>

                    {/* Button */}
                    <button
                      className={`au-agent-btn${isActive ? " active" : ""}`}
                      style={{ "--ac": layer.color }}
                      onClick={() => selectAgent(agent)}
                    >
                      <div className="au-agent-btn-name">{agent.name}</div>
                      <div className="au-agent-btn-model">{agent.model}</div>
                      {agent.cond && (
                        <span className={`au-agent-cond au-cond-${agent.cond.toLowerCase().replace(/-/g,"")}`}>
                          {agent.cond}
                        </span>
                      )}
                    </button>
                  </div>

                  {!isLast && (
                    <div className="au-agent-entry" style={{ paddingTop: 0, paddingBottom: 0 }}>
                      <div className="au-agent-spine">
                        <div
                          className="au-agent-spine-line"
                          style={{ minHeight: 6, background: isActive ? `${layer.color}33` : undefined }}
                        />
                      </div>
                      <div style={{ flex: 1 }} />
                    </div>
                  )}
                </React.Fragment>
              );
            })}
          </div>

          {/* Cross-layer nav */}
          <div className="au-agent-crossnav">
            <button
              className="au-crossnav-btn"
              disabled={globalIdx === 0}
              onClick={() => { const prev = ALL_AGENTS[globalIdx - 1]; selectAgent(prev); }}
            >
              ← Prev agent
            </button>
            <span className="au-crossnav-pos">
              {globalIdx + 1} / {ALL_AGENTS.length}
            </span>
            <button
              className="au-crossnav-btn"
              disabled={globalIdx === ALL_AGENTS.length - 1}
              onClick={() => { const next = ALL_AGENTS[globalIdx + 1]; selectAgent(next); }}
            >
              Next agent →
            </button>
          </div>
        </div>

        {/* Right — detail card */}
        <div className="au-agent-detail" key={activeAgent.id} style={{ "--ac": activeAgent.layerColor }}>
          <div
            className="au-detail-glow"
            style={{ background: `radial-gradient(ellipse at 50% -20%, ${activeAgent.layerColor}, transparent 68%)` }}
          />

          <div className="au-detail-head">
            <div className="au-detail-phase" style={{ color: activeAgent.layerColor }}>
              {activeAgent.layerLabel}
            </div>
            <h3 className="au-detail-name">{activeAgent.name}</h3>
            <div className="au-detail-model-chip">
              <span className="au-detail-model-lbl">MODEL</span>
              {activeAgent.model}
            </div>
            {activeAgent.cond && (
              <div className="au-detail-cond">{activeAgent.cond}</div>
            )}
          </div>

          <div className="au-detail-body">
            <p className="au-detail-desc">{activeAgent.desc}</p>

            <div className="au-detail-io">
              <div className="au-io-block au-io-in">
                <div className="au-io-head">Inputs</div>
                <ul className="au-io-list">
                  {activeAgent.inputs.map((x, i) => <li key={i}>{x}</li>)}
                </ul>
              </div>
              <div className="au-io-block au-io-out">
                <div className="au-io-head">Outputs</div>
                <ul className="au-io-list">
                  {activeAgent.outputs.map((x, i) => <li key={i}>{x}</li>)}
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Legend */}
      <div className="au-pipe-legend au-reveal" style={{ "--rd": "0.22s" }}>
        {[
          { dot: "#fbbf24", text: "AUDIO-ONLY — runs for voice submissions only" },
          { dot: "#fbbf24", text: "SKIPPED-IF-SET — bypassed if already provided" },
          { dot: "#a3e635", text: "OPTIONAL — feedback-loop dependent" },
        ].map(({ dot, text }) => (
          <div key={text} className="au-pipe-leg-chip">
            <div className="au-pipe-leg-dot" style={{ background: dot }} />
            {text}
          </div>
        ))}
      </div>
    </section>
  );
}

/* ─────────────────────────────────────────────────
   MAIN COMPONENT
───────────────────────────────────────────────── */
const HERO_WORDS = ["Intelligent", "Empathetic", "Precise", "Instant"];

export default function AboutUs() {
  const navigate = useNavigate();

  // Hero word cycle
  const [wordIdx, setWordIdx] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setWordIdx(i => (i + 1) % HERO_WORDS.length), 2500);
    return () => clearInterval(id);
  }, []);

  // Mouse parallax for blobs
  const [mouse, setMouse] = useState({ x: 0, y: 0 });
  useEffect(() => {
    const fn = e => setMouse({ x: e.clientX, y: e.clientY });
    window.addEventListener("mousemove", fn);
    return () => window.removeEventListener("mousemove", fn);
  }, []);

  // Stats counter trigger
  const statsRef = useRef(null);
  const [statsOn, setStatsOn] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(
      ([e]) => { if (e.isIntersecting) setStatsOn(true); },
      { threshold: 0.2 }
    );
    if (statsRef.current) obs.observe(statsRef.current);
    return () => obs.disconnect();
  }, []);

  // Modal + contact state
  const [showPrivacy, setShowPrivacy] = useState(false);
  const [showContact, setShowContact] = useState(false);

  // Scroll reveal
  useReveal();

  return (
    <div className="au-page">
      <Starfield />
      <div className="au-nebula" />

      {/* Parallax blobs */}
      <div
        className="au-blob au-blob-1"
        style={{ transform: `translate(${mouse.x * 0.01}px, ${mouse.y * 0.01}px)` }}
      />
      <div
        className="au-blob au-blob-2"
        style={{ transform: `translate(${-mouse.x * 0.007}px, ${-mouse.y * 0.007}px)` }}
      />

      {/* ── NAV ── */}
      <nav className="au-nav">
        <div className="au-nav-logo" onClick={() => navigate("/")} role="button" tabIndex={0}>
          <img src={novaLogo} alt="InnovaAI" />
        </div>
        <button className="au-back-btn" onClick={() => navigate("/")}>
          ← Back to Home
        </button>
      </nav>

      {/* ══════════════════════════════════
          HERO
      ══════════════════════════════════ */}
      <section className="au-hero">
        <div className="au-hero-badge">
          InnovaAI · Dubai CommerCity
        </div>

        <h1 className="au-hero-title">
          Customer Support,
          <span className="au-hero-title-grad">
            <span key={wordIdx} className="au-word-in">{HERO_WORDS[wordIdx]}</span>
          </span>
        </h1>

        <p className="au-hero-sub">
          InnovaCX is a multi-agent AI platform that analyses text and voice complaints,
          detects emotion and urgency, then automatically prioritises and routes every ticket
          to the right team in real time.
        </p>

        <div className="au-hero-ctas">
          <a href="#mission"  className="au-btn-primary">Our Mission</a>
          <a href="#pipeline" className="au-btn-ghost">See the Pipeline →</a>
        </div>
      </section>

      {/* ══════════════════════════════════
          MISSION
      ══════════════════════════════════ */}
      <section className="au-section" id="mission">
        <div className="au-mission-grid">
          <div>
            <div className="au-label au-reveal">Our Purpose</div>
            <h2 className="au-h2 au-reveal" style={{ "--rd": "0.07s" }}>
              Built to Make <em>Every Customer</em><br />Feel Heard
            </h2>
            <p className="au-body au-reveal" style={{ "--rd": "0.14s" }}>
              InnovaCX is an AI-powered customer experience platform developed by
              InnovaAI - a team of engineers and designers focused on improving how
              businesses connect with their customers. By combining natural language
              processing, sentiment analysis, and intelligent routing, the platform helps
              businesses quickly identify important customer issues, prioritize urgent cases,
              and ensure that no complaint is overlooked.
            </p>
            <p className="au-body au-reveal" style={{ "--rd": "0.2s" }}>
              Operating within the Dubai CommerCity ecosystem, InnovaCX supports 
              e-commerce businesses, logistics providers, and retail brands by helping their
              customer support teams manage complaints more efficiently. The platform acts
              as an AI assistant that works alongside support teams to analyze incoming
              issues, highlight urgent cases, and help ensure that customers receive timely
              responses.
            </p>
          </div>

          {/* Orbit visual */}
          <div className="au-orbit-wrap au-reveal" style={{ "--rd": "0.18s" }}>
            <div className="au-orbit-ring au-ring-1" />
            <div className="au-orbit-ring au-ring-2" />
            <div className="au-orbit-ring au-ring-3" />
            <div className="au-orbit-center">InnovaCX</div>
            {["Sentiment", "Audio Analysis", "Text Analysis", "Ticket Prioritization", "SLA Monitoring", "Chatbot"].map((lbl, i) => (
              <div key={lbl} className="au-orbit-node" style={{ "--oi": i }}>{lbl}</div>
            ))}
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════
          FEATURES
      ══════════════════════════════════ */}
      <section className="au-section" id="features">
        <div className="au-features-intro">
          <div className="au-label au-reveal">What We Do</div>
          <h2 className="au-h2 au-reveal" style={{ "--rd": "0.07s" }}>
            Everything Your Support<br />Team <em>Needs</em>
          </h2>
        </div>
        <div className="au-features-grid">
          {FEATURES.map((f, i) => (
            <FeatureCard key={i} {...f} delay={i * 60} />
          ))}
        </div>
      </section>

      {/* ══════════════════════════════════
          PIPELINE
      ══════════════════════════════════ */}
      <Pipeline />

      {/* ══════════════════════════════════
          STATS
      ══════════════════════════════════ */}
      <section className="au-section" ref={statsRef}>
        <div className="au-stats-header">
          <div className="au-label au-reveal">Real Impact</div>
          <h2 className="au-h2 au-reveal" style={{ "--rd": "0.07s" }}>
            Numbers that <em>matter</em>
          </h2>
        </div>
        <div className="au-stats-grid">
          {[
            { end: 98,   suffix: "%",  label: "Triage Accuracy",   note: "of tickets correctly classified and prioritised on first pass" },
            { end: 40,   suffix: "%",  label: "Faster Resolution",  note: "reduction in first-response time for Critical tickets" },
            { end: 3,    suffix: "×",  label: "Throughput Gain",    note: "more tickets handled per agent per shift" },
            { end: 0,    suffix: "",   label: "Missed Complaints",  note: "every complaint is captured, categorised, and routed" },
          ].map((s, i) => (
            <div key={i} className="au-stat au-reveal" style={{ "--rd": `${i * 80}ms` }}>
              <div className="au-stat-num">
                <Counter end={s.end} suffix={s.suffix} start={statsOn} />
              </div>
              <div className="au-stat-lbl">{s.label}</div>
              <div className="au-stat-note">{s.note}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ══════════════════════════════════
          BUSINESS VALUE
      ══════════════════════════════════ */}
      <section className="au-section">
        <div className="au-value-grid">
          <div>
            <div className="au-label au-reveal">Business Value</div>
            <h2 className="au-h2 au-reveal" style={{ "--rd": "0.07s" }}>
              Turn Support Costs Into a<br /><em>Competitive Advantage</em>
            </h2>
            <p className="au-body au-reveal" style={{ "--rd": "0.14s" }}>
              Inefficient customer support can lead to lost customers, wasted agent time, and poor reviews.
              InnovaCX helps businesses manage support more intelligently by identifying important issues
              faster and organizing incoming requests more effectively.
              
            </p>
            <ul className="au-value-list">
              {[
                "Identify and prioritise the cases that matter most before they escalate.",
                "Automated ticket analysis and routing eliminate manual sorting overhead.",
                "Support teams can focus on solving problems, not managing queues.",
                "Faster responses and better prioritisation create more consistent customer experiences.",
                "Handle growing ticket volumes without proportionally increasing headcount.",
              ].map((item, i) => (
                <li key={i} className="au-reveal" style={{ "--rd": `${0.18 + i * 0.07}s` }}>
                  <span className="au-value-bullet" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <div className="au-value-card au-reveal" style={{ "--rd": "0.2s" }}>
            <div className="au-vc-tag">Projected Impact</div>
            <div className="au-vc-fig">40%</div>
            <div className="au-vc-sub">
              average reduction in first-response time<br />for Critical tickets
            </div>
            <div className="au-vc-rows">
              <div className="au-vc-row"><span>Triage Accuracy</span><strong>98%</strong></div>
              <div className="au-vc-row"><span>Throughput Gain</span><strong>3×</strong></div>
              <div className="au-vc-row"><span>Missed Complaints</span><strong>0</strong></div>
              <div className="au-vc-row"><span>Agent Time Saved</span><strong>~30%</strong></div>
              <div className="au-vc-row"><span>Integration Time</span><strong>Days, not months</strong></div>
            </div>
          </div>
        </div>
      </section>

      {/* ══════════════════════════════════
          TEAM
      ══════════════════════════════════ */}
      <section className="au-section">
        <div className="au-team-header">
          <div className="au-label au-reveal">The People Behind It</div>
          <h2 className="au-h2 au-reveal" style={{ "--rd": "0.07s" }}>
            Meet <em>Team InnovaAI</em>
          </h2>
        </div>
        <div className="au-team-grid">
          {TEAM.map((m, i) => (
            <div key={i} className="au-team-card au-reveal" style={{ "--rd": `${i * 65}ms` }}>
              <div className="au-team-avatar">{m.initials}</div>
              <div className="au-team-name">{m.name}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ══════════════════════════════════
          CTA
      ══════════════════════════════════ */}
      <section className="au-cta">
        <h2 className="au-cta-h">
          Ready to Experience<br /><em>Smarter Support?</em>
        </h2>
        <p className="au-cta-p">
          Submit a ticket, chat with Nova, or explore the dashboard
          your team&apos;s new AI co-pilot is ready.
        </p>
        <div style={{ display: "flex", gap: 14, justifyContent: "center", flexWrap: "wrap" }}>
          <button className="au-btn-primary" onClick={() => navigate("/customer")}>
            Get Started
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>
          <button className="au-btn-ghost" onClick={() => navigate("/login")}>Log In →</button>
        </div>
      </section>

      {/* ── FOOTER ── */}
      <footer className="au-footer">
        <p>© 2026 InnovaAI · Dubai CommerCity</p>
        <div className="au-footer-links">
          <span onClick={() => setShowPrivacy(true)}>Privacy Policy</span>
          <span>Terms of Use</span>
          <div className="au-contact-wrap">
            <span onClick={() => setShowContact(c => !c)}>Contact</span>
            {showContact && (
              <div className="au-contact-drop">
                {ICONS.mail}
                <a href="mailto:innovacx.ai@gmail.com">innovacx.ai@gmail.com</a>
              </div>
            )}
          </div>
        </div>
      </footer>

      {showPrivacy && <PrivacyModal onClose={() => setShowPrivacy(false)} />}
    </div>
  );
}
