import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import "./ForgotPassword.css";

const API_BASE = "http://localhost:8000/api";

/* ── Starfield (same engine as Login) ── */
function Starfield() {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current; if (!c) return;
    const ctx = c.getContext("2d");
    let raf;
    const resize = () => { c.width = window.innerWidth; c.height = window.innerHeight; };
    resize();
    const stars = Array.from({ length: 240 }, () => ({
      x: Math.random(), y: Math.random(),
      r: Math.random() * 1.4 + 0.2,
      twinkle: Math.random() * Math.PI * 2,
      speed: Math.random() * 0.016 + 0.004,
      color: Math.random() > 0.8 ? "#c4b5fd" : Math.random() > 0.6 ? "#e9d5ff" : "#fff",
    }));
    const shooters = Array.from({ length: 3 }, () => ({
      x: Math.random() * 0.5, y: Math.random() * 0.4,
      len: Math.random() * 130 + 70, speed: Math.random() * 5 + 3,
      angle: Math.PI / 5.5, active: false, timer: Math.random() * 320 + 100, alpha: 0,
    }));
    const draw = () => {
      ctx.clearRect(0, 0, c.width, c.height);
      stars.forEach(s => {
        s.twinkle += s.speed;
        ctx.globalAlpha = Math.max(0.05, 0.28 + Math.sin(s.twinkle) * 0.5);
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
          s.alpha -= 0.018;
          if (s.alpha <= 0 || s.x > 1) {
            s.active = false;
            s.x = Math.random() * 0.45; s.y = Math.random() * 0.35;
            s.timer = Math.random() * 400 + 150;
          }
          ctx.save(); ctx.globalAlpha = s.alpha;
          const g = ctx.createLinearGradient(
            s.x * c.width, s.y * c.height,
            (s.x - Math.cos(s.angle) * s.len / c.width) * c.width,
            (s.y - Math.sin(s.angle) * s.len / c.height) * c.height
          );
          g.addColorStop(0, "#e9d5ff"); g.addColorStop(1, "transparent");
          ctx.beginPath();
          ctx.moveTo(s.x * c.width, s.y * c.height);
          ctx.lineTo(
            (s.x - Math.cos(s.angle) * s.len / c.width) * c.width,
            (s.y - Math.sin(s.angle) * s.len / c.height) * c.height
          );
          ctx.strokeStyle = g; ctx.lineWidth = 1.6; ctx.stroke();
          ctx.restore();
        }
      });
      raf = requestAnimationFrame(draw);
    };
    draw();
    window.addEventListener("resize", resize);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); };
  }, []);
  return <canvas ref={ref} className="fp-starfield" />;
}

/* ── Step indicator ── */
function Steps({ current }) {
  const steps = ["Enter Email", "New Password"];
  return (
    <div className="fp-steps">
      {steps.map((label, i) => {
        const n = i + 1;
        const state = current > n ? "done" : current === n ? "active" : "idle";
        return (
          <div key={n} className="fp-step">
            <div className={`fp-step-circle ${state}`}>
              {state === "done" ? "✓" : n}
            </div>
            <span className={`fp-step-label ${state}`}>{label}</span>
            {i < steps.length - 1 && (
              <div className={`fp-step-line ${current > n ? "lit" : "dim"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

export default function ForgotPassword() {
  const navigate = useNavigate();

  const [email, setEmail]           = useState("");
  const [sending, setSending]       = useState(false);
  const [step1Done, setStep1Done]   = useState(false);
  const [step1Error, setStep1Error] = useState("");

  const [token, setToken]                   = useState("");
  const [newPassword, setNewPassword]       = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword]     = useState(false);
  const [resetting, setResetting]           = useState(false);
  const [resetError, setResetError]         = useState("");
  const [resetDone, setResetDone]           = useState(false);

  const currentStep = resetDone ? 3 : step1Done ? 2 : 1;

  const handleSend = async (e) => {
    e.preventDefault();
    setSending(true); setStep1Error("");
    try {
      const res = await fetch(`${API_BASE}/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Request failed");
      setStep1Done(true);
    } catch (err) {
      setStep1Error(err.message || "Something went wrong. Try again.");
    } finally {
      setSending(false);
    }
  };

  const handleResend = async (e) => {
    e.preventDefault();
    setSending(true); setStep1Error("");
    try {
      await fetch(`${API_BASE}/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim().toLowerCase() }),
      });
    } finally {
      setSending(false);
    }
  };

  const handleReset = async (e) => {
    e.preventDefault();
    setResetError("");
    if (newPassword.length < 8) { setResetError("Password must be at least 8 characters."); return; }
    if (newPassword !== confirmPassword) { setResetError("Passwords do not match."); return; }
    if (!token.trim()) { setResetError("Please enter the reset token."); return; }
    setResetting(true);
    try {
      const res = await fetch(`${API_BASE}/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: token.trim(), new_password: newPassword }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data?.detail || "Reset failed");
      setResetDone(true);
    } catch (err) {
      setResetError(err.message || "Something went wrong. Try again.");
    } finally {
      setResetting(false);
    }
  };

  return (
    <div className="fpBg">
      <Starfield />
      <div className="fp-neb fp-neb1" />
      <div className="fp-neb fp-neb2" />

      <div className="fpContainer">
        <div className="fpCard">

          {/* Back */}
          <button
            type="button"
            className="fpBack"
            aria-label="Back"
            onClick={() => step1Done && !resetDone ? setStep1Done(false) : navigate(-1)}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" className="fpBackIcon">
              <path d="M15 18l-6-6 6-6" fill="none" stroke="currentColor"
                strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>

          <Steps current={currentStep} />

          {/* ── SUCCESS ── */}
          {resetDone ? (
            <div className="fp-success">
              <div className="fp-success-icon">✅</div>
              <h1 className="fpTitle">Password Reset!</h1>
              <p className="fpSubtitle">Your password has been updated successfully.</p>
              <button className="fpBtn" onClick={() => navigate("/")}>Back to Login</button>
            </div>

          ) : !step1Done ? (
            /* ── STEP 1 ── */
            <>
              <h1 className="fpTitle">Reset Password</h1>
              <p className="fpSubtitle">Enter your email and we'll send you a reset token.</p>
              <form onSubmit={handleSend}>
                <div className="fpFormGroup">
                  <label className="fpLabel" htmlFor="fp-email">Email</label>
                  <input
                    id="fp-email"
                    className="fpInput"
                    type="email"
                    placeholder="you@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                    autoComplete="email"
                  />
                </div>
                {step1Error && <p className="fp-error">{step1Error}</p>}
                <button className="fpBtn" type="submit" disabled={sending}>
                  {sending ? "Sending…" : "Send Reset Token"}
                </button>
                <p className="fpResend">
                  Didn't receive it?{" "}
                  <a href="#" onClick={handleResend}>Resend email</a>
                </p>
              </form>
            </>

          ) : (
            /* ── STEP 2 ── */
            <>
              <h1 className="fpTitle">New Password</h1>
              <p className="fpSubtitle">Paste your reset token and choose a new password.</p>
              <form onSubmit={handleReset}>
                <div className="fpFormGroup">
                  <label className="fpLabel" htmlFor="fp-token">Reset Token</label>
                  <input
                    id="fp-token"
                    className="fpInput"
                    type="text"
                    placeholder="Paste token here"
                    value={token}
                    onChange={(e) => setToken(e.target.value)}
                    required
                  />
                </div>
                <div className="fpFormGroup">
                  <label className="fpLabel" htmlFor="fp-newpw">New Password</label>
                  <div style={{ position: "relative" }}>
                    <input
                      id="fp-newpw"
                      className="fpInput"
                      type={showPassword ? "text" : "password"}
                      placeholder="At least 8 characters"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      required
                      style={{ paddingRight: 48 }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword(s => !s)}
                      style={{
                        position: "absolute", right: 14, top: "50%",
                        transform: "translateY(-50%)", background: "none",
                        border: "none", cursor: "pointer", padding: 0,
                        color: "rgba(255,255,255,.3)", display: "flex", alignItems: "center",
                        transition: "color .2s",
                      }}
                      onMouseEnter={e => e.currentTarget.style.color = "#c084fc"}
                      onMouseLeave={e => e.currentTarget.style.color = "rgba(255,255,255,.3)"}
                    >
                      {showPassword ? (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
                          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                          <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                          <line x1="1" y1="1" x2="23" y2="23"/>
                        </svg>
                      ) : (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none"
                          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                          <circle cx="12" cy="12" r="3"/>
                        </svg>
                      )}
                    </button>
                  </div>
                </div>
                <div className="fpFormGroup">
                  <label className="fpLabel" htmlFor="fp-confirmpw">Confirm Password</label>
                  <input
                    id="fp-confirmpw"
                    className="fpInput"
                    type={showPassword ? "text" : "password"}
                    placeholder="Repeat your new password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                  />
                </div>
                {resetError && <p className="fp-error">{resetError}</p>}
                <button className="fpBtn" type="submit" disabled={resetting}>
                  {resetting ? "Resetting…" : "Reset Password"}
                </button>
              </form>
            </>
          )}

        </div>
      </div>
    </div>
  );
}