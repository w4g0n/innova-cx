import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import "./ForgotPassword.css";

const API_BASE = "http://localhost:8000/api";

/* ── Validation helpers ── */
const validators = {
  email: (val) => {
    if (!val) return "Please enter your email address.";
    const re = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
    if (!re.test(val)) return "Enter a valid email address.";
    if (val.length > 254) return "Email address is too long.";
    return null;
  },
  token: (val) => {
    if (!val || !val.trim()) return "Please enter the reset token.";
    return null;
  },
  newPassword: (val, email = "") => {
    if (!val) return "Please enter a new password.";
    if (val.length < 12) return "Password must be at least 12 characters.";
    if (!/[A-Z]/.test(val)) return "Add at least one uppercase letter.";
    if (!/[a-z]/.test(val)) return "Add at least one lowercase letter.";
    if (!/\d/.test(val)) return "Add at least one number.";
    if (!/[^A-Za-z0-9]/.test(val)) return "Add at least one special character.";
    if (email) {
      const pw = val.toLowerCase();
      const local = email.toLowerCase().split("@")[0];
      const letters = local.replace(/[._+\-\d]+/g, "");
      if (letters.length >= 4) {
        for (let i = 0; i <= letters.length - 4; i++) {
          if (pw.includes(letters.slice(i, i + 4)))
            return "Password is too similar to your email.";
        }
      }
    }
    return null;
  },
  confirmPassword: (val, newPw) => {
    if (!val) return "Please confirm your password.";
    if (val !== newPw) return "Passwords do not match.";
    return null;
  },
};

/* ── Password rules (for checklist + strength) ── */
const PW_RULES = [
  { key: "length",  label: "At least 12 characters",  test: (v)      => v.length >= 12 },
  { key: "upper",   label: "Uppercase letter (A–Z)",   test: (v)      => /[A-Z]/.test(v) },
  { key: "lower",   label: "Lowercase letter (a–z)",   test: (v)      => /[a-z]/.test(v) },
  { key: "number",  label: "Number (0–9)",              test: (v)      => /\d/.test(v) },
  { key: "special", label: "Special character (!@#…)", test: (v)      => /[^A-Za-z0-9]/.test(v) },
  { key: "noemail", label: "Not similar to email",
    test: (v, email = "") => {
      if (!email) return true;
      const pw = v.toLowerCase();
      const local = email.toLowerCase().split("@")[0];
      const letters = local.replace(/[._+\-\d]+/g, "");
      if (letters.length < 4) return true;
      // Slide a 4-char window across the letter string
      // Any 4+ consecutive chars from the email found in the password = fail
      for (let i = 0; i <= letters.length - 4; i++) {
        const chunk = letters.slice(i, i + 4);
        if (pw.includes(chunk)) return false;
      }
      return true;
    }
  },
];

const STRENGTH_META = [
  null,
  { label: "Weak",        color: "#f87171" },
  { label: "Fair",        color: "#fb923c" },
  { label: "Good",        color: "#facc15" },
  { label: "Strong",      color: "#34d399" },
  { label: "Very Strong", color: "#22d3ee" },
];

function getStrength(val, email) {
  if (!val) return 0;
  const passed = PW_RULES.filter(r => r.test(val, email)).length;
  if (passed <= 1) return 1;
  if (passed <= 2) return 2;
  if (passed <= 3) return 3;
  if (passed <= 4) return 4;
  if (passed === 5) return 4;
  return 5;
}

/* ── Password strength bar ── */
function PasswordStrength({ password, email }) {
  if (!password) return null;
  const score = getStrength(password, email);
  const meta  = STRENGTH_META[score];
  return (
    <div className="fp-pwd-strength">
      <div className="fp-pwd-bars">
        {[1,2,3,4,5].map(i => (
          <div
            key={i}
            className="fp-pwd-bar"
            style={{
              background: i <= score ? meta.color : "rgba(255,255,255,.08)",
              transition: `background .25s ease ${i * 0.04}s`,
            }}
          />
        ))}
      </div>
      <span className="fp-pwd-label" style={{ color: meta.color }}>{meta.label}</span>
    </div>
  );
}

/* ── Password requirements checklist ── */
function PasswordRequirements({ password, email }) {
  if (!password) return null;
  return (
    <ul className="fp-pwd-reqs" aria-label="Password requirements">
      {PW_RULES.map(rule => {
        const pass = rule.test(password, email);
        return (
          <li key={rule.key} className={`fp-pwd-req ${pass ? "pass" : "fail"}`}>
            <span className="fp-pwd-req-icon" aria-hidden="true">
              {pass ? (
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              ) : (
                <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round">
                  <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              )}
            </span>
            {rule.label}
          </li>
        );
      })}
    </ul>
  );
}

/* ── Inline field message ── */
function FieldMessage({ error, touched }) {
  if (!touched || !error) return <div className="fp-field-msg-placeholder" />;
  return (
    <p className="fp-field-msg fp-field-msg--error" role="alert">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
      {error}
    </p>
  );
}

/* ── Starfield ── */
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

/* ── Main component ── */
export default function ForgotPassword() {
  const navigate = useNavigate();

  // Step 1
  const [email, setEmail]               = useState("");
  const [sending, setSending]           = useState(false);
  const [step1Done, setStep1Done]       = useState(false);
  const [step1Error, setStep1Error]     = useState("");
  const [touchedEmail, setTouchedEmail] = useState(false);

  // Step 2
  const [token, setToken]                     = useState("");
  const [newPassword, setNewPassword]         = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword]       = useState(false);
  const [resetting, setResetting]             = useState(false);
  const [resetError, setResetError]           = useState("");
  const [resetDone, setResetDone]             = useState(false);
  const [touchedStep2, setTouchedStep2]       = useState({ token: false, newPassword: false, confirmPassword: false });

  const currentStep = resetDone ? 3 : step1Done ? 2 : 1;

  const emailError           = validators.email(email);
  const tokenError           = validators.token(token);
  const newPasswordError     = validators.newPassword(newPassword, email);
  const confirmPasswordError = validators.confirmPassword(confirmPassword, newPassword);

  const markStep2 = (field) =>
    setTouchedStep2(prev => ({ ...prev, [field]: true }));

  const handleSend = async (e) => {
    e.preventDefault();
    setTouchedEmail(true);
    if (emailError) return;
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
    setTouchedStep2({ token: true, newPassword: true, confirmPassword: true });
    if (tokenError || newPasswordError || confirmPasswordError) return;
    setResetError("");
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

          <button
            type="button"
            className="fpBack"
            aria-label="Back"
            onClick={() => step1Done && !resetDone ? setStep1Done(false) : navigate(-1)}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" aria-hidden="true" className="fpBackIcon">
              <path d="M15 18l-6-6 6-6" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>

          <Steps current={currentStep} />

          {/* ── SUCCESS ── */}
          {resetDone ? (
            <div className="fp-success">
              <div className="fp-success-icon">
                <svg width="64" height="64" viewBox="0 0 64 64" fill="none">
                  <circle cx="32" cy="32" r="32" fill="rgba(147,51,234,0.18)" />
                  <circle cx="32" cy="32" r="26" fill="rgba(147,51,234,0.22)" stroke="rgba(168,85,247,0.55)" strokeWidth="1.5" />
                  <path d="M20 33l8 8 16-16" stroke="#c084fc" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </div>
              <h1 className="fpTitle">Password Reset!</h1>
              <p className="fpSubtitle">Your password has been updated successfully.</p>
              <button className="fpBtn" onClick={() => navigate("/")}>Back to Login</button>
            </div>

          ) : !step1Done ? (
            /* ── STEP 1 ── */
            <>
              <h1 className="fpTitle">Reset Password</h1>
              <p className="fpSubtitle">Enter your email and we'll send you a reset token.</p>
              <form onSubmit={handleSend} noValidate>
                <div className={`fpFormGroup${touchedEmail && emailError ? " fp-field--error" : ""}`}>
                  <label className="fpLabel" htmlFor="fp-email">Email</label>
                  <div className="fp-input-wrap">
                    <input
                      id="fp-email"
                      className="fpInput"
                      type="email"
                      placeholder="you@company.com"
                      value={email}
                      onChange={(e) => { setEmail(e.target.value); if (step1Error) setStep1Error(""); }}
                      onBlur={() => setTouchedEmail(true)}
                      autoComplete="email"
                      aria-invalid={touchedEmail && !!emailError}
                      aria-describedby="fp-email-msg"
                    />
                    {touchedEmail && emailError && (
                      <span className="fp-input-icon" aria-hidden="true">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                        </svg>
                      </span>
                    )}
                  </div>
                  <div id="fp-email-msg">
                    <FieldMessage error={emailError} touched={touchedEmail} />
                  </div>
                </div>

                {step1Error && (
                  <div className="fp-server-error" role="alert">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                    </svg>
                    {step1Error}
                  </div>
                )}

                <button className="fpBtn" type="submit" disabled={sending}>
                  {sending ? "Sending…" : "Verify Your Email"}
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
              <form onSubmit={handleReset} noValidate>

                {/* Token */}
                <div className={`fpFormGroup${touchedStep2.token && tokenError ? " fp-field--error" : ""}`}>
                  <label className="fpLabel" htmlFor="fp-token">Reset Token</label>
                  <div className="fp-input-wrap">
                    <input
                      id="fp-token"
                      className="fpInput"
                      type="text"
                      placeholder="Paste token here"
                      value={token}
                      onChange={(e) => setToken(e.target.value)}
                      onBlur={() => markStep2("token")}
                      aria-invalid={touchedStep2.token && !!tokenError}
                      aria-describedby="fp-token-msg"
                    />
                    {touchedStep2.token && tokenError && (
                      <span className="fp-input-icon" aria-hidden="true">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                        </svg>
                      </span>
                    )}
                  </div>
                  <div id="fp-token-msg">
                    <FieldMessage error={tokenError} touched={touchedStep2.token} />
                  </div>
                </div>

                {/* New Password */}
                <div className={`fpFormGroup${touchedStep2.newPassword && newPasswordError ? " fp-field--error" : ""}`}>
                  <label className="fpLabel" htmlFor="fp-newpw">New Password</label>
                  <div className="fp-input-wrap" style={{ position: "relative" }}>
                    <input
                      id="fp-newpw"
                      className="fpInput"
                      type={showPassword ? "text" : "password"}
                      placeholder="At least 12 characters"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      onBlur={() => markStep2("newPassword")}
                      style={{ paddingRight: 48 }}
                      aria-invalid={touchedStep2.newPassword && !!newPasswordError}
                      aria-describedby="fp-newpw-msg"
                    />
                    <button
                      type="button"
                      className="fp-pw-toggle"
                      onClick={() => setShowPassword(s => !s)}
                      aria-label={showPassword ? "Hide password" : "Show password"}
                    >
                      {showPassword ? (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                          <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                          <line x1="1" y1="1" x2="23" y2="23"/>
                        </svg>
                      ) : (
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                          <circle cx="12" cy="12" r="3"/>
                        </svg>
                      )}
                    </button>
                  </div>
                  <div id="fp-newpw-msg">
                    <PasswordStrength password={newPassword} email={email} />
                    <PasswordRequirements password={newPassword} email={email} />
                    <FieldMessage error={newPasswordError} touched={touchedStep2.newPassword} />
                  </div>
                </div>

                {/* Confirm Password */}
                <div className={`fpFormGroup${touchedStep2.confirmPassword && confirmPasswordError ? " fp-field--error" : ""}`}>
                  <label className="fpLabel" htmlFor="fp-confirmpw">Confirm Password</label>
                  <div className="fp-input-wrap">
                    <input
                      id="fp-confirmpw"
                      className="fpInput"
                      type={showPassword ? "text" : "password"}
                      placeholder="Repeat your new password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      onBlur={() => markStep2("confirmPassword")}
                      aria-invalid={touchedStep2.confirmPassword && !!confirmPasswordError}
                      aria-describedby="fp-confirmpw-msg"
                    />
                    {touchedStep2.confirmPassword && confirmPasswordError && (
                      <span className="fp-input-icon" aria-hidden="true">
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#f87171" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                        </svg>
                      </span>
                    )}
                  </div>
                  <div id="fp-confirmpw-msg">
                    <FieldMessage error={confirmPasswordError} touched={touchedStep2.confirmPassword} />
                  </div>
                </div>

                {resetError && (
                  <div className="fp-server-error" role="alert">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                      <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                    </svg>
                    {resetError}
                  </div>
                )}

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