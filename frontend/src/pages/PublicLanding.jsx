import { useNavigate } from "react-router-dom";
import { useEffect, useRef, useState} from "react";
import novaLogo from "../assets/nova-logo.png";
import "./PublicLanding.css";

/* ── Agents with full doc details ── */
const AGENTS_DATA = [
  {
    name: "Chatbot",
    role: "Resolves & Routes",
    model: "Falcon 1B Instruct",
    color: "#c084fc",
    icon: "settings",
    details: "The front-line agent users interact with directly. Uses intent classification to determine if a user has an inquiry or a complaint. Can create tickets, track existing tickets, and resolve inquiries using a connected knowledge base. If unresolved, it redirects users into the complaint pipeline. Also auto-generates a subject line if the user doesn't provide one.",
    inputs: ["User message", "Audio or Text"],
    outputs: ["Ticket creation", "Inquiry resolution", "Subject generation"],
    stat: "98%", statLabel: "Accuracy",
  },
  {
    name: "Transcriber",
    role: "Audio → Text",
    model: "OpenAI Whisper",
    color: "#818cf8",
    icon: "mic",
    details: "Handles live transcription of English-language voice complaints. When a ticket is submitted via audio recording, the Transcriber converts it to text before passing it downstream. The audio log is discarded after transcription to protect privacy.",
    inputs: ["Audio_Log"],
    outputs: ["Transcribed text (Details)"],
    stat: "<2s", statLabel: "Latency",
  },
  {
    name: "Classifier",
    role: "Complaint vs Inquiry",
    model: "NLI Model",
    color: "#a78bfa",
    icon: "tag",
    details: "Skipped if the user already selected a ticket type. Otherwise, this agent reads the complaint details and classifies whether it is a Complaint or an Inquiry. This classification gates the rest of the pipeline and determines which downstream agents are activated.",
    inputs: ["Details (text)"],
    outputs: ["Ticket_Type: Complaint or Inquiry"],
    stat: "2", statLabel: "Classes",
  },
  {
    name: "Sentiment",
    role: "Emotion Detection",
    model: "RoBERTa + Librosa",
    color: "#e879f9",
    icon: "heart",
    details: "Analyses the emotional tone of the complaint text using RoBERTa. If audio was submitted, Librosa analyses the voice recording for audio sentiment separately. A Sentiment Combiner module then merges both into a unified Sentiment_Score. Triggers ticket status change to 'In Progress'.",
    inputs: ["Details", "Audio_Log (optional)"],
    outputs: ["text_sentiment", "audio_sentiment", "Sentiment_Score"],
    stat: "99.2%", statLabel: "Precision",
  },
  {
    name: "Features",
    role: "Urgency & Impact",
    model: "NLI + Database",
    color: "#f0abfc",
    icon: "settings",
    details: "A multi-signal agent that determines four key attributes: whether the issue is recurring (via database lookup), whether there's a safety concern, the business impact level, and issue urgency and severity. These signals feed directly into the Prioritizer for accurate scoring.",
    inputs: ["Details"],
    outputs: ["is_recurring", "safety_concern", "business_impact", "issue_severity", "issue_urgency"],
    stat: "5", statLabel: "Signals",
  },
  {
    name: "Prioritizer",
    role: "Fuzzy Logic Scoring",
    model: "Fuzzy Logic Engine",
    color: "#c026d3",
    icon: "scale",
    details: "Combines all upstream signals using fuzzy logic to produce a single Priority score. Takes into account ticket type, recurrence, business impact, safety concern, combined sentiment, severity, and urgency. Outputs one of four priority levels: Critical, High, Medium, or Low.",
    inputs: ["ticket_type", "is_recurring", "business_impact", "safety_concern", "sentiment_score", "issue_severity", "issue_urgency"],
    outputs: ["Priority: Critical / High / Medium / Low"],
    stat: "4", statLabel: "Priority Levels",
  },
  {
    name: "Router",
    role: "Department Assignment",
    model: "NLI DeBERTa",
    color: "#d946ef",
    icon: "building",
    details: "Uses DeBERTa with a confidence threshold of 0.7 to route tickets to the correct department. Requires no training. If the confidence score falls below 0.7, the ticket is escalated to management for manual routing. Departments include: Facilities, Legal, Safety, HR, Leasing, Maintenance, and IT.",
    inputs: ["Complaint details"],
    outputs: ["Assigned department (or escalation to management)"],
    stat: "0.7", statLabel: "Threshold",
  },
  {
    name: "Resolver",
    role: "Suggested Fixes",
    model: "Flan-T5-Base",
    color: "#a855f7",
    icon: "lightbulb",
    details: "A mini-agent that generates suggested resolutions based on the complaint text. Features a built-in relearning loop: every time an employee submits their actual resolution, the model retrains on the difference between its suggestion and the real fix — continuously improving over time.",
    inputs: ["Complaint text"],
    outputs: ["Suggested resolution (improves with each employee correction)"],
    stat: "∞", statLabel: "Relearning",
  },
];

const PIPELINE = [
  { icon: "inbox",     label: "Ticket Submitted", sub: "Text or Audio",           color: "#c084fc", step: 0 },
  { icon: "mic",       label: "Transcribe",        sub: "Whisper (if audio)",      color: "#818cf8", step: 1 },
  { icon: "tag",       label: "Classify",          sub: "Complaint / Inquiry",     color: "#a78bfa", step: 2 },
  { icon: "heart",     label: "Sentiment",         sub: "RoBERTa + Librosa",       color: "#e879f9", step: 3 },
  { icon: "settings",  label: "Feature Eng.",      sub: "Urgency · Impact · Risk", color: "#f0abfc", step: 4 },
  { icon: "scale",     label: "Prioritise",        sub: "Fuzzy Logic",             color: "#c026d3", step: 5 },
  { icon: "clock",     label: "SLA",               sub: "Auto-escalation",         color: "#d946ef", step: 6 },
  { icon: "building",  label: "Route",             sub: "DeBERTa 0.7",             color: "#a855f7", step: 7 },
  { icon: "lightbulb", label: "Resolution",        sub: "Flan-T5 + relearn",       color: "#c084fc", step: 8 },
];

/* ── Professional SVG Icon component ── */
function Icon({ name, size = 20 }) {
  const s = { width: size, height: size };
  const p = { fill: "none", stroke: "currentColor", strokeWidth: "1.8", strokeLinecap: "round", strokeLinejoin: "round" };
  const icons = {
    inbox: <svg {...s} viewBox="0 0 24 24" {...p}><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 002 2h16a2 2 0 002-2v-6l-3.45-6.89A2 2 0 0016.76 4H7.24a2 2 0 00-1.79 1.11z"/></svg>,
    mic: <svg {...s} viewBox="0 0 24 24" {...p}><path d="M12 2a3 3 0 00-3 3v7a3 3 0 006 0V5a3 3 0 00-3-3z"/><path d="M19 10v2a7 7 0 01-14 0v-2M12 19v3M8 22h8"/></svg>,
    tag: <svg {...s} viewBox="0 0 24 24" {...p}><path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>,
    heart: <svg {...s} viewBox="0 0 24 24" {...p}><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/></svg>,
    settings: <svg {...s} viewBox="0 0 24 24" {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>,
    scale: <svg {...s} viewBox="0 0 24 24" {...p}><path d="M12 3v18M3 9l4-3 5 4 5-4 4 3M5 20h14"/><path d="M6 12H2l4 7h12l4-7h-4"/></svg>,
    clock: <svg {...s} viewBox="0 0 24 24" {...p}><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>,
    building: <svg {...s} viewBox="0 0 24 24" {...p}><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M3 9h18M3 15h18M15 3v18"/></svg>,
    lightbulb: <svg {...s} viewBox="0 0 24 24" {...p}><path d="M9 21h6M12 3a6 6 0 016 6c0 2.22-1.21 4.16-3 5.2V17H9v-2.8A6.002 6.002 0 0112 3z"/></svg>,
  };
  return icons[name] || null;
}

/* ══ STARFIELD — more shooting stars ══ */
function Starfield() {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current; if (!c) return;
    const ctx = c.getContext("2d");
    let raf;
    const resize = () => { c.width = c.offsetWidth; c.height = c.offsetHeight; };
    resize();
    const stars = Array.from({ length: 380 }, () => ({
      x: Math.random(), y: Math.random(),
      r: Math.random() * 1.5 + 0.2,
      twinkle: Math.random() * Math.PI * 2,
      speed: Math.random() * 0.018 + 0.004,
      color: Math.random() > 0.8 ? "#c4b5fd" : Math.random() > 0.6 ? "#e9d5ff" : "#fff",
    }));
    const shooters = Array.from({ length: 9 }, (_, idx) => ({
      x: Math.random() * 0.6, y: Math.random() * 0.5,
      len: Math.random() * 180 + 80, speed: Math.random() * 5 + 3,
      angle: Math.PI / 5.5 + (Math.random() - 0.5) * 0.35,
      active: false,
      timer: Math.random() * 260 + 50 + idx * 90,
      alpha: 0,
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
          s.alpha -= 0.012;
          if (s.alpha <= 0 || s.x > 1.1) {
            s.active = false;
            s.x = Math.random() * 0.55;
            s.y = Math.random() * 0.45;
            s.timer = Math.random() * 350 + 80;
            s.angle = Math.PI / 5.5 + (Math.random() - 0.5) * 0.35;
            s.len = Math.random() * 180 + 80;
          }
          ctx.save(); ctx.globalAlpha = s.alpha;
          const g = ctx.createLinearGradient(
            s.x*c.width, s.y*c.height,
            (s.x - Math.cos(s.angle)*s.len/c.width)*c.width,
            (s.y - Math.sin(s.angle)*s.len/c.height)*c.height
          );
          g.addColorStop(0, "#e9d5ff"); g.addColorStop(1, "transparent");
          ctx.beginPath();
          ctx.moveTo(s.x*c.width, s.y*c.height);
          ctx.lineTo(
            (s.x - Math.cos(s.angle)*s.len/c.width)*c.width,
            (s.y - Math.sin(s.angle)*s.len/c.height)*c.height
          );
          ctx.strokeStyle = g; ctx.lineWidth = 1.8; ctx.stroke();
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

/* ══ SOLAR SYSTEM — larger canvas, vignette for smooth edges ══ */
function SolarSystem() {
  const ref = useRef(null);
  const anglesRef = useRef(AGENTS_DATA.map((_, i) => (i / AGENTS_DATA.length) * Math.PI * 2));
  const hoverRef = useRef(-1);
  const [hovered, setHovered] = useState(null);
  const tRef = useRef(0);

  useEffect(() => {
    const c = ref.current; if (!c) return;
    const ctx = c.getContext("2d");
    let raf;
    const SIZE = 1060;
    c.width = SIZE; c.height = SIZE;
    const cx = SIZE / 2, cy = SIZE / 2;

    const draw = () => {
      tRef.current += 0.008;
      const t = tRef.current;
      ctx.clearRect(0, 0, SIZE, SIZE);

      const neb = ctx.createRadialGradient(cx, cy, 0, cx, cy, 430);
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

      // Smooth radial vignette to fade edges naturally
      const vignette = ctx.createRadialGradient(cx, cy, SIZE * 0.30, cx, cy, SIZE * 0.50);
      vignette.addColorStop(0, "transparent");
      vignette.addColorStop(1, "rgba(3,1,10,0.95)");
      ctx.fillStyle = vignette;
      ctx.fillRect(0, 0, SIZE, SIZE);

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
          <div className="pl-pt-name" style={{ color: hovered.color }}>
            <Icon name={hovered.icon} size={16} style={{ display: "inline-block", marginRight: "6px", verticalAlign: "middle" }} />
            {hovered.name}
          </div>
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
  }, [t]);
  return [ref, vis];
}

/* ══ PIPELINE ══ */
function PipelineFlow() {
  const [ref, vis] = useReveal(0.05);
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);
  const [manualStep, setManualStep] = useState(null);

  const currentStep = manualStep !== null ? manualStep : active;

  useEffect(() => {
    if (!vis || paused) return;
    const id = setInterval(() => setActive(a => (a + 1) % PIPELINE.length), 1100);
    return () => clearInterval(id);
  }, [vis, paused]);

  const handleStepClick = (i) => { setPaused(true); setManualStep(i); };
  const handleResume = () => { setPaused(false); setManualStep(null); setActive(0); };
  const step = PIPELINE[currentStep];

  return (
    <div ref={ref} className="pl-pipeline-outer">
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
                <Icon name={s.icon} size={20} />
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

      <div className={`pl-pipe-detail ${vis ? "is-vis" : ""}`} key={currentStep}>
        <div className="pl-pipe-detail-icon" style={{ color: step.color }}>
          <Icon name={step.icon} size={38} />
        </div>
        <div className="pl-pipe-detail-content">
          <div className="pl-pipe-detail-step" style={{ color: step.color }}>Step {currentStep + 1} of {PIPELINE.length}</div>
          <h3 className="pl-pipe-detail-name">{step.label}</h3>
          <p className="pl-pipe-detail-sub">{step.sub}</p>
        </div>
        <div className="pl-pipe-detail-progress">
          <div className="pl-pipe-detail-bar">
            <div className="pl-pipe-detail-fill" style={{ width: `${((currentStep + 1) / PIPELINE.length) * 100}%`, background: `linear-gradient(90deg, #7c3aed, ${step.color})` }} />
          </div>
          <span className="pl-pipe-detail-pct">{Math.round(((currentStep + 1) / PIPELINE.length) * 100)}% complete</span>
        </div>
        {paused && <button className="pl-pipe-resume-btn" onClick={handleResume}>▶ Resume Auto</button>}
      </div>

      <div className="pl-pipe-dots">
        {PIPELINE.map((s, i) => (
          <button key={i} className={`pl-pipe-dot ${i === currentStep ? "active" : ""} ${i < currentStep ? "done" : ""}`} style={{ "--ac": s.color }} onClick={() => handleStepClick(i)} />
        ))}
      </div>

      {!paused && <button className="pl-pipe-pause-btn" onClick={() => setPaused(true)}>⏸ Pause</button>}
    </div>
  );
}

/* ══ AGENTS SHOWCASE ══ */
function AgentsShowcase() {
  const [ref, vis] = useReveal(0.05);
  const [selected, setSelected] = useState(null);
  const [hoveredIdx, setHoveredIdx] = useState(null);

  return (
    <div ref={ref} className="pl-agents-showcase">
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
              {selected.inputs.map((inp, i) => <div key={i} className="pl-agent-panel-item pl-api-in">{inp}</div>)}
            </div>
            <div className="pl-agent-panel-divider" />
            <div className="pl-agent-panel-col">
              <div className="pl-agent-panel-col-label">← Outputs</div>
              {selected.outputs.map((out, i) => <div key={i} className="pl-agent-panel-item pl-api-out">{out}</div>)}
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

/* ══ MAIN ══ */
export default function PublicLanding() {
  const navigate = useNavigate();
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
          <button className="pl-login-btn" onClick={() => navigate("/login")}>Log In →</button>
        </nav>

        <div className="pl-hero-body">
          <div className="pl-hero-left">
            <p className="pl-eyebrow">InnovaAI · Dubai CommerCity</p>
            <h1 className="pl-headline">
              <span className="pl-hl1">Every Complaint</span>
              <span className="pl-hl2">Handled by</span>
              <span className="pl-hl3"><Typewriter words={["AI Agents.","InnovaCX.","Nova."]} /></span>
            </h1>
            <p className="pl-hero-sub">
              InnovaCX is a multi-agent pipeline that analyzes text and audio complaints to detect customer emotions and urgency. It automatically prioritizes and routes cases to the right department delivering real-time dashboard insights that improve response times and customer satisfaction, adaptable across any communication channel.
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
        <h2 className="pl-section-h light">The Agent Pipeline</h2>
        <p className="pl-section-p light">Click any step to explore it. Watch the data flow in real-time.</p>
        <PipelineFlow />
      </section>

      {/* ══ CTA ══ */}
      <section className="pl-cta">
        <Starfield />
        <div className="pl-cta-neb" />
        <div className="pl-cta-inner">
          <div className="pl-section-tag" style={{color:"#c084fc"}}>Ready for Liftoff?</div>
          <h2 className="pl-cta-h">Every complaint resolved.<br/>Every customer retained.</h2>
          <p className="pl-cta-p">InnovaAI's AI-powered complaint management platform. Built for scale. Designed for humans.</p>
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
          <a href="https://www.instagram.com/innovacx.ai?igsh=bzVxOTNuMXUzODEz&utm_source=qr" target="_blank" rel="noopener noreferrer" className="pl-social-link" aria-label="Instagram">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <rect x="2" y="2" width="20" height="20" rx="5.5" ry="5.5" stroke="currentColor" strokeWidth="1.8" fill="none"/>
              <circle cx="12" cy="12" r="4.5" stroke="currentColor" strokeWidth="1.8" fill="none"/>
              <circle cx="17.5" cy="6.5" r="1.1" fill="currentColor"/>
            </svg>
          </a>
          <a href="https://www.tiktok.com/@innovacx" target="_blank" rel="noopener noreferrer" className="pl-social-link" aria-label="TikTok">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
              <path d="M19.59 6.69a4.83 4.83 0 01-3.77-4.25V2h-3.45v13.67a2.89 2.89 0 01-2.88 2.5 2.89 2.89 0 01-2.89-2.89 2.89 2.89 0 012.89-2.89c.28 0 .54.04.79.1V9.01a6.34 6.34 0 00-.79-.05 6.34 6.34 0 00-6.34 6.34 6.34 6.34 0 006.34 6.34 6.34 6.34 0 006.33-6.34V8.75a8.28 8.28 0 004.84 1.54V6.84a4.85 4.85 0 01-1.07-.15z"/>
            </svg>
          </a>
          <a href="https://www.linkedin.com/in/innovacx-ai-7b55853a2?utm_source=share_via&utm_content=profile&utm_medium=member_ios" target="_blank" rel="noopener noreferrer" className="pl-social-link" aria-label="LinkedIn">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <rect x="2" y="2" width="20" height="20" rx="4" stroke="currentColor" strokeWidth="1.8" fill="none"/>
              <path d="M7 10v7M7 7v.01M11 17v-4a2 2 0 014 0v4M11 10v7" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </a>
        </div>
        <p className="pl-footer-copy">© 2026 InnovaAI · Dubai CommerCity. All rights reserved.</p>
      </footer>
    </div>
  );
}