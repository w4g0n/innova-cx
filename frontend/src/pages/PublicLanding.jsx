import { useNavigate } from "react-router-dom";
import { useEffect, useRef, useState } from "react";
import novaLogo from "../assets/nova-logo.png";
import "./PublicLanding.css";

const AGENTS_DATA = [
  { name: "Recurrence",            role: "History Detection",       model: "DB Lookup",         color: "#f472b6", icon: "settings",
    details: "Cross-references incoming tickets against historical records to detect repeated issues and flag recurring complaints." },
  { name: "Subject Generation",    role: "Topic Extraction",        model: "DeBERTa NLI",       color: "#4fc3f7", icon: "tag",
    details: "Determines the core subject of the ticket so the system can follow the correct downstream workflow." },
  { name: "Suggested Resolution",  role: "Resolution Draft",        model: "Qwen",              color: "#a855f7", icon: "lightbulb",
    details: "Generates a suggested resolution for the assigned employee to approve, edit, or reject — and retrains on every correction." },
  { name: "Classification",        role: "Complaint / Inquiry",     model: "DeBERTa NLI",       color: "#fbbf24", icon: "tag",
    details: "Classifies the ticket as a Complaint or Inquiry so the correct workflow path is followed. Bypassed when type is already known." },
  { name: "Sentiment Analysis",    role: "Emotion Detection",       model: "RoBERTa",           color: "#e879f9", icon: "heart",
    details: "Reads ticket text and produces a continuous sentiment score from −1 to +1, capturing tone, frustration, and urgency cues." },
  { name: "Audio Analysis",        role: "Voice Sentiment",         model: "Librosa",           color: "#34d399", icon: "mic",
    details: "Processes raw audio waveforms to extract emotional tone directly from speech — pitch, energy, and zero-crossing rate." },
  { name: "Feature Engineering",   role: "Urgency & Impact",        model: "DeBERTa NLI",       color: "#e8b87a", icon: "settings",
    details: "Infers five operational labels in parallel — safety concern, severity, urgency, business impact, and recurrence — from ticket text." },
  { name: "Prioritization Engine", role: "Priority Scoring",        model: "XGBoost",           color: "#d4b96a", icon: "scale",
    details: "Assigns Critical, High, Medium, or Low priority using engineered ticket signals. Relearns from every employee rescore." },
  { name: "Department Routing",    role: "Department Assignment",   model: "DeBERTa NLI",       color: "#7de8e8", icon: "building",
    details: "Assigns a confidence score across all departments. Above 0.7 the ticket is auto-routed; below that it goes for manager approval." },
  { name: "Review",                role: "Quality Check",           model: "Qwen",              color: "#f87171", icon: "clock",
    details: "Validates the completed ticket payload — checking SLA targets, routing decisions, and priority — before final handoff to the employee." },
  { name: "Sentiment Combiner",    role: "Signal Fusion",           model: "Fusion module",     color: "#a3e635", icon: "heart",
    details: "Fuses text and audio sentiment into a single score. With audio: (Audio × 0.5) + (Text × 0.5). Without audio: text sentiment is used directly." },
];


const PIPELINE = [
{ icon: "inbox",    label: "Chatbot",           sub: "Qwen · Nova",                      color: "#c084fc" },
{ icon: "tag",      label: "Create Ticket",     sub: "Qwen chatbot or form",             color: "#a78bfa" },
{ icon: "question", label: "Recurrence Check",  sub: "Transformer · DB lookup",          color: "#f472b6" },
{ icon: "tag",      label: "Classify",          sub: "Complaint / Inquiry",              color: "#fbbf24" },
{ icon: "heart",    label: "Sentiment",         sub: "RoBERTa + Librosa",                color: "#e879f9" },
{ icon: "settings", label: "Feature Eng.",      sub: "Urgency · Impact · Risk",          color: "#e8b87a" },
{ icon: "scale",    label: "Prioritise",        sub: "XGBoost scoring",                  color: "#d4b96a" },
{ icon: "clock",    label: "SLA",               sub: "Auto-escalation",                  color: "#d946ef" },
{ icon: "building", label: "Route",             sub: "Qwen department routing",          color: "#7de8e8" },
{ icon: "lightbulb",label: "Resolution",        sub: "Qwen suggested resolution",        color: "#a855f7" },
];

const PLANET_3D = [
  // 0: Recurrence — Mars-like: rust-pink, history scars
  { color: "#f472b6", radius: 0.42, orbitR: 3.0,  speed: 0.011,  tiltX:-0.12,  tiltZ: -0.06, startAngle: 0.0,
    personality: 'mars' },
  // 1: Subject Generation — Mercury-like: small, precise
  { color: "#4fc3f7", radius: 0.46, orbitR: 4.4,  speed: 0.009,  tiltX: 0.20,  tiltZ:  0.08, startAngle: 1.1,
    personality: 'mercury' },
  // 2: Suggested Resolution — Venus-like: bright, warm
  { color: "#a855f7", radius: 0.56, orbitR: 5.8,  speed: 0.008,  tiltX: 0.18,  tiltZ: -0.10, startAngle: 2.0,
    personality: 'venus' },
  // 3: Classification — Earth-like: structured, analytical
  { color: "#fbbf24", radius: 0.54, orbitR: 7.2,  speed: 0.007,  tiltX: 0.28,  tiltZ:  0.12, startAngle: 2.9,
    personality: 'earth' },
  // 4: Sentiment Analysis — Uranus-like: smooth emotional cyan
  { color: "#e879f9", radius: 0.58, orbitR: 8.6,  speed: 0.006,  tiltX:-0.30,  tiltZ: -0.11, startAngle: 3.8,
    personality: 'uranus' },
  // 5: Audio Analysis — Mercury-like: small, signal processing
  { color: "#34d399", radius: 0.40, orbitR: 10.0, speed: 0.0055, tiltX: 0.16,  tiltZ:  0.09, startAngle: 4.6,
    personality: 'mercury' },
  // 6: Feature Engineering — Jupiter-like: large, complex, banded
  { color: "#e8b87a", radius: 0.85, orbitR: 11.5, speed: 0.005,  tiltX: 0.22,  tiltZ:  0.15, startAngle: 5.3,
    personality: 'jupiter' },
  // 7: Prioritization Engine — Saturn-like: pale gold, prominent rings
  { color: "#d4b96a", radius: 0.72, orbitR: 13.2, speed: 0.0042, tiltX:-0.30,  tiltZ: -0.12, startAngle: 0.5,
    personality: 'saturn' },
  // 8: Department Routing — Neptune-like: deep blue, directed
  { color: "#7de8e8", radius: 0.62, orbitR: 14.8, speed: 0.0035, tiltX: 0.17,  tiltZ:  0.09, startAngle: 1.4,
    personality: 'neptune' },
  // 9: Review — Mars-like: warm final check
  { color: "#f87171", radius: 0.46, orbitR: 16.2, speed: 0.003,  tiltX:-0.18,  tiltZ: -0.08, startAngle: 2.3,
    personality: 'mars' },
  // 10: Sentiment Combiner — Earth-like: fusion of signals
  { color: "#a3e635", radius: 0.52, orbitR: 17.5, speed: 0.0028, tiltX: 0.24,  tiltZ:  0.13, startAngle: 3.2,
    personality: 'earth' },
];

function Icon({ name, size = 20 }) {
  const s = { width: size, height: size };
  const p = { fill: "none", stroke: "currentColor", strokeWidth: "1.8", strokeLinecap: "round", strokeLinejoin: "round" };
  const icons = {
    inbox:     <svg {...s} viewBox="0 0 24 24" {...p}><polyline points="22 12 16 12 14 15 10 15 8 12 2 12"/><path d="M5.45 5.11L2 12v6a2 2 0 002 2h16a2 2 0 002-2v-6l-3.45-6.89A2 2 0 0016.76 4H7.24a2 2 0 00-1.79 1.11z"/></svg>,
    mic:       <svg {...s} viewBox="0 0 24 24" {...p}><path d="M12 2a3 3 0 00-3 3v7a3 3 0 006 0V5a3 3 0 00-3-3z"/><path d="M19 10v2a7 7 0 01-14 0v-2M12 19v3M8 22h8"/></svg>,
    tag:       <svg {...s} viewBox="0 0 24 24" {...p}><path d="M20.59 13.41l-7.17 7.17a2 2 0 01-2.83 0L2 12V2h10l8.59 8.59a2 2 0 010 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>,
    heart:     <svg {...s} viewBox="0 0 24 24" {...p}><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/></svg>,
    settings:  <svg {...s} viewBox="0 0 24 24" {...p}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>,
    scale:     <svg {...s} viewBox="0 0 24 24" {...p}><path d="M12 3v18M3 9l4-3 5 4 5-4 4 3M5 20h14"/><path d="M6 12H2l4 7h12l4-7h-4"/></svg>,
    clock:     <svg {...s} viewBox="0 0 24 24" {...p}><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>,
    building:  <svg {...s} viewBox="0 0 24 24" {...p}><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M9 3v18M3 9h18M3 15h18M15 3v18"/></svg>,
    lightbulb: <svg {...s} viewBox="0 0 24 24" {...p}><path d="M9 21h6M12 3a6 6 0 016 6c0 2.22-1.21 4.16-3 5.2V17H9v-2.8A6.002 6.002 0 0112 3z"/></svg>,
    question:  <svg {...s} viewBox="0 0 24 24" {...p}><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 015.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>,
  };
  return icons[name] || null;
}

/* ══ STARFIELD ══ */
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
      active: false, timer: Math.random() * 260 + 50 + idx * 90, alpha: 0,
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
            s.active = false; s.x = Math.random() * 0.55; s.y = Math.random() * 0.45;
            s.timer = Math.random() * 350 + 80;
            s.angle = Math.PI / 5.5 + (Math.random() - 0.5) * 0.35;
            s.len = Math.random() * 180 + 80;
          }
          ctx.save(); ctx.globalAlpha = s.alpha;
          const g = ctx.createLinearGradient(s.x*c.width, s.y*c.height,
            (s.x-Math.cos(s.angle)*s.len/c.width)*c.width,
            (s.y-Math.sin(s.angle)*s.len/c.height)*c.height);
          g.addColorStop(0, "#e9d5ff"); g.addColorStop(1, "transparent");
          ctx.beginPath();
          ctx.moveTo(s.x*c.width, s.y*c.height);
          ctx.lineTo((s.x-Math.cos(s.angle)*s.len/c.width)*c.width,
            (s.y-Math.sin(s.angle)*s.len/c.height)*c.height);
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

/*  SOLAR SYSTEM  */
function SolarSystem({ onReady }) {
  const mountRef  = useRef(null);
  const labelsRef = useRef(null);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    const mount    = mountRef.current;
    const labelDiv = labelsRef.current;
    if (!mount || !labelDiv) return;

    let renderer, scene, camera, raf;
    let planetObjects = [];
    let orbitMeshes   = [];
    let raycaster, mouse;
    let selectedIdx = -1;
    let autoRotY    = 0;
    let isDragging = false;
    let prevMouse  = { x: 0, y: 0 };
    let camTheta   = 0.6;
    let camPhi     = 1.18;
    const camDist  = 44;
    let t          = 0;
    const angles   = PLANET_3D.map(p => p.startAngle);
    const labelEls = [];

    function setCamPos() {
      const THREE = window.THREE;
      camera.position.set(
        camDist * Math.sin(camPhi) * Math.cos(camTheta),
        camDist * Math.cos(camPhi),
        camDist * Math.sin(camPhi) * Math.sin(camTheta)
      );
      camera.lookAt(0, 0, 0);
    }

    function toScreen(worldPos, W, H) {
      const THREE = window.THREE;
      const v = worldPos.clone().project(camera);
      return {
        x: (v.x *  0.5 + 0.5) * W,
        y: (v.y * -0.5 + 0.5) * H,
        behind: v.z > 1,
      };
    }

    function init() {
      const THREE = window.THREE;
      const W = mount.clientWidth  || 600;
      const H = mount.clientHeight || 600;

      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
      renderer.setSize(W, H);
      renderer.setClearColor(0x000000, 0);
      renderer.domElement.style.background = "transparent";
      mount.appendChild(renderer.domElement);

      scene  = new THREE.Scene();
      camera = new THREE.PerspectiveCamera(52, W / H, 0.1, 600);
      setCamPos();

      raycaster = new THREE.Raycaster();
      mouse     = new THREE.Vector2(-9999, -9999);

      const sunLight = new THREE.PointLight(0xfff4d6, 6.5, 320);
      scene.add(sunLight);
      /* Raised ambient — deep space scatter, keeps dark sides visible */
      scene.add(new THREE.AmbientLight(0x8866aa, 0.45));

      /* SUN — self-luminous fire shader 
         Key principle: the sun emits light, it is NOT lit by anything.
         Uses ShaderMaterial with no lighting, pure emission.
         All detail sampled in 3-D sphere space — zero UV banding.
       */
      const sunVS = `
        varying vec3 vPos;
        void main(){
          vPos = position;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);
        }
      `;
      const sunFS = `
        uniform float uTime;
        varying vec3 vPos;

        float hash(vec3 p){
          p = fract(p * vec3(443.897, 441.423, 437.195));
          p += dot(p, p.yzx + 19.19);
          return fract((p.x+p.y)*p.z);
        }
        float n3(vec3 p){
          vec3 i=floor(p), f=fract(p), u=f*f*(3.0-2.0*f);
          return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),u.x),mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),u.x),u.y),
                     mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),u.x),mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),u.x),u.y),u.z);
        }
        /* Rotated FBM — breaks up axis-aligned patterns */
        float fbm(vec3 p){
          mat3 m = mat3( 0.00, 0.80, 0.60,
                        -0.80, 0.36,-0.48,
                        -0.60,-0.48, 0.64);
          float v=0.0, a=0.5;
          for(int i=0;i<7;i++){ v+=a*n3(p); p=m*p*2.01; a*=0.5; }
          return v;
        }
        /* Domain-warped FBM — gives fire's churning, billowing look */
        float fireFbm(vec3 p){
          vec3 q = vec3(fbm(p + vec3(0.0,0.0,0.0)),
                        fbm(p + vec3(5.2,1.3,2.8)),
                        fbm(p + vec3(1.7,9.2,3.4)));
          return fbm(p + 2.8*q);
        }

        /* 3-D Voronoi for granulation */
        float voronoi(vec3 p){
          vec3 b=floor(p); float d=8.0;
          for(int z=-1;z<=1;z++)for(int y=-1;y<=1;y++)for(int x=-1;x<=1;x++){
            vec3 n=b+vec3(x,y,z);
            vec3 r=vec3(hash(n),hash(n+3.7),hash(n+7.3));
            r=0.5+0.5*sin(uTime*0.10+6.28*r);
            d=min(d,length(vec3(x,y,z)+r-fract(p)));
          }
          return d;
        }

        void main(){
          vec3 sp = normalize(vPos); /* unit sphere — 3-D texture coords */

          /* ── TRUE limb darkening ──
             The sun IS bright all over. Limb darkening is just ~20% reduction
             at the very edge because we see cooler, less dense atmosphere.
             We measure it by how "edge-on" this surface point is to the camera. */
          float r2d = length(vPos.xy) / 1.8;         /* 0=centre, 1=limb in screen */
          r2d = clamp(r2d, 0.0, 1.0);
          /* Quadratic limb darkening law (Eddington): I(r) = 1 - u(1 - sqrt(1-r²)) */
          float u_ld = 0.55;
          float limbDark = 1.0 - u_ld*(1.0 - sqrt(max(0.0, 1.0 - r2d*r2d)));
          /* Boost the centre, pull edge down only slightly — sun is bright EVERYWHERE */
          limbDark = mix(0.78, 1.0, limbDark);

          /* ── Surface fire / plasma turbulence ──
             Domain-warped FBM gives the billowing, churning fire look. */
          float speed = uTime * 0.08;
          vec3 fc1 = sp*3.5 + vec3(speed*0.9, speed*0.7, speed*0.5);
          vec3 fc2 = sp*7.0 + vec3(-speed*1.1, speed*0.8, -speed*0.6);
          float fire1 = fireFbm(fc1);
          float fire2 = fireFbm(fc2);
          float fire  = fire1*0.65 + fire2*0.35;

          vec3 gp = sp*5.5 + vec3(uTime*0.015, uTime*0.011, uTime*0.009);
          float gran = voronoi(gp);
          /* Cell borders bright (rising hot plasma), centres slightly darker */
          gran = 1.0 - smoothstep(0.04, 0.40, gran)*0.25;

          vec3 sc1=normalize(vec3(sin(uTime*0.05),      sin(uTime*0.03)*0.55,  cos(uTime*0.05)));
          vec3 sc2=normalize(vec3(sin(uTime*0.04+2.09), sin(uTime*0.035)*0.50, cos(uTime*0.04+2.09)));
          float a1=acos(clamp(dot(sp,sc1),-1.0,1.0));
          float a2=acos(clamp(dot(sp,sc2),-1.0,1.0));
          /* Tiny spots: umbra radius ~0.04 rad, penumbra to ~0.08 — not giant blobs */
          float spot1 = mix(0.72, 1.0, smoothstep(0.02, 0.08, a1));
          float spot2 = mix(0.76, 1.0, smoothstep(0.02, 0.07, a2));
          float spots = spot1 * spot2;

          /* ── Fire colour palette — fully smooth, no if/else branches ──
             Use smoothstep blends so there are zero sharp colour transitions.
             Everything stays in warm orange-yellow-white range. */
          vec3 cWhite  = vec3(1.00, 0.95, 0.78);  /* bright yellow-white core */
          vec3 cYellow = vec3(1.00, 0.80, 0.35);  /* warm golden yellow */
          vec3 cOrange = vec3(1.00, 0.55, 0.10);  /* deep orange */

          float f = clamp(fire, 0.0, 1.0);
          /* Smooth two-stage blend — no hard edges */
          vec3 col = mix(cOrange, cYellow, smoothstep(0.25, 0.60, f));
          col       = mix(col,    cWhite,  smoothstep(0.55, 0.90, f));

          /* Gran as luminance-only — don't let it pull colours toward grey */
          float granLum = 0.82 + gran * 0.18;
          col *= granLum;
          col *= spots;
          col *= limbDark;

          /* Fiery hot veins — additive bright channels, warm only */
          float veins = max(0.0, fire1 - 0.65) * 2.5;
          col += veins * vec3(1.0, 0.75, 0.30) * 0.22;

          /* Rim glow — additive warm orange at edge only */
          float rim = smoothstep(0.55, 1.0, r2d);
          col += rim * vec3(0.85, 0.30, 0.04) * 0.18;

          /* Hard clamp to warm colours — zero chance of grey/green/blue */
          col.r = max(col.r, 0.52);
          col.g = max(col.g, col.r * 0.38);
          col.b = max(col.b, 0.0);
          col.b = min(col.b, col.g * 0.35);   /* kill any blue creep */

          col *= 0.97 + 0.03*sin(uTime*1.1);
          gl_FragColor = vec4(col, 1.0);
        }
      `;
      const sunUniforms = { uTime: { value: 0 } };
      const sun = new THREE.Mesh(
        new THREE.SphereGeometry(1.8, 96, 96),
        new THREE.ShaderMaterial({
          vertexShader: sunVS,
          fragmentShader: sunFS,
          uniforms: sunUniforms,
          lights: false,
        })
      );
      scene.add(sun);

      // Orchestrator label — always centered on the sun
      const sunLabelEl = document.createElement("div");
      sunLabelEl.className = "pl-planet-label";
      sunLabelEl.textContent = "Orchestrator";
      sunLabelEl.style.fontSize = "11px";
      sunLabelEl.style.padding = "3px 9px";
      sunLabelEl.style.borderRadius = "5px";
      sunLabelEl.style.background = "rgba(30, 10, 0, 0.90)";
      sunLabelEl.style.border = "1px solid rgba(255, 180, 50, 0.70)";
      sunLabelEl.style.boxShadow = "0 0 12px rgba(255, 160, 30, 0.40)";
      sunLabelEl.style.color = "#ffd580";
      sunLabelEl.style.fontWeight = "700";
      sunLabelEl.style.letterSpacing = "0.05em";
      labelDiv.appendChild(sunLabelEl);

      const coronaVS = `
        varying vec3 vPos;
        void main(){ vPos=position; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }
      `;
      const coronaFS = `
        varying vec3 vPos;
        void main(){
          /* r = 0 at sun surface (scale 1.0), 1 at outer edge of this sphere */
          float r = (length(vPos) - 1.8) / (1.8 * 3.0); /* normalised 0→1 over 3× radius */
          r = clamp(r, 0.0, 1.0);
          /* Exponential falloff — bright near surface, fades to nothing smoothly */
          float alpha = exp(-r * 4.5) * 0.55;
          /* Warm amber-white corona colour */
          vec3 col = mix(vec3(1.0, 0.90, 0.60), vec3(1.0, 0.65, 0.20), r);
          gl_FragColor = vec4(col, alpha);
        }
      `;
      const coronaMesh = new THREE.Mesh(
        new THREE.SphereGeometry(1.8 * 4.8, 48, 48),
        new THREE.ShaderMaterial({
          vertexShader: coronaVS,
          fragmentShader: coronaFS,
          transparent: true,
          side: THREE.BackSide,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
          lights: false,
        })
      );
      scene.add(coronaMesh);

      /*  PLANET TEXTURE ENGINE 
         Each planet has a handcrafted personality matching a real solar system body.
         Uses 3D sphere-mapped FBM noise — no axis-aligned banding ever.
         Contrast is kept subtle so surfaces look painterly, not noisy.
       */

      function h21(x, y, s) {
        // deterministic hash → [0,1]
        const n = Math.sin(x * 127.1 + y * 311.7 + s * 74.3) * 43758.5453;
        return n - Math.floor(n);
      }

      // 3-D value noise (sphere coords, never bands)
      function sn(lat, lon, sc, s) {
        const cx = Math.cos(lat)*Math.cos(lon)*sc;
        const cy = Math.cos(lat)*Math.sin(lon)*sc;
        const cz = Math.sin(lat)*sc;
        const ix=Math.floor(cx),iy=Math.floor(cy),iz=Math.floor(cz);
        const fx=cx-ix,fy=cy-iy,fz=cz-iz;
        const ux=fx*fx*(3-2*fx),uy=fy*fy*(3-2*fy),uz=fz*fz*(3-2*fz);
        const v = (dx,dy,dz) => h21(ix+dx+(iy+dy)*7+(iz+dz)*13, s, 0);
        return v(0,0,0)*(1-ux)*(1-uy)*(1-uz)+v(1,0,0)*ux*(1-uy)*(1-uz)
              +v(0,1,0)*(1-ux)*uy*(1-uz)     +v(1,1,0)*ux*uy*(1-uz)
              +v(0,0,1)*(1-ux)*(1-uy)*uz     +v(1,0,1)*ux*(1-uy)*uz
              +v(0,1,1)*(1-ux)*uy*uz         +v(1,1,1)*ux*uy*uz;
      }

      // FBM from sphere noise — gentle falloff to keep contrast moderate
      function fbm(lat, lon, oct, sc, s) {
        let v=0,a=0.5,sm=sc,mx=0;
        for(let i=0;i<oct;i++){v+=a*sn(lat,lon,sm,s+i*31);mx+=a;a*=0.48;sm*=2.05;}
        return v/mx;
      }

      // Smooth mix helper
      const sm = (a,b,t) => a+(b-a)*Math.max(0,Math.min(1,t));

      function makePlanetTexture(THREE, personality, seed) {
        const TW=512, TH=256;
        const px4 = new Uint8Array(TW*TH*4);
        const bm4 = new Uint8Array(TW*TH*4);

        for(let py=0;py<TH;py++) for(let lpx=0;lpx<TW;lpx++) {
          const lat = ((py/TH)-0.5)*Math.PI;
          const lon = (lpx/TW)*Math.PI*2;
          const absLat = Math.abs(lat)/(Math.PI/2); // 0 equator → 1 pole
          let r,g,b;

          if(personality==='mercury') {
            const terrain = fbm(lat,lon,5,3.0,seed);
            const detail  = fbm(lat,lon,3,7.0,seed+50);
            const h = terrain*0.6+detail*0.4;
            // Base: warm grey
            const base = 0.38+h*0.38;
            r = base*1.05; g = base*0.98; b = base*0.90;
            // Crater pits: high-freq noise spikes → dark rings
            const cr = fbm(lat,lon,2,11.0,seed+200);
            if(cr>0.72) { const d=(cr-0.72)/0.28; r*=1-d*0.6; g*=1-d*0.6; b*=1-d*0.55; }
            // Bright ejecta rays around craters
            const ray = fbm(lat,lon,2,15.0,seed+300);
            if(ray>0.80) { const e=(ray-0.80)/0.20; r=sm(r,0.85,e*0.5); g=sm(g,0.80,e*0.5); b=sm(b,0.72,e*0.5); }

          } else if(personality==='venus') {
            const c1 = fbm(lat,lon*0.9+lat*0.3,5,2.0,seed);
            const c2 = fbm(lat+c1*0.5,lon,4,4.0,seed+80);
            const cloud = c1*0.55+c2*0.45;
            // Cream-yellow base, darker swirl troughs
            r = 0.82+cloud*0.17;
            g = 0.68+cloud*0.18;
            b = 0.22+cloud*0.14;
            // Bright pole hazes
            if(absLat>0.72) { const p=(absLat-0.72)/0.28; r=sm(r,0.95,p); g=sm(g,0.88,p); b=sm(b,0.55,p); }

          } else if(personality==='earth') {
            const cont = fbm(lat,lon,6,2.2,seed);      // continent mask
            const cld  = fbm(lat,lon,4,3.5,seed+400);  // cloud layer
            const isLand = cont > 0.52;
            if(isLand) {
              // Land: mix green lowlands → brown highlands
              const h = (cont-0.52)/0.48;
              r = sm(0.30,0.52,h); g = sm(0.42,0.36,h); b = sm(0.18,0.20,h);
            } else {
              // Ocean: deep blue, shallows slightly lighter
              const depth = cont/0.52;
              r = sm(0.04,0.12,depth); g = sm(0.18,0.38,depth); b = sm(0.55,0.72,depth);
            }
            // Cloud overlay — white patches
            if(cld>0.58) { const cv=(cld-0.58)/0.42; r=sm(r,0.90,cv*0.85); g=sm(g,0.92,cv*0.85); b=sm(b,0.95,cv*0.85); }
            // Polar ice caps with noisy edge
            if(absLat>0.76) { const ic=fbm(lat,lon,3,4,seed+600); const p=(absLat-0.76)/0.24*(0.7+ic*0.3); r=sm(r,0.92,p); g=sm(g,0.95,p); b=sm(b,1.0,p); }

          } else if(personality==='mars') {
            const terrain = fbm(lat,lon,5,2.5,seed);
            const detail  = fbm(lat,lon,4,6.0,seed+60);
            const h = terrain*0.65+detail*0.35;
            // Rust base
            r = 0.62+h*0.28;
            g = 0.22+h*0.16;
            b = 0.10+h*0.08;
            // Dark volcanic lowlands
            if(h<0.38) { const d=(0.38-h)/0.38; r*=1-d*0.35; g*=1-d*0.3; b*=1-d*0.2; }
            // Valles Marineris-like canyon — dark scar near equator
            const canyonLat = Math.abs(lat)<0.18 ? 1 : 0;
            const canyonNoise = fbm(lat,lon,3,5,seed+150);
            if(canyonLat && canyonNoise>0.70) { const cn=(canyonNoise-0.70)/0.30; r*=1-cn*0.5; g*=1-cn*0.45; b*=1-cn*0.3; }
            // Small polar CO2 caps — white-ish
            if(absLat>0.82) { const p=(absLat-0.82)/0.18; r=sm(r,0.88,p); g=sm(g,0.82,p); b=sm(b,0.78,p); }

          } else if(personality==='jupiter') {
            // Warp latitude with FBM for organic band edges
            const warp = fbm(lat,lon,3,1.5,seed+10)*1.2-0.6;
            const wlat = lat+warp*0.55;
            // Wide gentle bands via smooth sin (low freq = fewer stripes)
            const band = Math.sin(wlat*4.5)*0.5+0.5;
            const turb = fbm(lat,lon,4,3.0,seed+100)*0.28;
            const mix  = band*0.72+turb;
            // Color palette: cream ↔ warm brown ↔ amber
            r = sm(0.68,0.92,mix);
            g = sm(0.38,0.74,mix);
            b = sm(0.18,0.50,mix);
            // Great Red Spot — warm oval near -20° lat
            const grsLat=-0.34, grsLon=Math.PI*1.1;
            const dL=(lat-grsLat)*4.0;
            const dO=Math.min(Math.abs(lon-grsLon),Math.PI*2-Math.abs(lon-grsLon))*2.2;
            const grs=dL*dL+dO*dO;
            if(grs<0.20) { const gi=(0.20-grs)/0.20; r=sm(r,0.82,gi*0.9); g=sm(g,0.28,gi*0.7); b=sm(b,0.18,gi*0.5); }

          } else if(personality==='saturn') {
            const warp = fbm(lat,lon,3,1.2,seed+15)*0.8-0.4;
            const wlat = lat+warp*0.4;
            const band = Math.sin(wlat*3.5)*0.5+0.5;
            const turb = fbm(lat,lon,3,2.5,seed+120)*0.20;
            const mix  = band*0.80+turb;
            // Pale golden palette
            r = sm(0.72,0.90,mix);
            g = sm(0.62,0.80,mix);
            b = sm(0.30,0.48,mix);
            // Subtle polar hexagon-ish darkening
            if(absLat>0.85) { const p=(absLat-0.85)/0.15; r*=1-p*0.15; g*=1-p*0.18; }

          } else if(personality==='uranus') {
            const smooth = fbm(lat,lon,3,1.5,seed)*0.18; // very low contrast
            const faint  = Math.sin(lat*3.0)*0.08;       // barely visible bands
            const h = 0.50+smooth+faint;
            // Cyan-teal palette — uniform and calm
            r = sm(0.42,0.62,h)*0.80;
            g = sm(0.72,0.90,h);
            b = sm(0.78,0.95,h);
            // Faint polar brightening
            if(absLat>0.70) { const p=(absLat-0.70)/0.30; r=sm(r,0.72,p*0.4); g=sm(g,0.95,p*0.3); b=sm(b,1.0,p*0.3); }

          } else { // neptune
            const turb = fbm(lat,lon,5,2.8,seed);
            const streak = fbm(lat,lon*1.4,3,5.0,seed+200);
            // Deep blue base
            r = 0.05+turb*0.12;
            g = 0.12+turb*0.20;
            b = 0.62+turb*0.28;
            // Bright white cloud streaks (high-freq, elongated along longitude)
            if(streak>0.68) { const s=(streak-0.68)/0.32; r=sm(r,0.85,s*0.7); g=sm(g,0.88,s*0.7); b=sm(b,0.95,s*0.5); }
            // Great Dark Spot — deep blue-black oval
            const gdsLat=0.22, gdsLon=Math.PI*0.5;
            const dL=(lat-gdsLat)*5.0;
            const dO=Math.min(Math.abs(lon-gdsLon),Math.PI*2-Math.abs(lon-gdsLon))*2.8;
            const gds=dL*dL+dO*dO;
            if(gds<0.15) { const gi=(0.15-gds)/0.15; r*=1-gi*0.7; g*=1-gi*0.6; b=sm(b,0.38,gi*0.5); }
          }

          // Clamp
          const idx=(py*TW+lpx)*4;
          px4[idx]  =Math.max(0,Math.min(255,Math.round(r*255)));
          px4[idx+1]=Math.max(0,Math.min(255,Math.round(g*255)));
          px4[idx+2]=Math.max(0,Math.min(255,Math.round(b*255)));
          px4[idx+3]=255;
        }

        // Bump map — always from same FBM for consistent relief
        for(let py=0;py<TH;py++) for(let lpx=0;lpx<TW;lpx++) {
          const lat=((py/TH)-0.5)*Math.PI;
          const lon=(lpx/TW)*Math.PI*2;
          const h=fbm(lat,lon,4,3.0,seed+500);
          const v=Math.round(h*255);
          const bi=(py*TW+lpx)*4;
          bm4[bi]=v;bm4[bi+1]=v;bm4[bi+2]=v;bm4[bi+3]=255;
        }

        const tex =new THREE.DataTexture(px4,TW,TH,THREE.RGBAFormat); tex.needsUpdate=true;
        const bump=new THREE.DataTexture(bm4,TW,TH,THREE.RGBAFormat); bump.needsUpdate=true;
        return {tex,bump};
      }

      /*  PLANETS  */
      PLANET_3D.forEach((cfg, i) => {
        const hex = cfg.color;
        const r   = parseInt(hex.slice(1,3),16)/255;
        const g   = parseInt(hex.slice(3,5),16)/255;
        const b   = parseInt(hex.slice(5,7),16)/255;

        const pts = [];
        for (let s = 0; s <= 256; s++) {
          const a = (s / 256) * Math.PI * 2;
          pts.push(new THREE.Vector3(Math.cos(a)*cfg.orbitR, 0, Math.sin(a)*cfg.orbitR));
        }
        const orbitLine = new THREE.LineLoop(
          new THREE.BufferGeometry().setFromPoints(pts),
          new THREE.LineBasicMaterial({
            color: new THREE.Color(0.48, 0.18, 0.80),
            transparent: true, opacity: 0.38,
            blending: THREE.AdditiveBlending, depthWrite: false,
          })
        );
        orbitLine.rotation.x = cfg.tiltX;
        orbitLine.rotation.z = cfg.tiltZ;
        scene.add(orbitLine);
        orbitMeshes.push(orbitLine);

        const orbitPivot = new THREE.Object3D();
        orbitPivot.rotation.x = cfg.tiltX;
        orbitPivot.rotation.z = cfg.tiltZ;
        scene.add(orbitPivot);
        const innerPivot = new THREE.Object3D();
        orbitPivot.add(innerPivot);

        // Per-personality material properties
        const matProps = {
          mercury: { bumpScale:0.8, shininess:8,  specular:[0.20,0.18,0.15] },
          venus:   { bumpScale:0.2, shininess:45, specular:[0.55,0.45,0.20] },
          earth:   { bumpScale:0.5, shininess:30, specular:[0.20,0.35,0.60] },
          mars:    { bumpScale:0.7, shininess:10, specular:[0.25,0.12,0.08] },
          jupiter: { bumpScale:0.15,shininess:18, specular:[0.30,0.22,0.12] },
          saturn:  { bumpScale:0.12,shininess:22, specular:[0.35,0.28,0.15] },
          uranus:  { bumpScale:0.08,shininess:60, specular:[0.40,0.65,0.75] },
          neptune: { bumpScale:0.25,shininess:40, specular:[0.20,0.30,0.70] },
        };
        const mp = matProps[cfg.personality] || matProps.mercury;

        const { tex, bump } = makePlanetTexture(THREE, cfg.personality, i + 1);
        const mat = new THREE.MeshPhongMaterial({
          map: tex, bumpMap: bump, bumpScale: mp.bumpScale,
          emissive: new THREE.Color(r*0.05, g*0.03, b*0.08),
          specular: new THREE.Color(...mp.specular),
          shininess: mp.shininess,
        });

        const mesh = new THREE.Mesh(new THREE.SphereGeometry(cfg.radius, 64, 64), mat);
        mesh.position.set(cfg.orbitR, 0, 0);
        innerPivot.add(mesh);

        // Saturn-style rings on planet index 7 (Prioritization Engine — saturn personality)
        if (i === 7) {
          const ringMat = new THREE.MeshBasicMaterial({
            color: new THREE.Color(0.72, 0.60, 0.35),
            transparent: true, opacity: 0.55, side: THREE.DoubleSide,
            blending: THREE.AdditiveBlending, depthWrite: false,
          });
          const ring = new THREE.Mesh(new THREE.RingGeometry(cfg.radius*1.52, cfg.radius*2.55, 80), ringMat);
          ring.rotation.x = Math.PI * 0.38;
          mesh.add(ring);
          const ring2 = new THREE.Mesh(
            new THREE.RingGeometry(cfg.radius*2.6, cfg.radius*3.1, 80),
            new THREE.MeshBasicMaterial({ color: new THREE.Color(0.55, 0.44, 0.22),
              transparent: true, opacity: 0.25, side: THREE.DoubleSide,
              blending: THREE.AdditiveBlending, depthWrite: false })
          );
          ring2.rotation.x = Math.PI * 0.38;
          mesh.add(ring2);
        }

        const labelAnchor = new THREE.Object3D();
        labelAnchor.position.set(cfg.orbitR, cfg.radius + 0.7, 0);
        innerPivot.add(labelAnchor);

        // HTML label — purple theme
        const el = document.createElement("div");
        el.className = "pl-planet-label";
        el.textContent = AGENTS_DATA[i].name;
        el.style.setProperty("--pc", "#a855f7");
        el.style.fontSize = "10px";
        el.style.padding = "2px 7px";
        el.style.borderRadius = "5px";
        el.style.background = "rgba(20, 4, 40, 0.88)";
        el.style.border = "1px solid rgba(168, 85, 247, 0.65)";
        el.style.boxShadow = "0 0 10px rgba(168, 85, 247, 0.35)";
        el.style.color = "#e9d5ff";
        el.style.fontWeight = "700";
        el.style.letterSpacing = "0.04em";
        labelDiv.appendChild(el);
        labelEls.push(el);

        planetObjects.push({ mesh, labelAnchor, orbitPivot, innerPivot, cfg, idx: i, mat, r, g, b });
      });

      /* REALISTIC ASTEROIDS
         Uses deformed geometry (perturbed vertices) + a rocky material.
         Each asteroid is a unique irregular chunk, not a smooth sphere.
       */

      // Seeded pseudo-random
      function srand(seed) {
        let s = seed | 0;
        return () => { s = (s * 1664525 + 1013904223) & 0xffffffff; return (s >>> 0) / 0xffffffff; };
      }

      // Create an irregular asteroid geometry by deforming a low-poly sphere
      function makeAsteroidGeometry(THREE, baseRadius, seed) {
        const rand = srand(seed);
        // Use an icosahedron for natural faceted look
        const detail = Math.floor(rand() * 2); // 0 or 1 subdivisions
        const geo = new THREE.IcosahedronGeometry(baseRadius, detail);

        // Deform vertices randomly for organic rock shape
        const pos = geo.attributes.position;
        for (let vi = 0; vi < pos.count; vi++) {
          const x = pos.getX(vi), y = pos.getY(vi), z = pos.getZ(vi);
          const len = Math.sqrt(x*x + y*y + z*z);
          // Perturbation: ±30% of radius, seeded per vertex
          const noise = 0.70 + rand() * 0.60;
          pos.setXYZ(vi, x/len * len * noise, y/len * len * noise, z/len * len * noise);
        }
        pos.needsUpdate = true;
        geo.computeVertexNormals();

        // Non-uniform scale to make it look more like a tumbling rock
        const sx = 0.7 + rand() * 0.7;
        const sy = 0.5 + rand() * 0.6;
        const sz = 0.6 + rand() * 0.8;
        geo.scale(sx, sy, sz);
        return geo;
      }

      const asteroidBelt = [];
      const NUM_ASTEROIDS = 60;

      for (let ai = 0; ai < NUM_ASTEROIDS; ai++) {
        const rand = srand(ai * 7919 + 1337);

        // Belt occupies the space between orbits 6 and 7 (roughly 12.0–13.0 units)
        const beltR = 12.0 + rand() * 1.0;
        const angle = rand() * Math.PI * 2;
        const yOff  = (rand() - 0.5) * 1.8;  // slight vertical spread

        const scale = 0.06 + rand() * 0.14;
        const geo = makeAsteroidGeometry(THREE, scale, ai + 1);

        // Rocky grey-brown material with subtle color tints
        const greyVal = 0.28 + rand() * 0.22;
        const warmTint = rand() * 0.08;
        const mat = new THREE.MeshPhongMaterial({
          color: new THREE.Color(greyVal + warmTint, greyVal + warmTint * 0.5, greyVal),
          emissive: new THREE.Color(0.02, 0.01, 0.03),
          specular: new THREE.Color(0.12, 0.10, 0.14),
          shininess: 4 + rand() * 8,
          flatShading: rand() > 0.4, // some have flat faces for craggy look
        });

        const mesh = new THREE.Mesh(geo, mat);
        mesh.position.set(
          Math.cos(angle) * beltR,
          yOff,
          Math.sin(angle) * beltR
        );

        // Random initial rotation
        mesh.rotation.set(rand() * Math.PI * 2, rand() * Math.PI * 2, rand() * Math.PI * 2);

        scene.add(mesh);
        asteroidBelt.push({
          mesh,
          orbitR:    beltR,
          angle,
          orbitSpeed: (0.0006 + rand() * 0.0014) * (rand() > 0.5 ? 1 : -1),
          yOff,
          spinAxis:  new THREE.Vector3(rand()-0.5, rand()-0.5, rand()-0.5).normalize(),
          spinSpeed: (rand() - 0.5) * 0.8,
        });
      }

      let last = performance.now();
      let readyCalled = false;
      function animate() {
        raf = requestAnimationFrame(animate);
        const now = performance.now();
        const dt  = Math.min((now-last)/1000, 0.05);
        last = now; t += dt;

        sunUniforms.uTime.value = t;
        sun.rotation.y += dt * 0.055;
        autoRotY += dt * 0.07;
        scene.rotation.y = autoRotY;

        // Subtle sun light flicker — solar variability
        sunLight.intensity = 5.8 + Math.sin(t*1.3)*0.3 + Math.sin(t*2.9)*0.12;

        planetObjects.forEach(({ mesh, innerPivot, cfg, idx, mat }) => {
          angles[idx] += cfg.speed;
          innerPivot.rotation.y = angles[idx];
          mesh.rotation.y += dt * 0.3;
          const isH = selectedIdx === idx;
          const hv = isH ? 1 : 0;
          // Gentle hover glow — doesn't distort the planet's natural color
          mat.emissive.setRGB(hv*0.12, hv*0.06, hv*0.18);
          const ts = 1 + hv * 0.3;
          mesh.scale.lerp({ x: ts, y: ts, z: ts }, 0.12);
        });

        // Animate asteroids
        asteroidBelt.forEach(a => {
          a.angle += a.orbitSpeed;
          a.mesh.position.set(
            Math.cos(a.angle) * a.orbitR,
            a.yOff,
            Math.sin(a.angle) * a.orbitR
          );
          a.mesh.rotateOnAxis(a.spinAxis, dt * a.spinSpeed);
        });

        orbitMeshes.forEach((o, i) => {
          o.material.opacity = 0.25 + Math.sin(t*0.5+i*0.45)*0.12;
        });

        renderer.render(scene, camera);

        // Signal page ready after first fully rendered frame
        if (!readyCalled) { readyCalled = true; onReady && onReady(); }

        // Project planet labels to 2D
        const CW = mount.clientWidth;
        const CH = mount.clientHeight;
        planetObjects.forEach(({ labelAnchor }, i) => {
          const el = labelEls[i];
          if (!el) return;
          const wp = new THREE.Vector3();
          labelAnchor.getWorldPosition(wp);
          const s = toScreen(wp, CW, CH);
          if (s.behind) {
            el.style.opacity = "0";
            el.style.pointerEvents = "none";
          } else {
            el.style.opacity = "1";
            el.style.pointerEvents = "auto";
            el.style.transform = `translate(-50%,-100%) translate(${s.x.toFixed(1)}px,${s.y.toFixed(1)}px)`;
          }
        });

        // Project Orchestrator (sun) label — sun is at scene origin
        const sunS = toScreen(new THREE.Vector3(0, 2.6, 0), CW, CH);
        sunLabelEl.style.transform = `translate(-50%,-100%) translate(${sunS.x.toFixed(1)}px,${sunS.y.toFixed(1)}px)`;
      }
      animate();

      // Track whether the mouse moved between mousedown and mouseup (to distinguish click vs drag)
      let mouseMovedSincDown = false;

      const onMouseMove = (e) => {
        // Update cursor based on whether we're over a planet
        const rect = mount.getBoundingClientRect();
        mouse.x =  ((e.clientX-rect.left)/rect.width)*2-1;
        mouse.y = -((e.clientY-rect.top)/rect.height)*2+1;
        if (!isDragging) {
          raycaster.setFromCamera(mouse, camera);
          const hits = raycaster.intersectObjects(planetObjects.map(p => p.mesh), true);
          mount.style.cursor = hits.length ? "pointer" : "grab";
        }
        mouseMovedSincDown = true;
      };
      const onClick = (e) => {
        // Only register as click if mouse barely moved (not a drag)
        if (mouseMovedSincDown && isDragging) return;
        const rect = mount.getBoundingClientRect();
        mouse.x =  ((e.clientX-rect.left)/rect.width)*2-1;
        mouse.y = -((e.clientY-rect.top)/rect.height)*2+1;
        raycaster.setFromCamera(mouse, camera);
        const hits = raycaster.intersectObjects(planetObjects.map(p => p.mesh), true);
        if (hits.length) {
          const found = planetObjects.find(p => p.mesh===hits[0].object);
          if (found) {
            // Toggle off if already selected
            if (selectedIdx === found.idx) { selectedIdx=-1; setSelected(null); }
            else { selectedIdx=found.idx; setSelected(AGENTS_DATA[found.idx]); }
            return;
          }
        }
        // Clicked empty space — deselect
        selectedIdx=-1; setSelected(null);
      };
      const onMouseDown = (e) => { isDragging=true; mouseMovedSincDown=false; prevMouse={x:e.clientX,y:e.clientY}; mount.style.cursor="grabbing"; };
      const onMouseUp   = ()    => { isDragging=false; mount.style.cursor="grab"; };
      const onDrag      = (e)   => {
        if (!isDragging) return;
        autoRotY += (e.clientX-prevMouse.x)*0.004;
        camPhi = Math.max(0.25, Math.min(Math.PI-0.25, camPhi-(e.clientY-prevMouse.y)*0.004));
        prevMouse={x:e.clientX,y:e.clientY};
        setCamPos();
      };
      let lastTouch=null;
      const onTouchStart = (e) => { lastTouch=e.touches[0]; };
      const onTouchMove  = (e) => { if(!lastTouch)return; autoRotY+=(e.touches[0].clientX-lastTouch.clientX)*0.004; lastTouch=e.touches[0]; };
      const onResize = () => {
        const W2=mount.clientWidth, H2=mount.clientHeight;
        camera.aspect=W2/H2; camera.updateProjectionMatrix(); renderer.setSize(W2,H2);
      };
      mount.addEventListener("mousemove", onMouseMove);
      mount.addEventListener("mousedown", onMouseDown);
      mount.addEventListener("click",     onClick);
      mount.addEventListener("touchstart",onTouchStart,{passive:true});
      mount.addEventListener("touchmove", onTouchMove, {passive:true});
      window.addEventListener("mouseup",  onMouseUp);
      window.addEventListener("mousemove",onDrag);
      window.addEventListener("resize",   onResize);

      mount._cleanup = () => {
        cancelAnimationFrame(raf); renderer.dispose();
        if (renderer.domElement.parentNode===mount) mount.removeChild(renderer.domElement);
        labelEls.forEach(el => { if (el.parentNode) el.parentNode.removeChild(el); });
        if (sunLabelEl && sunLabelEl.parentNode) sunLabelEl.parentNode.removeChild(sunLabelEl);
        mount.removeEventListener("mousemove", onMouseMove);
        mount.removeEventListener("mousedown", onMouseDown);
        mount.removeEventListener("click",     onClick);
        mount.removeEventListener("touchstart",onTouchStart);
        mount.removeEventListener("touchmove", onTouchMove);
        window.removeEventListener("mouseup",  onMouseUp);
        window.removeEventListener("mousemove",onDrag);
        window.removeEventListener("resize",   onResize);
      };
    }

    const THREE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r134/three.min.js";

    const handleWebGLError = (err) => {
      console.warn("[SolarSystem] WebGL unavailable, using CSS fallback:", err?.message || err);
      if (mount) mount.classList.add("pl-solar-fallback");
      onReady && onReady();
    };

    if (window.THREE) {
      try { init(); } catch (err) { handleWebGLError(err); }
    } else {
      const existing = document.querySelector(`script[src="${THREE_CDN}"]`);
      if (existing) {
        existing.addEventListener("load", () => { try { init(); } catch (err) { handleWebGLError(err); } }, { once: true });
        return () => { if (mount._cleanup) mount._cleanup(); };
      }
      const script = document.createElement("script");
      script.src = THREE_CDN;
      script.onload = () => { try { init(); } catch (err) { handleWebGLError(err); } };
      script.onerror = () => { console.warn("[SolarSystem] Failed to load three.min.js, using CSS fallback"); if (mount) mount.classList.add("pl-solar-fallback"); onReady && onReady(); };
      document.head.appendChild(script);
      return () => { if (mount._cleanup) mount._cleanup(); if (script.parentNode) script.parentNode.removeChild(script); };
    }
    return () => { if (mount._cleanup) mount._cleanup(); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="pl-solar-wrap" style={{ background: "transparent" }}>
      <div ref={mountRef} className="pl-solar-canvas" style={{ background: "transparent" }} />
      <div ref={labelsRef} className="pl-label-layer" />
      {selected && (
        <div className="pl-planet-tooltip" style={{ borderColor: selected.color + "66" }}>
          <div className="pl-pt-icon-row">
            <Icon name={selected.icon} size={14} />
            <span className="pl-pt-name" style={{ color: selected.color }}>{selected.name}</span>
            <span className="pl-pt-role">{selected.role}</span>
          </div>
          <p className="pl-pt-desc">{selected.details}</p>
          <div className="pl-pt-model">{selected.model}</div>
        </div>
      )}
      <p className="pl-solar-hint">Drag to rotate · click planets</p>
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

/* ══ REVEAL HOOK ══ */
function useReveal(threshold = 0.1) {
  const ref = useRef(null);
  const [vis, setVis] = useState(false);
  useEffect(() => {
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setVis(true); }, { threshold });
    if (ref.current) obs.observe(ref.current);
    return () => obs.disconnect();
  }, [threshold]);
  return [ref, vis];
}

/* PIPELINE */
function PipelineFlow() {
  const [ref, vis] = useReveal(0.05);
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);
  const [manualStep, setManualStep] = useState(null);
  const currentStep = manualStep !== null ? manualStep : active;

  useEffect(() => {
    if (!vis || paused) return;
    const id = setInterval(() => setActive(a => (a + 1) % PIPELINE.length), 3000);
    return () => clearInterval(id);
  }, [vis, paused]);

  const step = PIPELINE[currentStep];
  return (
    <div ref={ref} className="pl-pipeline-outer">
      <div className="pl-pipeline-track">
        {PIPELINE.map((s, i) => {
          const isDone = i < currentStep, isActive = i === currentStep;
          return (
            <button key={i}
              className={`pl-pipe-node ${vis?"is-vis":""} ${isActive?"is-active":""} ${isDone?"is-done":""}`}
              style={{"--d":`${i*0.07}s`,"--ac":s.color}}
              onClick={() => { setPaused(true); setManualStep(i); }}>
              <div className="pl-pipe-node-dot"><Icon name={s.icon} size={20}/></div>
              <div className="pl-pipe-node-connector">
                <div className={`pl-pipe-node-line ${isDone||isActive?"is-lit":""}`}/>
              </div>
              <span className="pl-pipe-node-label">{s.label}</span>
              <span className="pl-pipe-node-sub">{s.sub}</span>
            </button>
          );
        })}
      </div>
      <div className={`pl-pipe-detail ${vis?"is-vis":""}`} key={currentStep}>
        <div className="pl-pipe-detail-icon" style={{color:step.color}}><Icon name={step.icon} size={38}/></div>
        <div className="pl-pipe-detail-content">
          <div className="pl-pipe-detail-step" style={{color:step.color}}>Step {currentStep+1} of {PIPELINE.length}</div>
          <h3 className="pl-pipe-detail-name">{step.label}</h3>
          <p className="pl-pipe-detail-sub">{step.sub}</p>
        </div>
        <div className="pl-pipe-detail-progress">
          <div className="pl-pipe-detail-bar">
            <div className="pl-pipe-detail-fill" style={{width:`${((currentStep+1)/PIPELINE.length)*100}%`,background:`linear-gradient(90deg,#7c3aed,${step.color})`}}/>
          </div>
          <span className="pl-pipe-detail-pct">{Math.round(((currentStep+1)/PIPELINE.length)*100)}% complete</span>
        </div>
        {paused && <button className="pl-pipe-resume-btn" onClick={() => { setPaused(false); setManualStep(null); setActive(0); }}>▶ Resume Auto</button>}
      </div>
      <div className="pl-pipe-dots">
        {PIPELINE.map((s, i) => (
          <button key={i}
            className={`pl-pipe-dot ${i===currentStep?"active":""} ${i<currentStep?"done":""}`}
            style={{"--ac":s.color}} onClick={() => { setPaused(true); setManualStep(i); }}/>
        ))}
      </div>
      {!paused && <button className="pl-pipe-pause-btn" onClick={() => setPaused(true)}>⏸ Pause</button>}
    </div>
  );
}

/* MAIN */
export default function PublicLanding() {
  const navigate = useNavigate();
  const [scrollY, setScrollY] = useState(0);
  const [ready, setReady] = useState(false);
  const readyRef = useRef(false);
  const splashDoneRef = useRef(false);

  // Minimum hold: 2.8s so text animations finish before fade-out.
  // Hard fallback at 6s in case WebGL/Three.js never fires onReady.
  useEffect(() => {
    const t = setTimeout(() => {
      splashDoneRef.current = true;
      if (readyRef.current) setReady(true);
    }, 2800);
    const fallback = setTimeout(() => {
      readyRef.current = true;
      splashDoneRef.current = true;
      setReady(true);
    }, 6000);
    return () => { clearTimeout(t); clearTimeout(fallback); };
  }, []);

  const handleReady = () => {
    readyRef.current = true;
    if (splashDoneRef.current) setReady(true);
  };

  useEffect(() => {
    const fn = () => setScrollY(window.scrollY);
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  return (
    <>
      {/* WELCOME SPLASH 
          Sequence: black → text fades in (0.9s) → holds → fades out with page (0.8s)
          The landing beneath fades in simultaneously as splash fades out.
       */}
      <div style={{
        position: "fixed", inset: 0, zIndex: 9999,
        background: "#06010f",
        display: "flex", flexDirection: "column",
        alignItems: "center", justifyContent: "center",
        opacity: ready ? 0 : 1,
        pointerEvents: ready ? "none" : "auto",
        transition: ready ? "opacity 1.1s cubic-bezier(0.4,0,0.2,1)" : "none",
      }}>

        {/* Ambient nebula glow behind text */}
        <div style={{
          position: "absolute", width: 600, height: 600,
          borderRadius: "50%",
          background: "radial-gradient(circle, rgba(124,58,237,0.18) 0%, rgba(168,85,247,0.07) 45%, transparent 70%)",
          filter: "blur(40px)",
          animation: "wcx-breathe 4s ease-in-out infinite",
        }}/>

        {/* Logo mark — sun + orbit */}
        <div style={{
          position: "relative", width: 64, height: 64, marginBottom: 36,
          animation: "wcx-fadein 1s ease 0.1s both",
        }}>
          <div style={{
            position: "absolute", inset: 0, borderRadius: "50%",
            border: "1.5px solid rgba(168,85,247,0.40)",
          }}/>
          <div style={{
            position: "absolute", inset: 6, borderRadius: "50%",
            border: "1px solid rgba(168,85,247,0.20)",
          }}/>
          {/* Sun */}
          <div style={{
            position: "absolute", top: "50%", left: "50%",
            transform: "translate(-50%,-50%)",
            width: 18, height: 18, borderRadius: "50%",
            background: "radial-gradient(circle, #fff8e1 0%, #ffb300 55%, #e65100 100%)",
            boxShadow: "0 0 22px 8px rgba(255,140,0,0.55), 0 0 8px 2px rgba(255,200,50,0.8)",
          }}/>
          {/* Orbiting planet */}
          <div style={{
            position: "absolute", top: 0, left: "50%",
            marginLeft: -5, marginTop: -5,
            width: 10, height: 10, borderRadius: "50%",
            background: "radial-gradient(circle, #c084fc, #7c3aed)",
            boxShadow: "0 0 10px 3px rgba(168,85,247,0.7)",
            animation: "wcx-orbit 3s linear infinite",
            transformOrigin: "5px 37px",
          }}/>
        </div>

        {/* Welcome text */}
        <div style={{
          textAlign: "center",
          animation: "wcx-fadein 1s ease 0.3s both",
        }}>
          <div style={{
            fontSize: "clamp(11px, 1.4vw, 13px)",
            fontWeight: 600,
            letterSpacing: "0.30em",
            textTransform: "uppercase",
            color: "rgba(167,139,250,0.75)",
            marginBottom: 16,
          }}>Welcome to</div>

          <div style={{
            fontSize: "clamp(36px, 6vw, 72px)",
            fontWeight: 800,
            letterSpacing: "-0.02em",
            lineHeight: 1,
            background: "linear-gradient(135deg, #ffffff 0%, #e9d5ff 40%, #a855f7 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
            marginBottom: 20,
          }}>InnovaCX</div>

          <div style={{
            fontSize: "clamp(13px, 1.6vw, 17px)",
            color: "rgba(196,165,255,0.70)",
            letterSpacing: "0.04em",
            fontWeight: 400,
            maxWidth: 380,
            lineHeight: 1.6,
            animation: "wcx-fadein 1s ease 0.6s both",
          }}>
            AI-powered complaint intelligence.<br/>Every case resolved, every customer retained.
          </div>
        </div>

        {/* Subtle bottom line */}
        <div style={{
          position: "absolute", bottom: 36,
          fontSize: 11, letterSpacing: "0.12em",
          color: "rgba(167,139,250,0.30)",
          animation: "wcx-fadein 1s ease 0.9s both",
        }}>InnovaAI X DUBAI COMMERCITY · 2026</div>

        <style>{`
          @keyframes wcx-fadein {
            from { opacity: 0; transform: translateY(12px); }
            to   { opacity: 1; transform: translateY(0); }
          }
          @keyframes wcx-orbit {
            from { transform: rotate(0deg); }
            to   { transform: rotate(360deg); }
          }
          @keyframes wcx-breathe {
            0%,100% { transform: scale(1);    opacity: 0.7; }
            50%      { transform: scale(1.15); opacity: 1;   }
          }
        `}</style>
      </div>

      <div className="pl-root" style={{
        opacity: ready ? 1 : 0,
        transition: ready ? "opacity 1.0s cubic-bezier(0.4,0,0.2,1) 0.3s" : "none",
      }}>

      {/* HERO */}
      <section className="pl-hero">
        <Starfield />
        <div className="pl-neb pl-neb1" style={{transform:`translateY(${scrollY*0.12}px)`}}/>
        <div className="pl-neb pl-neb2" style={{transform:`translateY(${scrollY*0.07}px)`}}/>
        <div className="pl-neb pl-neb3" style={{transform:`translateY(${scrollY*0.18}px)`}}/>
        <nav className="pl-nav">
          <img src={novaLogo} alt="InnovaCX" className="pl-logo"/>
          <button className="pl-login-btn" onClick={() => navigate("/login")}>Log In →</button>
        </nav>
        <div className="pl-hero-body">
          <div className="pl-hero-left">
            <p className="pl-eyebrow">InnovaAI · Dubai CommerCity</p>
            <h1 className="pl-headline">
              <span className="pl-hl1">Every Complaint</span>
              <span className="pl-hl2">Handled by</span>
              <span className="pl-hl3"><Typewriter words={["AI Agents.","InnovaCX.","Nova."]}/></span>
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
              <span className="pl-nova-dot"/>
              Chat with Nova AI
              <span className="pl-nova-arrow">Try Now →</span>
            </button>
          </div>
          <div className="pl-hero-right"><SolarSystem onReady={handleReady} /></div>
        </div>
      </section>

      {/* MARQUEE */}
      <div className="pl-marquee">
        <div className="pl-marquee-track">
          {[...Array(4)].map((_,r) =>
            ["Chatbot by Qwen","Transcriber by FasterWhisper","Orchestrator by LangChain",
              "Recurrence by Transformer","Subject Generation by Qwen","Suggested Resolution by Qwen",
              "Classification by DeBERTa","Sentiment Analysis by RoBERTa","Audio Analysis by Librosa",
              "Feature Engineering by DeBERTa","Prioritization Engine by XGBoost",
              "Department Routing by Qwen","Review by Qwen"].map((x,i)=>(
              <span key={`${r}-${i}`} className="pl-marquee-item">✦ {x}</span>
            ))
          )}
        </div>
      </div>

      {/* PIPELINE */}
      <section className="pl-pipeline-section">
        <div className="pl-section-tag">How It Works</div>
        <h2 className="pl-section-h light">The Agent Pipeline</h2>
        <p className="pl-section-p light">Click any step to explore it. Watch the data flow in real-time.</p>
        <PipelineFlow />
      </section>

      {/* CTA */}
      <section className="pl-cta">
        <Starfield />
        <div className="pl-cta-neb"/>
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

      {/* FOOTER */}
      <footer className="pl-footer">
        <img src={novaLogo} alt="InnovaCX" className="pl-footer-logo"/>
        <div className="pl-footer-socials" style={{display:"none"}}>
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
        <p className="pl-footer-copy">© 2026 InnovaAI · All rights reserved. &nbsp;·&nbsp; Sponsored By Dubai CommerCity</p>
      </footer>
    </div>

    <div className="pl-social-dock" aria-label="Follow us on social media">
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
    </>
  );
}
