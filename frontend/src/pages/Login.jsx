import { useState, useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import logo from "../assets/nova-logo.png";
import { apiUrl } from "../config/apiBase";
import { isStaffHost } from "../utils/hostUtils";
import "./Login.css";

/* ── Validation helpers ── */
const validators = {
  email: (val) => {
    if (!val) return "Email is required.";
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
    if (!re.test(val)) return "Enter a valid email address.";
    if (val.length > 254) return "Email address is too long.";
    return null;
  },
  password: (val) => {
    if (!val) return "Please enter your password.";
    return null;
  },
};

/* ── Starfield ── */
function Starfield() {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    let raf;
    const resize = () => {
      c.width = window.innerWidth;
      c.height = window.innerHeight;
    };
    resize();
    const stars = Array.from({ length: 260 }, () => ({
      x: Math.random(),
      y: Math.random(),
      r: Math.random() * 1.4 + 0.2,
      twinkle: Math.random() * Math.PI * 2,
      speed: Math.random() * 0.016 + 0.004,
      color:
        Math.random() > 0.8
          ? "#c4b5fd"
          : Math.random() > 0.6
          ? "#e9d5ff"
          : "#fff",
    }));
    const shooters = Array.from({ length: 4 }, () => ({
      x: Math.random() * 0.5,
      y: Math.random() * 0.4,
      len: Math.random() * 140 + 80,
      speed: Math.random() * 5 + 3,
      angle: Math.PI / 5.5,
      active: false,
      timer: Math.random() * 300 + 80,
      alpha: 0,
    }));
    const draw = () => {
      ctx.clearRect(0, 0, c.width, c.height);
      stars.forEach((s) => {
        s.twinkle += s.speed;
        ctx.globalAlpha = Math.max(0.05, 0.28 + Math.sin(s.twinkle) * 0.5);
        ctx.fillStyle = s.color;
        ctx.beginPath();
        ctx.arc(s.x * c.width, s.y * c.height, s.r, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.globalAlpha = 1;
      shooters.forEach((s) => {
        s.timer--;
        if (s.timer <= 0 && !s.active) {
          s.active = true;
          s.alpha = 1;
        }
        if (s.active) {
          s.x += (Math.cos(s.angle) * s.speed) / c.width;
          s.y += (Math.sin(s.angle) * s.speed) / c.height;
          s.alpha -= 0.018;
          if (s.alpha <= 0 || s.x > 1) {
            s.active = false;
            s.x = Math.random() * 0.45;
            s.y = Math.random() * 0.35;
            s.timer = Math.random() * 400 + 150;
          }
          ctx.save();
          ctx.globalAlpha = s.alpha;
          const g = ctx.createLinearGradient(
            s.x * c.width,
            s.y * c.height,
            (s.x - (Math.cos(s.angle) * s.len) / c.width) * c.width,
            (s.y - (Math.sin(s.angle) * s.len) / c.height) * c.height
          );
          g.addColorStop(0, "#e9d5ff");
          g.addColorStop(1, "transparent");
          ctx.beginPath();
          ctx.moveTo(s.x * c.width, s.y * c.height);
          ctx.lineTo(
            (s.x - (Math.cos(s.angle) * s.len) / c.width) * c.width,
            (s.y - (Math.sin(s.angle) * s.len) / c.height) * c.height
          );
          ctx.strokeStyle = g;
          ctx.lineWidth = 1.8;
          ctx.stroke();
          ctx.restore();
        }
      });
      raf = requestAnimationFrame(draw);
    };
    draw();
    window.addEventListener("resize", resize);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
    };
  }, []);
  return <canvas ref={ref} className="login-starfield" />;
}

/* ── Staff Background — floating orbs + aurora ribbons ── */
function StaffBackground() {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    let raf, t = 0;

    const resize = () => { c.width = window.innerWidth; c.height = window.innerHeight; };
    resize();
    window.addEventListener("resize", resize);

    const orbs = [
      { x: 0.15, y: 0.20, r: 0.18, ax: 0.00004, ay: 0.00003, phase: 0.0, color: [180, 150, 230] },
      { x: 0.80, y: 0.15, r: 0.13, ax: 0.00003, ay: 0.00005, phase: 1.2, color: [200, 170, 255] },
      { x: 0.65, y: 0.75, r: 0.16, ax: 0.00004, ay: 0.00002, phase: 2.5, color: [170, 140, 220] },
      { x: 0.25, y: 0.80, r: 0.11, ax: 0.00005, ay: 0.00004, phase: 3.8, color: [210, 190, 255] },
      { x: 0.50, y: 0.45, r: 0.09, ax: 0.00003, ay: 0.00004, phase: 0.7, color: [190, 160, 240] },
      { x: 0.90, y: 0.60, r: 0.12, ax: 0.00002, ay: 0.00004, phase: 4.2, color: [220, 200, 255] },
    ];

    const ribbons = [
      { baseY: 0.28, amp: 0.04, freq: 0.0018, speed: 0.00008, phase: 0.0, color: [180,150,220], alpha: 0.06, thickness: 0.12 },
      { baseY: 0.55, amp: 0.03, freq: 0.0022, speed: 0.00006, phase: 2.1, color: [200,170,255], alpha: 0.04, thickness: 0.09 },
      { baseY: 0.72, amp: 0.05, freq: 0.0015, speed: 0.00010, phase: 4.3, color: [170,140,220], alpha: 0.05, thickness: 0.10 },
    ];

    const particles = Array.from({ length: 55 }, () => ({
      x: Math.random(), y: Math.random(),
      r: Math.random() * 1.8 + 0.5,
      speed: Math.random() * 0.000015 + 0.000005,
      drift: Math.random() * 0.000008 - 0.000004,
      phase: Math.random() * Math.PI * 2,
      twinkleSpeed: Math.random() * 0.008 + 0.003,
      color: Math.random() > 0.5 ? [210,190,255] : [230,215,255],
    }));

    const nodes = Array.from({ length: 22 }, () => ({
      x: Math.random(), y: Math.random(),
      vx: (Math.random() - 0.5) * 0.00002,
      vy: (Math.random() - 0.5) * 0.00002,
    }));

    const drawOrb = (orb) => {
      const cx = orb.x * c.width;
      const cy = orb.y * c.height;
      const rx = orb.r * Math.min(c.width, c.height);
      const [r, g, b] = orb.color;
      const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, rx * 1.6);
      glow.addColorStop(0,   `rgba(${r},${g},${b},0.13)`);
      glow.addColorStop(0.5, `rgba(${r},${g},${b},0.05)`);
      glow.addColorStop(1,   `rgba(${r},${g},${b},0)`);
      ctx.beginPath(); ctx.arc(cx, cy, rx * 1.6, 0, Math.PI * 2);
      ctx.fillStyle = glow; ctx.fill();
      const core = ctx.createRadialGradient(cx - rx * 0.25, cy - rx * 0.25, 0, cx, cy, rx);
      core.addColorStop(0,    `rgba(255,255,255,0.22)`);
      core.addColorStop(0.35, `rgba(${r},${g},${b},0.18)`);
      core.addColorStop(0.75, `rgba(${r},${g},${b},0.08)`);
      core.addColorStop(1,    `rgba(${r},${g},${b},0.02)`);
      ctx.beginPath(); ctx.arc(cx, cy, rx, 0, Math.PI * 2);
      ctx.fillStyle = core; ctx.fill();
      const spec = ctx.createRadialGradient(cx - rx * 0.3, cy - rx * 0.3, 0, cx - rx * 0.3, cy - rx * 0.3, rx * 0.45);
      spec.addColorStop(0, `rgba(255,255,255,0.35)`);
      spec.addColorStop(1, `rgba(255,255,255,0)`);
      ctx.beginPath(); ctx.arc(cx, cy, rx, 0, Math.PI * 2);
      ctx.fillStyle = spec; ctx.fill();
    };

    const drawRibbon = (rib) => {
      const W = c.width, H = c.height;
      const [r, g, b] = rib.color;
      const thick = rib.thickness * H;
      ctx.save(); ctx.beginPath();
      for (let px = 0; px <= W; px += 6) {
        const nx = px / W;
        const wave = Math.sin(nx * Math.PI * 2 * rib.freq * W + rib.phase + t * rib.speed * 1000);
        const py = (rib.baseY + wave * rib.amp) * H - thick / 2;
        px === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
      }
      for (let px = W; px >= 0; px -= 6) {
        const nx = px / W;
        const wave = Math.sin(nx * Math.PI * 2 * rib.freq * W + rib.phase + t * rib.speed * 1000);
        const py = (rib.baseY + wave * rib.amp) * H + thick / 2;
        ctx.lineTo(px, py);
      }
      ctx.closePath();
      const midY = rib.baseY * H;
      const grad = ctx.createLinearGradient(0, midY - thick / 2, 0, midY + thick / 2);
      grad.addColorStop(0,    `rgba(${r},${g},${b},0)`);
      grad.addColorStop(0.35, `rgba(${r},${g},${b},${rib.alpha})`);
      grad.addColorStop(0.5,  `rgba(${r},${g},${b},${rib.alpha * 1.6})`);
      grad.addColorStop(0.65, `rgba(${r},${g},${b},${rib.alpha})`);
      grad.addColorStop(1,    `rgba(${r},${g},${b},0)`);
      ctx.fillStyle = grad; ctx.fill(); ctx.restore();
    };

    const drawNodes = () => {
      const W = c.width, H = c.height;
      nodes.forEach((n) => {
        n.x += n.vx; n.y += n.vy;
        if (n.x < 0 || n.x > 1) n.vx *= -1;
        if (n.y < 0 || n.y > 1) n.vy *= -1;
      });
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = (nodes[i].x - nodes[j].x) * W;
          const dy = (nodes[i].y - nodes[j].y) * H;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < 180) {
            ctx.beginPath();
            ctx.moveTo(nodes[i].x * W, nodes[i].y * H);
            ctx.lineTo(nodes[j].x * W, nodes[j].y * H);
            ctx.strokeStyle = `rgba(120,60,220,${(1 - dist / 180) * 0.07})`;
            ctx.lineWidth = 0.8; ctx.stroke();
          }
        }
      }
      nodes.forEach((n) => {
        ctx.beginPath(); ctx.arc(n.x * W, n.y * H, 1.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(160,100,255,0.15)`; ctx.fill();
      });
    };

    const draw = () => {
      t++;
      ctx.clearRect(0, 0, c.width, c.height);
      drawNodes();
      ribbons.forEach((rib) => { rib.phase += rib.speed; drawRibbon(rib); });
      orbs.forEach((orb) => {
        const drift  = Math.sin(t * orb.ax * 1000 + orb.phase) * 0.04;
        const driftY = Math.cos(t * orb.ay * 1000 + orb.phase * 1.3) * 0.035;
        drawOrb({ ...orb, x: orb.x + drift, y: orb.y + driftY });
      });
      particles.forEach((p) => {
        p.y -= p.speed; p.x += p.drift; p.phase += p.twinkleSpeed;
        if (p.y < -0.02) { p.y = 1.02; p.x = Math.random(); }
        if (p.x < 0 || p.x > 1) p.drift *= -1;
        const alpha = Math.max(0.04, 0.12 + Math.sin(p.phase) * 0.1);
        const [r, g, b] = p.color;
        ctx.beginPath(); ctx.arc(p.x * c.width, p.y * c.height, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(${r},${g},${b},${alpha})`; ctx.fill();
      });
      raf = requestAnimationFrame(draw);
    };
    draw();

    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); };
  }, []);
  return <canvas ref={ref} className="login-starfield staff-canvas" />;
}

/* ── Mouse-tracking glow on the card ── */
function useCardGlow() {
  const cardRef = useRef(null);
  const handleMouseMove = (e) => {
    const card = cardRef.current;
    if (!card) return;
    const rect = card.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    card.style.setProperty("--gx", `${x}%`);
    card.style.setProperty("--gy", `${y}%`);
  };
  const handleMouseLeave = () => {
    const card = cardRef.current;
    if (!card) return;
    card.style.setProperty("--gx", "50%");
    card.style.setProperty("--gy", "50%");
  };
  return { cardRef, handleMouseMove, handleMouseLeave };
}

/* ── Inline field message ── */
function FieldMessage({ error, success, touched }) {
  if (!touched) return <div className="field-msg-placeholder" />;
  if (error)
    return (
      <p className="field-msg field-msg--error" role="alert">
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="12" y1="8" x2="12" y2="12" />
          <line x1="12" y1="16" x2="12.01" y2="16" />
        </svg>
        {error}
      </p>
    );
  if (success)
    return (
      <p className="field-msg field-msg--success">
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          aria-hidden="true"
        >
          <polyline points="20 6 9 17 4 12" />
        </svg>
        {success}
      </p>
    );
  return <div className="field-msg-placeholder" />;
}

export default function Login() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [capsLock, setCapsLock] = useState(false);
  const [focusedField, setFocusedField] = useState(null);
  const [loginError, setLoginError] = useState("");
  const [loading, setLoading] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(
    searchParams.get("sessionExpired") === "1"
  );

  const [touched, setTouched] = useState({ email: false, password: false });

  const emailError = validators.email(email);
  const passwordError = validators.password(password);

  const { cardRef, handleMouseMove, handleMouseLeave } = useCardGlow();

  const markTouched = (field) =>
    setTouched((prev) => ({ ...prev, [field]: true }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setTouched({ email: true, password: true });
    if (emailError || passwordError) return;

    setLoginError("");
    setLoading(true);

    try {
      const res = await fetch(apiUrl("/api/auth/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        if (res.status === 401) {
          setLoginError("Invalid credentials. Please try again.");
        } else {
          setLoginError(
            err.detail || "Unable to log in right now. Please try again."
          );
        }
        return;
      }

      const data = await res.json();

      sessionStorage.removeItem("mfa_token");
      sessionStorage.removeItem("mfa_user");

      const role = data.user?.role;

      // ── Domain enforcement ──
      // null  = localhost / dev → skip enforcement
      // true  = staff.domain.com → staff roles only
      // false = domain.com → customer only
      const staffHost = isStaffHost();
      if (staffHost !== null) {
        const isCustomer = role === "customer";
        if (staffHost && isCustomer) {
          setLoginError("Customer accounts must log in at domain.com.");
          setLoading(false);
          return;
        }
        if (!staffHost && !isCustomer) {
          setLoginError("Staff accounts must log in at staff.domain.com.");
          setLoading(false);
          return;
        }
      }

      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem(
        "user",
        JSON.stringify({
          id: data.user?.id,
          email: data.user?.email,
          role: data.user?.role,
          full_name: data.user?.full_name,
          token_type: data.token_type,
        })
      );

      const rawNext = searchParams.get("next");
      const nextPath =
        rawNext && decodeURIComponent(rawNext).startsWith("/")
          ? decodeURIComponent(rawNext)
          : null;
      navigate(
        nextPath ?? (role === "customer" ? "/customer/dashboard" : `/${role}`),
        { replace: true }
      );
    } catch {
      setLoginError(
        "Cannot reach the server. Make sure the backend is running."
      );
    } finally {
      setLoading(false);
    }
  };

  const emailInputState = touched.email && emailError ? "error" : "";
  const passwordInputState = touched.password && passwordError ? "error" : "";

  const bgClass = isStaffHost() ? "loginBg loginBg--staff" : "loginBg loginBg--customer";

  return (
    <div className={bgClass}>
      {isStaffHost() ? <StaffBackground /> : <Starfield />}
      {!isStaffHost() && <div className="login-neb login-neb1" />}
      {!isStaffHost() && <div className="login-neb login-neb2" />}
      {!isStaffHost() && <div className="login-neb login-neb3" />}

      <div
        className="loginWrapper"
        ref={cardRef}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      >
        {/* ── Left panel ── */}
        <section className="loginLeft">
          <div className="loginOverlay" />
          <div className="loginLeftContent">
            <h1 className="welcomeTitle">Welcome back.</h1>
            <p className="welcomeSub">Sign in to access your dashboard.</p>
            <div className="markWrap">
              <img src={logo} alt="InnovaCX" className="novaLogo" />
            </div>
          </div>
        </section>

        {/* ── Right panel ── */}
        <section className="loginRight">
          <button
            className="backBtn"
            onClick={() => navigate(-1)}
          >
            ← Back
          </button>

          <div className="loginHeader">
            <div className="login-header-tag">InnovaCX · Dubai CommerCity</div>
            <h2 className="loginTitle">Log In</h2>
          </div>

          {sessionExpired && (
            <div className="login-session-banner" role="alert">
              <div className="login-session-banner__icon" aria-hidden="true">
                <svg
                  width="16"
                  height="16"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
              </div>
              <div className="login-session-banner__body">
                <span className="login-session-banner__title">
                  Session Expired
                </span>
                <span className="login-session-banner__text">
                  For your security, please sign in again.
                </span>
              </div>
              <button
                type="button"
                className="login-session-banner__close"
                aria-label="Dismiss"
                onClick={() => setSessionExpired(false)}
              >
                <svg
                  width="12"
                  height="12"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  aria-hidden="true"
                >
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>
          )}

          <form className="loginForm" onSubmit={handleSubmit} noValidate>
            {/* Email field */}
            <div className={`field field--${emailInputState || "idle"}`}>
              <label className="label" htmlFor="login-email">
                Email
              </label>
              <div className="input-wrap">
                <input
                  id="login-email"
                  className="input"
                  type="email"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (loginError) setLoginError("");
                  }}
                  onBlur={() => { markTouched("email"); setFocusedField(null); }}
                  onFocus={(e) => { setFocusedField("email"); setCapsLock(e.getModifierState("CapsLock")); }}
                  onKeyDown={(e) => setCapsLock(e.getModifierState("CapsLock"))}
                  onKeyUp={(e) => setCapsLock(e.getModifierState("CapsLock"))}
                  autoComplete="email"
                  aria-invalid={touched.email && !!emailError}
                  aria-describedby="email-msg"
                />
                <span className="input-icon" aria-hidden="true">
                  {capsLock && focusedField === "email" && emailInputState !== "error" && (
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.5)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><polyline points="7 11 12 6 17 11"/><line x1="12" y1="6" x2="12" y2="18"/><rect x="5" y="18" width="14" height="3" rx="1"/></svg>
                  )}
                  {emailInputState === "error" && (
                    <svg
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="#f87171"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="8" x2="12" y2="12" />
                      <line x1="12" y1="16" x2="12.01" y2="16" />
                    </svg>
                  )}
                </span>
              </div>
              <div id="email-msg">
                <FieldMessage error={emailError} touched={touched.email} />
              </div>
            </div>

            {/* Password field */}
            <div className={`field field--${passwordInputState || "idle"}`}>
              <label className="label" htmlFor="login-password">
                Password
              </label>
              <div className="input-wrap passwordField">
                <input
                  id="login-password"
                  className={`input passwordInput${capsLock ? " has-capslock" : ""}`}
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (loginError) setLoginError("");
                  }}
                  onBlur={() => { markTouched("password"); setFocusedField(null); setCapsLock(false); }}
                  onFocus={(e) => { setFocusedField("password"); setCapsLock(e.getModifierState("CapsLock")); }}
                  onKeyDown={(e) => setCapsLock(e.getModifierState("CapsLock"))}
                  onKeyUp={(e) => setCapsLock(e.getModifierState("CapsLock"))}
                  autoComplete="current-password"
                  aria-invalid={touched.password && !!passwordError}
                  aria-describedby="password-msg"
                />
                {capsLock && focusedField === "password" && (
                  <span className="login-capslock-icon">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="rgba(255,255,255,0.5)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><polyline points="7 11 12 6 17 11"/><line x1="12" y1="6" x2="12" y2="18"/><rect x="5" y="18" width="14" height="3" rx="1"/></svg>
                  </span>
                )}
                <button
                  type="button"
                  className="passwordToggleBtn"
                  onClick={() => setShowPassword((p) => !p)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? (
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path
                        d="M3 3l18 18M10.58 10.59A2 2 0 0012 14a2 2 0 001.41-.58M9.88 5.09A9.77 9.77 0 0112 5c5 0 9 7 9 7a17.59 17.59 0 01-3.24 3.93M6.1 6.1A17.3 17.3 0 003 12s4 7 9 7a9.8 9.8 0 004.25-.95"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  ) : (
                    <svg viewBox="0 0 24 24" aria-hidden="true">
                      <path
                        d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                      <circle
                        cx="12"
                        cy="12"
                        r="3"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="2"
                      />
                    </svg>
                  )}
                </button>
              </div>
              <div id="password-msg">
                <FieldMessage
                  error={passwordError}
                  touched={touched.password}
                />
              </div>
            </div>

            {/* Server-side error */}
            {loginError && (
              <div className="loginError" role="alert">
                <svg
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  aria-hidden="true"
                >
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                {loginError}
              </div>
            )}

            <button
              type="button"
              className="forgotLink"
              onClick={() => navigate("/forgot-password")}
            >
              Forgot password?
            </button>

            <button type="submit" className="loginBtn" disabled={loading}>
              {loading ? "Signing in…" : "Sign In →"}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}