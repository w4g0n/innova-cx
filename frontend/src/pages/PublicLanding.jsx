import { useNavigate } from "react-router-dom";
import { useEffect, useRef, useState, useCallback } from "react";
import novaLogo from "../assets/nova-logo.png";
import "./PublicLanding.css";

/* ── Agents with full doc details ── */
const AGENTS_DATA = [
  {
    name: "Chatbot",
    role: "Resolves & Routes",
    model: "Falcon 1B Instruct",
    color: "#c084fc",
    emoji: "🤖",
    details: "The front-line agent users interact with directly. Uses intent classification to determine if a user has an inquiry or a complaint. Can create tickets, track existing tickets, and resolve inquiries using a connected knowledge base. If unresolved, it redirects users into the complaint pipeline. Also auto-generates a subject line if the user doesn't provide one.",
    inputs: ["User message", "Audio or Text"],
    outputs: ["Ticket creation", "Inquiry resolution", "Subject generation"],
    stat: "98%", statLabel: "Accuracy",
    description: "First point of contact for every user. Instantly classifies intent and routes intelligently.",
  },
  {
    name: "Transcriber",
    role: "Audio → Text",
    model: "OpenAI Whisper",
    color: "#818cf8",
    emoji: "🎙️",
    details: "Handles live transcription of English-language voice complaints. When a ticket is submitted via audio recording, the Transcriber converts it to text before passing it downstream. The audio log is discarded after transcription to protect privacy.",
    inputs: ["Audio_Log"],
    outputs: ["Transcribed text (Details)"],
    stat: "<2s", statLabel: "Latency",
    description: "Converts voice recordings to text in real-time. Privacy-first: audio discarded after transcription.",
  },
  {
    name: "Classifier",
    role: "Complaint vs Inquiry",
    model: "NLI Model",
    color: "#a78bfa",
    emoji: "🏷️",
    details: "Skipped if the user already selected a ticket type. Otherwise, this agent reads the complaint details and classifies whether it is a Complaint or an Inquiry. This classification gates the rest of the pipeline and determines which downstream agents are activated.",
    inputs: ["Details (text)"],
    outputs: ["Ticket_Type: Complaint or Inquiry"],
    stat: "2", statLabel: "Classes",
    description: "Gates the entire pipeline. Determines which agents activate downstream with zero ambiguity.",
  },
  {
    name: "Sentiment",
    role: "Emotion Detection",
    model: "RoBERTa + Librosa",
    color: "#e879f9",
    emoji: "💜",
    details: "Analyses the emotional tone of the complaint text using RoBERTa. If audio was submitted, Librosa analyses the voice recording for audio sentiment separately. A Sentiment Combiner module then merges both into a unified Sentiment_Score. Triggers ticket status change to 'In Progress'.",
    inputs: ["Details", "Audio_Log (optional)"],
    outputs: ["text_sentiment", "audio_sentiment", "Sentiment_Score"],
    stat: "99.2%", statLabel: "Precision",
    description: "Dual-channel: reads text tone with RoBERTa, voice stress with Librosa. Fused into one score.",
  },
  {
    name: "Features",
    role: "Urgency & Impact",
    model: "NLI + Database",
    color: "#f0abfc",
    emoji: "⚙️",
    details: "A multi-signal agent that determines four key attributes: whether the issue is recurring (via database lookup), whether there's a safety concern, the business impact level, and issue urgency and severity. These signals feed directly into the Prioritizer for accurate scoring.",
    inputs: ["Details"],
    outputs: ["is_recurring", "safety_concern", "business_impact", "issue_severity", "issue_urgency"],
    stat: "5", statLabel: "Signals",
    description: "Extracts 5 critical signals from every complaint. Feeds directly into fuzzy logic scoring.",
  },
  {
    name: "Prioritizer",
    role: "Fuzzy Logic Scoring",
    model: "Fuzzy Logic Engine",
    color: "#c026d3",
    emoji: "⚖️",
    details: "Combines all upstream signals using fuzzy logic to produce a single Priority score. Takes into account ticket type, recurrence, business impact, safety concern, combined sentiment, severity, and urgency. Outputs one of four priority levels: Critical, High, Medium, or Low.",
    inputs: ["ticket_type", "is_recurring", "business_impact", "safety_concern", "sentiment_score", "issue_severity", "issue_urgency"],
    outputs: ["Priority: Critical / High / Medium / Low"],
    stat: "4", statLabel: "Priority Levels",
    description: "7 inputs in, one crystal-clear priority out. No guesswork, no bias — pure logic.",
  },
  {
    name: "Router",
    role: "Department Assignment",
    model: "NLI DeBERTa",
    color: "#d946ef",
    emoji: "🏢",
    details: "Uses DeBERTa with a confidence threshold of 0.7 to route tickets to the correct department. Requires no training. If the confidence score falls below 0.7, the ticket is escalated to management for manual routing. Departments include: Facilities, Legal, Safety, HR, Leasing, Maintenance, and IT.",
    inputs: ["Complaint details"],
    outputs: ["Assigned department (or escalation to management)"],
    stat: "0.7", statLabel: "Threshold",
    description: "Routes to 7 departments with zero training. Escalates to management if confidence dips below 0.7.",
  },
  {
    name: "Resolver",
    role: "Suggested Fixes",
    model: "Flan-T5-Base",
    color: "#a855f7",
    emoji: "💡",
    details: "A mini-agent that generates suggested resolutions based on the complaint text. Features a built-in relearning loop: every time an employee submits their actual resolution, the model retrains on the difference between its suggestion and the real fix — continuously improving over time.",
    inputs: ["Complaint text"],
    outputs: ["Suggested resolution (improves with each employee correction)"],
    stat: "∞", statLabel: "Relearning",
    description: "Gets smarter with every closed ticket. Self-improving resolution engine that never stops learning.",
  },
];

const PIPELINE = [
  { icon: "📥", label: "Ticket Submitted",  sub: "Text or Audio",           color: "#c084fc", step: 0 },
  { icon: "🔤", label: "Transcribe",        sub: "Whisper (if audio)",      color: "#818cf8", step: 1 },
  { icon: "🏷️", label: "Classify",         sub: "Complaint / Inquiry",     color: "#a78bfa", step: 2 },
  { icon: "💜", label: "Sentiment",         sub: "RoBERTa + Librosa",       color: "#e879f9", step: 3 },
  { icon: "⚙️", label: "Feature Eng.",     sub: "Urgency · Impact · Risk", color: "#f0abfc", step: 4 },
  { icon: "⚖️", label: "Prioritise",       sub: "Fuzzy Logic",             color: "#c026d3", step: 5 },
  { icon: "📋", label: "SLA",              sub: "Auto-escalation",          color: "#d946ef", step: 6 },
  { icon: "🏢", label: "Route",            sub: "DeBERTa 0.7",             color: "#a855f7", step: 7 },
  { icon: "💡", label: "Resolution",       sub: "Flan-T5 + relearn",       color: "#c084fc", step: 8 },
];

/* ══ STARFIELD ══ */
function Starfield() {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current; if (!c) return;
    const ctx = c.getContext("2d");
    let raf;
    const resize = () => { c.width = c.offsetWidth; c.height = c.offsetHeight; };
    resize();
    const stars = Array.from({ length: 300 }, () => ({
      x: Math.random(), y: Math.random(),
      r: Math.random() * 1.5 + 0.2,
      twinkle: Math.random() * Math.PI * 2,
      speed: Math.random() * 0.018 + 0.004,
      color: Math.random() > 0.8 ? "#c4b5fd" : Math.random() > 0.6 ? "#e9d5ff" : "#fff",
    }));
    const shooters = Array.from({ length: 3 }, () => ({
      x: Math.random() * 0.5, y: Math.random() * 0.4,
      len: Math.random() * 130 + 70, speed: Math.random() * 4 + 3,
      angle: Math.PI / 5.5, active: false, timer: Math.random() * 400 + 100, alpha: 0,
    }));
    const draw = () => {
      ctx.clearRect(0, 0, c.width, c.height);
      stars.forEach(s => {
        s.twinkle += s.speed;
        ctx.globalAlpha = Math.max(0.05, 0.3 + Math.sin(s.twinkle) * 0.55);
        ctx.fillStyle = s.color;
        ctx.beginPath();
        ctx.arc(s.x * c.width, s.y * c.height, s.r, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.globalAlpha = 1;
      shooters.forEach(s => {
        s.timer--;
        if (s.timer <= 0 && !s.active) { s.active = true; s.alpha = 1; }
        if (s.active) {
          s.x += Math.cos(s.angle) * s.speed / c.width;
          s.y += Math.sin(s.angle) * s.speed / c.height;
          s.alpha -= 0.016;
          if (s.alpha <= 0 || s.x > 1) {
            s.active = false; s.x = Math.random() * 0.4; s.y = Math.random() * 0.35;
            s.timer = Math.random() * 500 + 200;
          }
          ctx.save(); ctx.globalAlpha = s.alpha;
          const g = ctx.createLinearGradient(s.x*c.width, s.y*c.height,
            (s.x - Math.cos(s.angle)*s.len/c.width)*c.width,
            (s.y - Math.sin(s.angle)*s.len/c.height)*c.height);
          g.addColorStop(0, "#e9d5ff"); g.addColorStop(1, "transparent");
          ctx.beginPath();
          ctx.moveTo(s.x*c.width, s.y*c.height);
          ctx.lineTo((s.x - Math.cos(s.angle)*s.len/c.width)*c.width,
                     (s.y - Math.sin(s.angle)*s.len/c.height)*c.height);
          ctx.strokeStyle = g; ctx.lineWidth = 1.5; ctx.stroke();
          ctx.restore();
        }
      });
      raf = requestAnimationFrame(draw);
    };
    draw();
    window.addEventListener("resize", resize);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); };
  }, []);
  return <canvas ref={ref} className="pl-starfield" />;
}

/* ══ SOLAR SYSTEM — wider, slower, larger planets ══ */
function SolarSystem() {
  const ref = useRef(null);
  const anglesRef = useRef(AGENTS_DATA.map((_, i) => (i / AGENTS_DATA.length) * Math.PI * 2));
  const hoverRef = useRef(-1);
  const [hovered, setHovered] = useState(null);
  const tRef = useRef(0);

  // Larger planets, wider orbits, much slower speeds
  const PLANET_CFG = [
    { color: "#c084fc", size: 15, orbitRx: 95,  orbitRy: 38,  speed: 0.012 },
    { color: "#818cf8", size: 18, orbitRx: 148, orbitRy: 59,  speed: 0.009 },
    { color: "#a78bfa", size: 20, orbitRx: 198, orbitRy: 79,  speed: 0.007 },
    { color: "#e879f9", size: 18, orbitRx: 248, orbitRy: 99,  speed: 0.006 },
    { color: "#f0abfc", size: 30, orbitRx: 295, orbitRy: 118, speed: 0.005 },
    { color: "#c026d3", size: 25, orbitRx: 342, orbitRy: 137, speed: 0.0042 },
    { color: "#d946ef", size: 28, orbitRx: 386, orbitRy: 154, speed: 0.0036 },
    { color: "#a855f7", size: 23, orbitRx: 428, orbitRy: 171, speed: 0.003 },
  ];

  useEffect(() => {
    const c = ref.current; if (!c) return;
    const ctx = c.getContext("2d");
    let raf;
    const SIZE = 920;
    c.width = SIZE; c.height = SIZE;
    const cx = SIZE / 2, cy = SIZE / 2;

    const draw = () => {
      tRef.current += 0.008;
      const t = tRef.current;
      ctx.clearRect(0, 0, SIZE, SIZE);

      const neb = ctx.createRadialGradient(cx, cy, 0, cx, cy, 380);
      neb.addColorStop(0,   "rgba(147,51,234,0.18)");
      neb.addColorStop(0.5, "rgba(88,28,135,0.08)");
      neb.addColorStop(1,   "transparent");
      ctx.fillStyle = neb;
      ctx.fillRect(0, 0, SIZE, SIZE);

      PLANET_CFG.forEach(p => {
        ctx.save();
        ctx.translate(cx, cy);
        ctx.beginPath();
        ctx.ellipse(0, 0, p.orbitRx, p.orbitRy, 0, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(167,139,250,0.08)";
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 12]);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.restore();
      });

      // Sun
      const sunSizes = [100, 70, 50, 32];
      const sunAlphas = [0.06, 0.12, 0.25, 1];
      sunSizes.forEach((r, i) => {
        const sg = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
        sg.addColorStop(0,   `rgba(255,255,255,${sunAlphas[i]})`);
        sg.addColorStop(0.4, `rgba(232,210,255,${sunAlphas[i] * 0.6})`);
        sg.addColorStop(0.7, `rgba(168,85,247,${sunAlphas[i] * 0.3})`);
        sg.addColorStop(1,   "transparent");
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.fillStyle = sg;
        ctx.fill();
      });

      const coronaR = 38 + Math.sin(t * 2.5) * 4;
      ctx.beginPath();
      ctx.arc(cx, cy, coronaR, 0, Math.PI * 2);
      ctx.strokeStyle = `rgba(192,132,252,${0.35 + Math.sin(t * 2) * 0.15})`;
      ctx.lineWidth = 2;
      ctx.stroke();

      ctx.font = "bold 13px Outfit, sans-serif";
      ctx.textAlign = "center"; ctx.textBaseline = "middle";
      ctx.fillStyle = "rgba(255,255,255,0.9)";
      ctx.fillText("InnovaCX", cx, cy - 6);
      ctx.font = "10px JetBrains Mono, monospace";
      ctx.fillStyle = "rgba(255,255,255,0.45)";
      ctx.fillText("Orchestrator", cx, cy + 10);

      const positions = PLANET_CFG.map((p, i) => {
        const angle = anglesRef.current[i] + p.speed;
        anglesRef.current[i] = angle;
        const px = cx + Math.cos(angle) * p.orbitRx;
        const py = cy + Math.sin(angle) * p.orbitRy;
        return { px, py, angle, p, i };
      });

      const sorted = [...positions].sort((a, b) => a.py - b.py);

      sorted.forEach(({ px, py, p, i }) => {
        const isH = hoverRef.current === i;
        const r = isH ? p.size * 1.4 : p.size;

        const g = ctx.createRadialGradient(px, py, 0, px, py, r * 4);
        g.addColorStop(0,   p.color + (isH ? "99" : "55"));
        g.addColorStop(1,   p.color + "00");
        ctx.beginPath();
        ctx.arc(px, py, r * 4, 0, Math.PI * 2);
        ctx.fillStyle = g;
        ctx.fill();

        const hx = px - r * 0.35, hy = py - r * 0.35;
        const sphere = ctx.createRadialGradient(hx, hy, 0, px, py, r);
        sphere.addColorStop(0,   "#ffffff");
        sphere.addColorStop(0.25, p.color + "ff");
        sphere.addColorStop(0.7,  p.color + "cc");
        sphere.addColorStop(1,    "#000000aa");
        ctx.beginPath();
        ctx.arc(px, py, r, 0, Math.PI * 2);
        ctx.fillStyle = sphere;
        ctx.fill();

        ctx.beginPath();
        ctx.arc(px, py, r, 0, Math.PI * 2);
        ctx.strokeStyle = isH ? "rgba(255,255,255,0.8)" : "rgba(255,255,255,0.25)";
        ctx.lineWidth = isH ? 2 : 0.8;
        ctx.stroke();

        // Bigger, bolder labels
        ctx.font = `${isH ? "bold " : ""}${isH ? 13 : 12}px Outfit, sans-serif`;
        ctx.textAlign = "center"; ctx.textBaseline = "top";
        ctx.fillStyle = isH ? "#fff" : "rgba(255,255,255,0.65)";
        ctx.fillText(AGENTS_DATA[i].name, px, py + r + 7);

        if (isH) {
          ctx.font = "10px JetBrains Mono, monospace";
          ctx.fillStyle = "rgba(255,255,255,0.4)";
          ctx.fillText(AGENTS_DATA[i].role, px, py + r + 23);
        }
      });

      raf = requestAnimationFrame(draw);
    };
    draw();

    const onMove = (e) => {
      const rect = c.getBoundingClientRect();
      const scaleX = SIZE / rect.width, scaleY = SIZE / rect.height;
      const mx = (e.clientX - rect.left) * scaleX;
      const my = (e.clientY - rect.top) * scaleY;
      let found = -1;
      PLANET_CFG.forEach((p, i) => {
        const angle = anglesRef.current[i];
        const px = cx + Math.cos(angle) * p.orbitRx;
        const py = cy + Math.sin(angle) * p.orbitRy;
        if (Math.hypot(mx - px, my - py) < p.size + 14) found = i;
      });
      hoverRef.current = found;
      setHovered(found >= 0 ? AGENTS_DATA[found] : null);
    };
    c.addEventListener("mousemove", onMove);
    c.addEventListener("mouseleave", () => { hoverRef.current = -1; setHovered(null); });
    return () => { cancelAnimationFrame(raf); };
  }, []);

  return (
    <div className="pl-solar-wrap">
      <canvas ref={ref} className="pl-solar-canvas" />
      {hovered && (
        <div className="pl-planet-tooltip">
          <div className="pl-pt-name" style={{ color: hovered.color }}>{hovered.emoji} {hovered.name}</div>
          <div className="pl-pt-role">{hovered.role}</div>
          <div className="pl-pt-model">{hovered.model}</div>
        </div>
      )}
      <p className="pl-solar-hint">Hover a planet · each is an AI agent</p>
    </div>
  );
}

/* ══ TYPEWRITER ══ */
function Typewriter({ words }) {
  const [wi, setWi] = useState(0);
  const [ci, setCi] = useState(0);
  const [del, setDel] = useState(false);
  const [txt, setTxt] = useState("");
  useEffect(() => {
    const w = words[wi];
    const id = del
      ? setTimeout(() => { setTxt(w.slice(0,ci-1)); setCi(c=>c-1); if(ci-1===0){setDel(false);setWi(x=>(x+1)%words.length);} }, 55)
      : setTimeout(() => { setTxt(w.slice(0,ci+1)); setCi(c=>c+1); if(ci+1===w.length)setTimeout(()=>setDel(true),1600); }, 85);
    return () => clearTimeout(id);
  }, [ci, del, wi, words]);
  return <span className="pl-tw">{txt}<span className="pl-caret">|</span></span>;
}

/* ══ COUNTER ══ */
function Counter({ end, suffix }) {
  const [v, setV] = useState(0);
  const ref = useRef(null);
  const done = useRef(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting && !done.current) {
        done.current = true;
        let cur = 0; const n = parseFloat(end);
        const t = setInterval(() => { cur += n/55; if(cur>=n){setV(n);clearInterval(t);}else setV(Math.floor(cur)); }, 28);
      }
    }, { threshold: 0.4 });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [end]);
  return <span ref={ref}>{v}{suffix}</span>;
}

/* ══ REVEAL HOOK ══ */
function useReveal(t = 0.1) {
  const ref = useRef(null);
  const [vis, setVis] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if(e.isIntersecting)setVis(true); }, {threshold:t});
    if(ref.current)obs.observe(ref.current);
    return ()=>obs.disconnect();
  }, []);
  return [ref, vis];
}

/* ══ PIPELINE — full width, interactive, animated ══ */
function PipelineFlow() {
  const [ref, vis] = useReveal(0.05);
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);
  const [manualStep, setManualStep] = useState(null);
  const intervalRef = useRef(null);

  const currentStep = manualStep !== null ? manualStep : active;

  useEffect(() => {
    if (!vis || paused) return;
    intervalRef.current = setInterval(() => setActive(a => (a + 1) % PIPELINE.length), 1100);
    return () => clearInterval(intervalRef.current);
  }, [vis, paused]);

  const handleStepClick = (i) => {
    setPaused(true);
    setManualStep(i);
  };

  const handleResume = () => {
    setPaused(false);
    setManualStep(null);
    setActive(0);
  };

  const step = PIPELINE[currentStep];

  return (
    <div ref={ref} className="pl-pipeline-outer">
      {/* Full-width step track */}
      <div className="pl-pipeline-track">
        {PIPELINE.map((s, i) => {
          const isDone = i < currentStep;
          const isActive = i === currentStep;
          return (
            <button
              key={i}
              className={`pl-pipe-node ${vis ? "is-vis" : ""} ${isActive ? "is-active" : ""} ${isDone ? "is-done" : ""}`}
              style={{ "--d": `${i * 0.07}s`, "--ac": s.color }}
              onClick={() => handleStepClick(i)}
            >
              <div className="pl-pipe-node-dot">
                <span className="pl-pipe-node-icon">{s.icon}</span>
              </div>
              <div className="pl-pipe-node-connector">
                <div className={`pl-pipe-node-line ${isDone || isActive ? "is-lit" : ""}`} />
              </div>
              <span className="pl-pipe-node-label">{s.label}</span>
              <span className="pl-pipe-node-sub">{s.sub}</span>
            </button>
          );
        })}
      </div>

      {/* Detail panel for active step */}
      <div className={`pl-pipe-detail ${vis ? "is-vis" : ""}`} key={currentStep}>
        <div className="pl-pipe-detail-icon" style={{ color: step.color }}>{step.icon}</div>
        <div className="pl-pipe-detail-content">
          <div className="pl-pipe-detail-step" style={{ color: step.color }}>
            Step {currentStep + 1} of {PIPELINE.length}
          </div>
          <h3 className="pl-pipe-detail-name">{step.label}</h3>
          <p className="pl-pipe-detail-sub">{step.sub}</p>
        </div>
        <div className="pl-pipe-detail-progress">
          <div className="pl-pipe-detail-bar">
            <div
              className="pl-pipe-detail-fill"
              style={{
                width: `${((currentStep + 1) / PIPELINE.length) * 100}%`,
                background: `linear-gradient(90deg, #7c3aed, ${step.color})`,
              }}
            />
          </div>
          <span className="pl-pipe-detail-pct">{Math.round(((currentStep + 1) / PIPELINE.length) * 100)}% complete</span>
        </div>
        {paused && (
          <button className="pl-pipe-resume-btn" onClick={handleResume}>
            ▶ Resume Auto
          </button>
        )}
      </div>

      {/* Step dots indicator */}
      <div className="pl-pipe-dots">
        {PIPELINE.map((s, i) => (
          <button
            key={i}
            className={`pl-pipe-dot ${i === currentStep ? "active" : ""} ${i < currentStep ? "done" : ""}`}
            style={{ "--ac": s.color }}
            onClick={() => handleStepClick(i)}
          />
        ))}
      </div>

      {!paused && (
        <button className="pl-pipe-pause-btn" onClick={() => setPaused(true)}>⏸ Pause</button>
      )}
    </div>
  );
}

/* ══ AGENTS — immersive grid with 3D cards ══ */
function AgentsShowcase() {
  const [ref, vis] = useReveal(0.05);
  const [selected, setSelected] = useState(null);
  const [hoveredIdx, setHoveredIdx] = useState(null);

  return (
    <div ref={ref} className="pl-agents-showcase">
      {/* Hexagonal agent grid */}
      <div className="pl-agents-grid">
        {AGENTS_DATA.map((agent, i) => (
          <div
            key={agent.name}
            className={`pl-agent-hex ${vis ? "is-vis" : ""} ${selected?.name === agent.name ? "is-selected" : ""} ${hoveredIdx === i ? "is-hovered" : ""}`}
            style={{ "--ac": agent.color, "--d": `${i * 0.08}s` }}
            onClick={() => setSelected(selected?.name === agent.name ? null : agent)}
            onMouseEnter={() => setHoveredIdx(i)}
            onMouseLeave={() => setHoveredIdx(null)}
          >
            <div className="pl-agent-hex-bg" />
            <div className="pl-agent-hex-glow" />
            <div className="pl-agent-hex-content">
              <div className="pl-agent-hex-num">0{i + 1}</div>
              <div className="pl-agent-hex-emoji">{agent.emoji}</div>
              <div className="pl-agent-hex-name">{agent.name}</div>
              <div className="pl-agent-hex-role">{agent.role}</div>
              <div className="pl-agent-hex-stat">
                <span className="pl-agent-hex-stat-n">{agent.stat}</span>
                <span className="pl-agent-hex-stat-l">{agent.statLabel}</span>
              </div>
            </div>
            <div className="pl-agent-hex-ring" />
          </div>
        ))}
      </div>

      {/* Detail panel */}
      {selected ? (
        <div className="pl-agent-panel" key={selected.name} style={{ "--ac": selected.color }}>
          <div className="pl-agent-panel-header">
            <div className="pl-agent-panel-emoji">{selected.emoji}</div>
            <div>
              <div className="pl-agent-panel-tag" style={{ color: selected.color }}>{selected.model}</div>
              <h3 className="pl-agent-panel-name">{selected.name}</h3>
              <div className="pl-agent-panel-role">{selected.role}</div>
            </div>
            <button className="pl-agent-panel-close" onClick={() => setSelected(null)}>✕</button>
          </div>
          <p className="pl-agent-panel-desc">{selected.details}</p>
          <div className="pl-agent-panel-io">
            <div className="pl-agent-panel-col">
              <div className="pl-agent-panel-col-label">→ Inputs</div>
              {selected.inputs.map((inp, i) => (
                <div key={i} className="pl-agent-panel-item pl-api-in">{inp}</div>
              ))}
            </div>
            <div className="pl-agent-panel-divider" />
            <div className="pl-agent-panel-col">
              <div className="pl-agent-panel-col-label">← Outputs</div>
              {selected.outputs.map((out, i) => (
                <div key={i} className="pl-agent-panel-item pl-api-out">{out}</div>
              ))}
            </div>
          </div>
          <div className="pl-agent-panel-stat-strip">
            <div className="pl-agent-panel-stat-n" style={{ color: selected.color }}>{selected.stat}</div>
            <div className="pl-agent-panel-stat-l">{selected.statLabel}</div>
          </div>
        </div>
      ) : (
        <div className="pl-agent-panel pl-agent-panel-empty">
          <div className="pl-agent-panel-empty-icon">🛸</div>
          <p className="pl-agent-panel-empty-txt">Select an agent to explore its capabilities</p>
        </div>
      )}
    </div>
  );
}

/* ══ AGENT CARD (expandable, kept for reference) ══ */
function AgentCard({ agent, index, visible }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div
      className={`pl-agent-card ${visible?"is-vis":""} ${expanded?"is-expanded":""}`}
      style={{"--ac":agent.color,"--d":`${index*0.07}s`}}
      onClick={() => setExpanded(e => !e)}
    >
      <div className="pl-agent-glow" />
      <div className="pl-agent-top">
        <div className="pl-agent-planet" style={{background:agent.color,boxShadow:`0 0 16px ${agent.color}66`}} />
        <div className="pl-agent-header">
          <span className="pl-agent-num">0{index+1}</span>
          <span className="pl-agent-name">{agent.name}</span>
          <span className="pl-agent-role">{agent.role}</span>
        </div>
        <div className="pl-agent-model-tag">{agent.model}</div>
        <div className="pl-agent-chevron">{expanded ? "−" : "+"}</div>
      </div>
      {expanded && (
        <div className="pl-agent-expanded" onClick={e => e.stopPropagation()}>
          <p className="pl-agent-details">{agent.details}</p>
          <div className="pl-agent-io">
            <div className="pl-agent-io-col">
              <span className="pl-agent-io-label">Inputs</span>
              {agent.inputs.map((inp,i) => <span key={i} className="pl-agent-io-item pl-io-in">{inp}</span>)}
            </div>
            <div className="pl-agent-io-div" />
            <div className="pl-agent-io-col">
              <span className="pl-agent-io-label">Outputs</span>
              {agent.outputs.map((out,i) => <span key={i} className="pl-agent-io-item pl-io-out">{out}</span>)}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ══ MAIN ══ */
export default function PublicLanding() {
  const navigate = useNavigate();
  const [featRef, featVis] = useReveal();
  const [scrollY, setScrollY] = useState(0);

  useEffect(() => {
    const fn = () => setScrollY(window.scrollY);
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  return (
    <div className="pl-root">

      {/* ══ HERO ══ */}
      <section className="pl-hero">
        <Starfield />
        <div className="pl-neb pl-neb1" style={{transform:`translateY(${scrollY*0.12}px)`}} />
        <div className="pl-neb pl-neb2" style={{transform:`translateY(${scrollY*0.07}px)`}} />
        <div className="pl-neb pl-neb3" style={{transform:`translateY(${scrollY*0.18}px)`}} />

        <nav className="pl-nav">
          <img src={novaLogo} alt="InnovaCX" className="pl-logo" />
          <div className="pl-nav-chip"><span className="pl-live-dot" /> 8 Agents · Live Pipeline</div>
          <button className="pl-login-btn" onClick={() => navigate("/login")}>Log In →</button>
        </nav>

        <div className="pl-hero-body">
          <div className="pl-hero-left">
            <p className="pl-eyebrow">Dubai CommerCity · AI Multi-Agent CX Platform</p>
            <h1 className="pl-headline">
              <span className="pl-hl1">Every Complaint</span>
              <span className="pl-hl2">Handled by</span>
              <span className="pl-hl3"><Typewriter words={["AI Agents.","InnovaCX.","8 Experts.","Nova."]} /></span>
            </h1>
            <p className="pl-hero-sub">
              Eight specialised AI agents — from Whisper transcription to Flan-T5 resolution —
              orchestrated in a LangChain pipeline so no complaint is ever missed, misrouted, or unresolved.
            </p>
            <div className="pl-hero-actions">
              <button className="pl-btn-primary" onClick={() => navigate("/login")}>
                Get Started
                <svg width="15" height="15" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
              </button>
              <button className="pl-btn-ghost" onClick={() => navigate("/about")}>About Us</button>
            </div>
            <button className="pl-nova-pill" onClick={() => navigate("/login")}>
              <span className="pl-nova-dot" />
              Chat with Nova AI
              <span className="pl-nova-arrow">Try Now →</span>
            </button>
            <div className="pl-hero-stats">
              {[["98%","Triage Accuracy"],["40%","Faster Resolution"],["3×","Throughput"]].map(([v,l]) => (
                <div key={l} className="pl-hstat">
                  <span className="pl-hstat-v">{v}</span>
                  <span className="pl-hstat-l">{l}</span>
                </div>
              ))}
            </div>
          </div>
          <div className="pl-hero-right">
            <SolarSystem />
          </div>
        </div>

        <div className="pl-scroll-hint">
          <div className="pl-scroll-line" />
          <span className="pl-scroll-txt">Scroll to explore</span>
        </div>
      </section>

      {/* ══ MARQUEE ══ */}
      <div className="pl-marquee">
        <div className="pl-marquee-track">
          {[...Array(4)].map((_,r) =>
            ["Falcon 1B Chatbot","Whisper Transcription","RoBERTa Sentiment","Fuzzy Logic Priority",
             "DeBERTa Routing","Flan-T5 Resolution","SLA Automation","Zero Missed Complaints"].map((x,i)=>(
              <span key={`${r}-${i}`} className="pl-marquee-item">✦ {x}</span>
            ))
          )}
        </div>
      </div>

      {/* ══ PIPELINE ══ */}
      <section className="pl-pipeline-section">
        <div className="pl-section-tag">How It Works</div>
        <h2 className="pl-section-h light">The Complaint Pipeline</h2>
        <p className="pl-section-p light">Click any step to explore it. Watch the data flow in real-time.</p>
        <PipelineFlow />
      </section>

      {/* ══ FEATURES ══ */}
      <section className="pl-features" ref={featRef}>
        <div className="pl-feat-nebula" />
        <div className="pl-section-tag">Capabilities</div>
        <h2 className="pl-section-h light">Powered by 8 AI Agents</h2>
        <p className="pl-section-p light">Each agent a specialist. Together unstoppable.</p>
        <div className="pl-feat-grid">
          {[
            {icon:"🧠",title:"Sentiment Analysis",desc:"RoBERTa reads emotional tone in text. Librosa analyses voice recordings. A combiner merges both into one unified Sentiment_Score used for priority scoring.",stat:"99.2%",sl:"Accuracy"},
            {icon:"🎙️",title:"Audio Intelligence",desc:"Whisper transcribes voice complaints in real time. Librosa analyses the audio waveform for tone and stress. The audio log is discarded after processing to protect privacy.",stat:"<2s",sl:"Latency"},
            {icon:"⚖️",title:"Fuzzy Prioritisation",desc:"Takes 7 signals — ticket type, recurrence, business impact, safety concern, sentiment, severity, and urgency — and outputs one of four Priority levels using fuzzy logic rules.",stat:"7",sl:"Input Signals"},
            {icon:"🏢",title:"Smart Routing",desc:"DeBERTa assigns tickets to Facilities, Legal, Safety, HR, Leasing, Maintenance, or IT with a 0.7 confidence threshold. Below threshold, the ticket escalates to management.",stat:"0.7",sl:"Threshold"},
            {icon:"💡",title:"Resolution Engine",desc:"Flan-T5 generates suggested resolutions instantly. A relearning loop retrains the model on every real employee resolution, making it smarter with every ticket closed.",stat:"∞",sl:"Relearning"},
            {icon:"📋",title:"SLA Automation",desc:"Tickets automatically escalate as SLA deadlines approach. Status flows: Open → In Progress → Escalated → Overdue. Priority auto-increases when response time is breached.",stat:"0",sl:"Missed SLAs"},
          ].map((f,i) => (
            <div key={i} className={`pl-feat-card ${featVis?"is-vis":""}`} style={{"--d":`${i*0.1}s`}}>
              <div className="pl-feat-glow" />
              <div className="pl-feat-top">
                <span className="pl-feat-icon">{f.icon}</span>
                <div className="pl-feat-stat">
                  <span className="pl-feat-stat-n">{f.stat}</span>
                  <span className="pl-feat-stat-l">{f.sl}</span>
                </div>
              </div>
              <h3 className="pl-feat-title">{f.title}</h3>
              <p className="pl-feat-desc">{f.desc}</p>
              <div className="pl-feat-bar"><div className={`pl-feat-bar-fill ${featVis?"is-full":""}`} style={{transitionDelay:`${i*0.1+0.5}s`}}/></div>
            </div>
          ))}
        </div>
        <div className="pl-stat-row">
          {[["40","%","Faster Resolution"],["3","×","Complaint Throughput"],["98","%","Triage Accuracy"]].map(([n,s,l]) => (
            <div className="pl-stat-block" key={l}>
              <div className="pl-stat-n"><Counter end={n} suffix={s} /></div>
              <div className="pl-stat-l">{l}</div>
            </div>
          ))}
        </div>
      </section>

      {/* ══ AGENTS — new immersive showcase ══ */}
      <section className="pl-agents-section">
        <div className="pl-agents-section-bg" />
        <div className="pl-agents-section-inner">
          <div className="pl-section-tag" style={{color:"#c084fc"}}>The Eight Agents</div>
          <h2 className="pl-section-h light">Each one a specialist</h2>
          <p className="pl-section-p light">Click any agent card to dive deep into how it works.</p>
          <AgentsShowcase />
        </div>
      </section>

      {/* ══ CTA ══ */}
      <section className="pl-cta">
        <Starfield />
        <div className="pl-cta-neb" />
        <div className="pl-cta-inner">
          <div className="pl-section-tag" style={{color:"#c084fc"}}>Ready for Liftoff?</div>
          <h2 className="pl-cta-h">Every complaint resolved.<br/>Every customer retained.</h2>
          <p className="pl-cta-p">Dubai CommerCity's AI-powered complaint management platform. Built for scale. Designed for humans.</p>
          <div className="pl-cta-btns">
            <button className="pl-btn-primary pl-btn-lg" onClick={() => navigate("/login")}>
              Start Now
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none"><path d="M3 8h10M9 4l4 4-4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/></svg>
            </button>
            <button className="pl-btn-ghost pl-btn-lg" onClick={() => navigate("/about")}>Learn More</button>
          </div>
        </div>
      </section>

      {/* ══ FOOTER ══ */}
      <footer className="pl-footer">
        <img src={novaLogo} alt="InnovaCX" className="pl-footer-logo" />
        <div className="pl-footer-links">
          <button className="pl-footer-link" onClick={() => navigate("/about")}>About</button>
          <button className="pl-footer-link" onClick={() => navigate("/login")}>Log In</button>
        </div>
        <div className="pl-footer-socials">
          {/* Instagram */}
          <a href="https://www.instagram.com/innovacx.ai?igsh=bzVxOTNuMXUzODEz&utm_source=qr" target="_blank" rel="noopener noreferrer" className="pl-social-link" aria-label="Instagram">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="2" y="2" width="20" height="20" rx="5.5" ry="5.5" stroke="currentColor" strokeWidth="1.8" fill="none"/>
              <circle cx="12" cy="12" r="4.5" stroke="currentColor" strokeWidth="1.8" fill="none"/>
              <circle cx="17.5" cy="6.5" r="1.1" fill="currentColor"/>
            </svg>
          </a>
          {/* TikTok */}
          <a href="https://www.tiktok.com/@innovacx" target="_blank" rel="noopener noreferrer" className="pl-social-link" aria-label="TikTok">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
              <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1V9.01a6.34 6.34 0 00-.79-.05 6.34 6.34 0 00-6.34 6.34 6.34 6.34 0 006.34 6.34 6.34 6.34 0 006.33-6.34V8.75a8.28 8.28 0 004.84 1.54V6.84a4.85 4.85 0 01-1.07-.15z"/>
            </svg>
          </a>
          {/* LinkedIn */}
          <a href="https://www.linkedin.com/in/innovacx-ai-7b55853a2?utm_source=share_via&utm_content=profile&utm_medium=member_ios" className="pl-social-link pl-social-placeholder" aria-label="LinkedIn (coming soon)" title="LinkedIn — coming soon">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <rect x="2" y="2" width="20" height="20" rx="4" stroke="currentColor" strokeWidth="1.8" fill="none"/>
              <path d="M7 10v7M7 7v.01M11 17v-4a2 2 0 014 0v4M11 10v7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </a>
        </div>
        <p className="pl-footer-copy">© 2026 Dubai CommerCity · InnovaCX. All rights reserved.</p>
      </footer>
    </div>
  );
}