import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import "./AboutUs.css";
import novaLogo from "../../assets/nova-logo.png";

const HERO_WORDS = ["Intelligent", "Fast", "Empathetic", "Precise"];

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
function FeatureCard({ icon, title, desc, detail, delay }) {
  const [ref, inView] = useInView();
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      ref={ref}
      className={`au-feature-card ${inView ? "au-fade-up" : ""}`}
      style={{ animationDelay: `${delay}ms` }}
    >
      <div className="au-feature-icon">{icon}</div>
      <h3 className="au-feature-title">{title}</h3>
      <p className="au-feature-desc">{desc}</p>
      {detail && (
        <>
          <button
            type="button"
            className="au-feature-toggle"
            onClick={() => setExpanded((p) => !p)}
          >
            {expanded ? "Show less ↑" : "How we do it ↓"}
          </button>
          {expanded && (
            <div className="au-feature-detail">
              <p>{detail}</p>
            </div>
          )}
        </>
      )}
    </div>
  );
}

/* ─── Pipeline Data ─── */
const PIPELINE_LAYERS = [
  {
    id: "entry",
    name: "User Entry",
    color: "#22d3ee",
    stages: [
      {
        id: "chatbot",
        agent: "Chatbot Agent",
        model: "Falcon 1B Instruct",
        desc: "Handles inquiries from the knowledge base and starts ticketing when an issue needs formal handling.",
        inputs: ["User message", "Knowledge base context"],
        outputs: ["Answer or ticket handoff"],
      },
      {
        id: "transcriber",
        agent: "Transcriber Agent",
        model: "Whisper",
        desc: "Transcribes voice submissions into text so audio and typed requests follow the same flow.",
        inputs: ["Audio_Log"],
        outputs: ["Details (transcribed text)"],
        conditionTag: "AUDIO-ONLY",
      },
      {
        id: "ticket-gate",
        agent: "Ticket Creation Gate",
        model: "Rule-based",
        desc: "Builds a structured ticket and triggers the orchestration pipeline.",
        inputs: ["User data + details", "Optional ticket fields"],
        outputs: ["Ticket payload", "Ticket_Status = Open"],
      },
    ],
  },
  {
    id: "control",
    name: "Control Layer",
    color: "#fb923c",
    stages: [
      {
        id: "orchestrator",
        agent: "Controller / Orchestrator",
        model: "LangChain",
        desc: "Coordinates all downstream agents and passes outputs between them.",
        inputs: ["Ticket payload", "Agent outputs"],
        outputs: ["Ordered execution state"],
      },
    ],
  },
  {
    id: "signal",
    name: "Signal Extraction",
    color: "#fbbf24",
    stages: [
      {
        id: "classification",
        agent: "Classification Agent",
        model: "Classifier",
        desc: "Classifies ticket type (complaint/inquiry) if not already provided.",
        inputs: ["Details"],
        outputs: ["Ticket_Type"],
        conditionTag: "SKIPPED-IF-SET",
      },
      {
        id: "sentiment",
        agent: "Sentiment Analysis Agent",
        model: "RoBERTa",
        desc: "Extracts text sentiment from written or transcribed details.",
        inputs: ["Details"],
        outputs: ["Text_Sentiment"],
      },
      {
        id: "feature",
        agent: "Feature Engineering Agent",
        model: "Classifiers + DB lookup",
        desc: "Builds operational signals like recurrence, urgency, severity, impact, and safety concerns. This is the guaranteed next step after sentiment analysis.",
        inputs: ["Details", "Historical records"],
        outputs: ["issue_urgency", "issue_severity", "business_impact", "safety_concern", "is_recurring"],
      },
      {
        id: "audio-analysis",
        agent: "Audio Analysis Agent",
        model: "Librosa",
        desc: "Derives audio sentiment from recorded voice submissions.",
        inputs: ["Audio_Log"],
        outputs: ["Audio_Sentiment"],
        conditionTag: "AUDIO-ONLY",
      },
      {
        id: "combiner",
        agent: "Sentiment Combiner",
        model: "Fusion module",
        desc: "Combines text and audio sentiment into a unified sentiment score when audio is provided.",
        inputs: ["Text_Sentiment", "Audio_Sentiment"],
        outputs: ["Sentiment_Score"],
        conditionTag: "AUDIO-ONLY",
      },
    ],
  },
  {
    id: "decision",
    name: "Decision Layer",
    color: "#f87171",
    stages: [
      {
        id: "priority",
        agent: "Prioritization Agent",
        model: "Fuzzy logic",
        desc: "Assigns final ticket priority from extracted signals.",
        inputs: ["Ticket signals"],
        outputs: ["Priority"],
      },
      {
        id: "sla",
        agent: "SLA",
        model: "Policy engine",
        desc: "Maps priority to SLA targets and escalation behavior.",
        inputs: ["Priority"],
        outputs: ["SLA level + deadlines"],
      },
      {
        id: "routing",
        agent: "Department Routing",
        model: "Rule routing",
        desc: "Routes the ticket to the correct department and assignee.",
        inputs: ["Ticket signals", "Routing rules"],
        outputs: ["Department + employee assignment"],
      },
    ],
  },
  {
    id: "learning",
    name: "Learning Loop",
    color: "#a3e635",
    stages: [
      {
        id: "resolution",
        agent: "Suggested Resolution Agent",
        model: "LLM + reinforcement learning",
        desc: "Proposes actionable resolution steps for the assigned employee.",
        inputs: ["Details", "Priority"],
        outputs: ["Suggested resolution"],
      },
      {
        id: "feedback",
        agent: "Employee Feedback Loop",
        model: "Continual learning",
        desc: "Uses employee outcomes to improve prioritization and resolution quality over time.",
        inputs: ["Rescore changes", "Employee resolution actions"],
        outputs: ["Retraining signals"],
        conditionTag: "OPTIONAL",
      },
    ],
  },
];

const PIPELINE_STAGES = PIPELINE_LAYERS.flatMap((layer) =>
  layer.stages.map((stage) => ({
    ...stage,
    layerId: layer.id,
    lane: layer.name,
    laneColor: layer.color,
  }))
);

/* ─── Pipeline sub-components ─── */
function PipelineNode({ stage, isActive, isCompact, relation, isKeyboardFocus, onClick }) {
  return (
    <button
      type="button"
      className={`au-pipeline-node ${isActive ? "is-active" : ""} ${isCompact ? "is-compact" : ""} ${relation === "upstream" ? "is-upstream" : ""} ${relation === "downstream" ? "is-downstream" : ""} ${relation === "unrelated" ? "is-unrelated" : ""} ${isKeyboardFocus ? "is-key-focus" : ""}`}
      onClick={onClick}
      aria-pressed={isActive}
      style={{ "--node-color": stage.laneColor }}
    >
      <span className="au-pipeline-lane" style={{ color: stage.laneColor }}>{stage.lane}</span>
      <span className="au-pipeline-agent">{stage.agent}</span>
      <span className="au-pipeline-model">{stage.model}</span>
    </button>
  );
}

function PipelineDetail({ stage, onPrev, onNext, isFirst, isLast }) {
  return (
    <article className="au-pipeline-detail" key={stage.id}>
      <div className="au-pipeline-detail-header">
        <div className="au-pipeline-detail-lane" style={{ color: stage.laneColor }}>
          {stage.lane}
        </div>
        <h3 className="au-pipeline-detail-title">{stage.agent}</h3>
        <div className="au-pipeline-detail-model">
          <span className="au-pipeline-model-label">MODEL</span>
          {stage.model}
        </div>
        {stage.conditionTag && <div className="au-pipeline-detail-condition">{stage.conditionTag}</div>}
      </div>

      <p className="au-pipeline-detail-desc">{stage.desc}</p>

      <div className="au-pipeline-io">
        <div className="au-pipeline-io-block au-pipeline-io-inputs">
          <h4>↘ Inputs</h4>
          <ul>
            {stage.inputs.map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        </div>
        <div className="au-pipeline-io-block au-pipeline-io-outputs">
          <h4>↗ Outputs</h4>
          <ul>
            {stage.outputs.map((item, i) => <li key={i}>{item}</li>)}
          </ul>
        </div>
      </div>

      <div className="au-pipeline-nav">
        <button type="button" className="au-pipeline-nav-btn" onClick={onPrev} disabled={isFirst}>
          ← Previous
        </button>
        <button type="button" className="au-pipeline-nav-btn" onClick={onNext} disabled={isLast}>
          Next →
        </button>
      </div>
    </article>
  );
}

export default function AboutUs() {
  const navigate = useNavigate();

  /* hero text cycle */
  const [wordIdx, setWordIdx] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setWordIdx((i) => (i + 1) % HERO_WORDS.length), 2400);
    return () => clearInterval(id);
  }, []);

  /* sections in-view */
  const [missionRef, missionInView] = useInView();
  const [pipelineRef, pipelineInView] = useInView();
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

  /* pipeline state */
  const [activeStage, setActiveStage] = useState(PIPELINE_STAGES[0]);
  const [collapsedLayers, setCollapsedLayers] = useState({});
  const [searchQuery, setSearchQuery] = useState("");
  const [compactMode, setCompactMode] = useState(false);
  const [keyboardStageId, setKeyboardStageId] = useState(PIPELINE_STAGES[0].id);
  const laneRefs = useRef({});

  const searchableText = (stage) => `${stage.agent} ${stage.model} ${stage.desc}`.toLowerCase();

  const filteredLayers = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    return PIPELINE_LAYERS.map((layer) => ({
      ...layer,
      stages: PIPELINE_STAGES
        .filter((stage) => stage.layerId === layer.id)
        .filter((stage) => !query || searchableText(stage).includes(query)),
    })).filter((layer) => layer.stages.length > 0 || !query);
  }, [searchQuery]);

  const visibleStages = useMemo(
    () => filteredLayers.flatMap((layer) => layer.stages),
    [filteredLayers]
  );
  const fallbackStage = visibleStages[0] || PIPELINE_STAGES[0];
  const resolvedActiveStage = visibleStages.find((stage) => stage.id === activeStage.id) || fallbackStage;
  const resolvedKeyboardStageId = visibleStages.find((stage) => stage.id === keyboardStageId)
    ? keyboardStageId
    : fallbackStage.id;

  const currentStageIndex = PIPELINE_STAGES.findIndex((stage) => stage.id === resolvedActiveStage.id);
  const handlePrevStage = () => {
    if (currentStageIndex <= 0) return;
    setActiveStage(PIPELINE_STAGES[currentStageIndex - 1]);
  };
  const handleNextStage = () => {
    if (currentStageIndex >= PIPELINE_STAGES.length - 1) return;
    setActiveStage(PIPELINE_STAGES[currentStageIndex + 1]);
  };

  const toggleLayer = (layerId) => {
    setCollapsedLayers((prev) => ({ ...prev, [layerId]: !prev[layerId] }));
  };

  const jumpToLayer = (layerId) => {
    laneRefs.current[layerId]?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const handlePipelineKeyDown = (event) => {
    if (!visibleStages.length) return;
    const keyIndex = visibleStages.findIndex((stage) => stage.id === resolvedKeyboardStageId);
    if (event.key === "ArrowRight" || event.key === "ArrowDown") {
      event.preventDefault();
      const next = visibleStages[Math.min(keyIndex + 1, visibleStages.length - 1)];
      if (next) setKeyboardStageId(next.id);
    }
    if (event.key === "ArrowLeft" || event.key === "ArrowUp") {
      event.preventDefault();
      const prev = visibleStages[Math.max(keyIndex - 1, 0)];
      if (prev) setKeyboardStageId(prev.id);
    }
    if (event.key === "Enter") {
      event.preventDefault();
      const selected = visibleStages.find((stage) => stage.id === resolvedKeyboardStageId);
      if (selected) setActiveStage(selected);
    }
  };

  const getNodeRelation = (stage) => {
    if (stage.id === resolvedActiveStage.id) return "active";
    if (stage.layerId === resolvedActiveStage.layerId) return "same-lane";
    return "unrelated";
  };

  const features = [
    {
      icon: "🧠",
      title: "AI-Powered Prioritization",
      desc: "Our system analyzes every ticket using natural language processing and sentiment detection to identify urgent cases and bring the most critical issues to the top automatically.",
      detail: "We use a Fuzzy Logic Prioritization Agent that combines signals from a Feature Engineering Agent — detecting urgency, severity, business impact, safety concerns, and recurrence — alongside a RoBERTa-based Sentiment Analysis Agent. Together, these produce a nuanced priority score (Critical, High, Medium, or Low) assigned automatically the moment a ticket is created.",
    },
    {
      icon: "🎙️",
      title: "Audio & Sentiment Analysis",
      desc: "Customer voice calls can be transcribed and analyzed for sentiment, giving support agents useful context before they begin handling the case.",
      detail: "Voice submissions are processed by a Whisper-powered Transcriber Agent that converts audio to text. In parallel, a Librosa-based Audio Analysis Agent extracts emotional cues directly from the audio waveform. A Sentiment Combiner then fuses text and audio signals into a unified sentiment score, feeding directly into prioritization.",
    },
    {
      icon: "⚡",
      title: "Instant Escalation",
      desc: "High-priority tickets are automatically flagged and routed to the appropriate team, helping reduce delays and improve response times.",
      detail: "Once priority is assigned, an SLA Policy Engine maps it to deadline targets and a Department Routing Agent automatically assigns the ticket to the correct team and employee. Critical and High priority tickets bypass the standard queue, triggering immediate notifications so urgent cases are never left waiting.",
    },
    {
      icon: "📊",
      title: "Live Analytics Dashboard",
      desc: "Managers can view real-time insights into ticket volume, team performance, and customer sentiment through a centralized dashboard.",
      detail: "Managers access a dedicated analytics view with real-time ticket volume, team performance metrics, and sentiment trends. Employees see their personal queue with AI-generated resolution suggestions powered by a Suggested Resolution Agent that applies LLM reasoning and reinforcement learning from past outcomes.",
    },
    {
      icon: "🔗",
      title: "Seamless Integration",
      desc: "InnovaCX can integrate with existing CRM, helpdesk, or e-commerce platforms, allowing businesses to incorporate the system into their current workflows.",
      detail: "InnovaCX exposes a RESTful API secured with JWT authentication, enabling connection to existing CRM, helpdesk, and e-commerce systems. Webhook support allows external platforms to receive ticket events in real time, and the modular architecture ensures new integrations can be added without disrupting existing workflows.",
    },
    {
      icon: "🔒",
      title: "Enterprise-Grade Security",
      desc: "Customer data is protected through encryption, role-based access control, and detailed audit logs to support secure and responsible data handling.",
      detail: "Access is governed by role-based JWT tokens enforcing separate permissions for Customers, Employees, and Managers. All traffic is encrypted in transit via HTTPS, and every ticket action is recorded in a tamper-evident audit log. Sensitive data handling aligns with standard enterprise data protection practices.",
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
              <span key={wordIdx} className="au-word-spin">{HERO_WORDS[wordIdx]}</span>
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

      {/* ── Model Pipeline ── */}
      <section className="au-section au-pipeline-section" ref={pipelineRef}>
        <div className={`au-pipeline-header ${pipelineInView ? "au-fade-up" : ""}`}>
          <div className="au-section-tag">How It Works</div>
          <h2 className="au-section-title">InnovaCX Agent Pipeline</h2>
          <p className="au-pipeline-intro">
            A compact overview of how requests move from user entry to decisioning and continuous learning.
            Click any agent to inspect its role, inputs, and outputs.
          </p>
          <div className="au-pipeline-legend">
            <span className="au-legend-item"><b>OPTIONAL</b> feedback-dependent step</span>
            <span className="au-legend-item"><b>AUDIO-ONLY</b> runs for voice submissions</span>
            <span className="au-legend-item"><b>SKIPPED-IF-SET</b> bypassed if already provided</span>
          </div>
        </div>

        <div className="au-pipeline-controls">
          <div className="au-pipeline-search-wrap">
            <input
              type="search"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="au-pipeline-search"
              placeholder="Search agents (e.g. sentiment, SLA)"
              aria-label="Search pipeline agents"
            />
          </div>
          <button
            type="button"
            className="au-compact-toggle"
            onClick={() => setCompactMode((prev) => !prev)}
          >
            {compactMode ? "Full cards" : "Compact mode"}
          </button>
        </div>

        <div className="au-lane-jumps">
          {PIPELINE_LAYERS.map((layer) => (
            <button
              key={layer.id}
              type="button"
              className={`au-lane-pill ${resolvedActiveStage.layerId === layer.id ? "is-active" : ""}`}
              onClick={() => jumpToLayer(layer.id)}
              style={{ "--lane-color": layer.color }}
            >
              {layer.name}
            </button>
          ))}
        </div>

        <div className="au-pipeline-workspace" onKeyDown={handlePipelineKeyDown} tabIndex={0}>
          {/* ── Swimlane diagram ── */}
          <div className="au-pipeline-swimlanes-wrap">
            <div className="au-pipeline-panel-title">Pipeline Stages</div>
            <div className="au-pipeline-swimlanes">
              {filteredLayers.map((layer) => (
                <div key={layer.id} className="au-swimlane" ref={(el) => { laneRefs.current[layer.id] = el; }}>
                  {/* Lane label */}
                  <div className="au-swimlane-label">
                    <span className="au-swimlane-bar" style={{ background: layer.color }} />
                    <span className="au-swimlane-name" style={{ color: layer.color }}>{layer.name}</span>
                    <span className="au-swimlane-rule" style={{ background: `linear-gradient(90deg, ${layer.color}44, transparent)` }} />
                    <button
                      type="button"
                      className="au-lane-toggle"
                      onClick={() => toggleLayer(layer.id)}
                    >
                      {collapsedLayers[layer.id] ? "Show" : "Collapse"}
                    </button>
                  </div>

                  {/* Nodes */}
                  {!collapsedLayers[layer.id] && layer.stages.length > 0 && (
                    (() => {
                      const renderNode = (stage) => (
                        <PipelineNode
                          stage={stage}
                          isActive={resolvedActiveStage.id === stage.id}
                          isCompact={compactMode}
                          relation={getNodeRelation(stage)}
                          isKeyboardFocus={resolvedKeyboardStageId === stage.id}
                          onClick={() => {
                            setActiveStage(stage);
                            setKeyboardStageId(stage.id);
                          }}
                        />
                      );

                      const isSignalLayer = layer.id === "signal";
                      const stageById = Object.fromEntries(layer.stages.map((stage) => [stage.id, stage]));
                      const hasSignalFlow =
                        isSignalLayer &&
                        stageById.classification &&
                        stageById.sentiment &&
                        stageById.feature &&
                        stageById["audio-analysis"] &&
                        stageById.combiner;

                      if (hasSignalFlow) {
                        return (
                          <div className="au-swimlane-nodes au-swimlane-nodes--signal">
                            <div className="au-signal-grid">
                              <div className="au-signal-cell au-signal-sentiment">
                                {renderNode(stageById.sentiment)}
                              </div>
                              <div className="au-signal-cell au-signal-classification">
                                {renderNode(stageById.classification)}
                              </div>
                              <span className="au-pipeline-arrow au-signal-arrow-cs" style={{ color: `${layer.color}88` }}>
                                →
                              </span>
                              <span className="au-pipeline-arrow au-signal-arrow-sf" style={{ color: `${layer.color}88` }}>
                                →
                              </span>
                              <div className="au-signal-cell au-signal-feature">
                                {renderNode(stageById.feature)}
                              </div>

                              <div className="au-signal-cell au-signal-audio">
                                {renderNode(stageById["audio-analysis"])}
                              </div>
                              <span className="au-pipeline-arrow au-signal-arrow-ac is-conditional-flow" style={{ color: `${layer.color}88` }}>
                                →
                              </span>
                              <div className="au-signal-cell au-signal-combiner">
                                {renderNode(stageById.combiner)}
                              </div>

                              <span className="au-pipeline-arrow au-signal-arrow-down is-conditional-flow" style={{ color: `${layer.color}88` }}>
                                →
                              </span>
                            </div>
                          </div>
                        );
                      }

                      return (
                        <div className="au-swimlane-nodes">
                          {layer.stages.map((stage, si) => {
                            const nextStage = layer.stages[si + 1];
                            const showArrow = !nextStage ? false : true;
                            return (
                              <React.Fragment key={stage.id}>
                                {renderNode(stage)}
                                {showArrow && (
                                  <span
                                    className="au-pipeline-arrow"
                                    style={{ color: `${layer.color}88` }}
                                  >
                                    →
                                  </span>
                                )}
                              </React.Fragment>
                            );
                          })}
                        </div>
                      );
                    })()
                  )}
                </div>
              ))}
              {filteredLayers.length === 0 && (
                <div className="au-pipeline-empty">
                  No matching agents found for "{searchQuery}".
                </div>
              )}
            </div>
          </div>

          {/* ── Detail panel ── */}
          <div className="au-pipeline-detail-wrap">
            <div className="au-pipeline-panel-title">Selected Agent Details</div>
            <PipelineDetail
              stage={resolvedActiveStage}
              onPrev={handlePrevStage}
              onNext={handleNextStage}
              isFirst={currentStageIndex === 0}
              isLast={currentStageIndex === PIPELINE_STAGES.length - 1}
            />
          </div>
        </div>
      </section>

      <section className="au-section au-stats-section" ref={statsRef}>
        <h2 className="au-section-title" style={{ textAlign: "center" }}>
          Real Impact, Real Results
        </h2>
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