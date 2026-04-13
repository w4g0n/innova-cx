import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { apiUrl } from "../config/apiBase";
import { getCsrfToken } from "../services/api";
import { safeParseUser, sanitizeText } from "./customer/sanitize";
import { isStaffHost } from "../utils/hostUtils";

// Starfield (same as Login/CustomerAuthPage)
function Starfield() {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    let raf;
    const resize = () => { c.width = window.innerWidth; c.height = window.innerHeight; };
    resize();
    const stars = Array.from({ length: 260 }, () => ({
      x: Math.random(), y: Math.random(),
      r: Math.random() * 1.4 + 0.2,
      twinkle: Math.random() * Math.PI * 2,
      speed: Math.random() * 0.016 + 0.004,
      color: Math.random() > 0.8 ? "#c4b5fd" : Math.random() > 0.6 ? "#e9d5ff" : "#fff",
    }));
    const shooters = Array.from({ length: 4 }, () => ({
      x: Math.random() * 0.5, y: Math.random() * 0.4,
      len: Math.random() * 140 + 80, speed: Math.random() * 5 + 3,
      angle: Math.PI / 5.5, active: false, timer: Math.random() * 300 + 80, alpha: 0,
    }));
    const draw = () => {
      ctx.clearRect(0, 0, c.width, c.height);
      stars.forEach((s) => {
        s.twinkle += s.speed;
        ctx.globalAlpha = Math.max(0.05, 0.28 + Math.sin(s.twinkle) * 0.5);
        ctx.fillStyle = s.color;
        ctx.beginPath(); ctx.arc(s.x * c.width, s.y * c.height, s.r, 0, Math.PI * 2); ctx.fill();
      });
      ctx.globalAlpha = 1;
      shooters.forEach((s) => {
        s.timer--;
        if (s.timer <= 0 && !s.active) { s.active = true; s.alpha = 1; }
        if (s.active) {
          s.x += (Math.cos(s.angle) * s.speed) / c.width;
          s.y += (Math.sin(s.angle) * s.speed) / c.height;
          s.alpha -= 0.018;
          if (s.alpha <= 0 || s.x > 1) {
            s.active = false; s.x = Math.random() * 0.45; s.y = Math.random() * 0.35;
            s.timer = Math.random() * 400 + 150;
          }
          ctx.save(); ctx.globalAlpha = s.alpha;
          const g = ctx.createLinearGradient(
            s.x * c.width, s.y * c.height,
            (s.x - (Math.cos(s.angle) * s.len) / c.width) * c.width,
            (s.y - (Math.sin(s.angle) * s.len) / c.height) * c.height
          );
          g.addColorStop(0, "#e9d5ff"); g.addColorStop(1, "transparent");
          ctx.beginPath();
          ctx.moveTo(s.x * c.width, s.y * c.height);
          ctx.lineTo(
            (s.x - (Math.cos(s.angle) * s.len) / c.width) * c.width,
            (s.y - (Math.sin(s.angle) * s.len) / c.height) * c.height
          );
          ctx.strokeStyle = g; ctx.lineWidth = 1.8; ctx.stroke(); ctx.restore();
        }
      });
      raf = requestAnimationFrame(draw);
    };
    draw();
    window.addEventListener("resize", resize);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); };
  }, []);
  return <canvas ref={ref} style={{ position: "fixed", inset: 0, width: "100%", height: "100%", zIndex: 0, pointerEvents: "none" }} />;
}

// Main component
export default function MfaSetup() {
  const navigate = useNavigate();
  const isStaff  = isStaffHost() === true;
  const loginToken  = sessionStorage.getItem("mfa_token");
  const storedUser  = safeParseUser(sessionStorage.getItem("mfa_user"));

  const [step,        setStep]        = useState(1); // 1 = email backup, 2 = TOTP QR
  const [qrCode,      setQrCode]      = useState(null);
  const [secretKey,   setSecretKey]   = useState(null);
  const [otp,         setOtp]         = useState(["", "", "", "", "", ""]);
  const [loading,     setLoading]     = useState(true);
  const [verified,    setVerified]    = useState(false);
  const [verifying,   setVerifying]   = useState(false);
  const [errorMsg,    setErrorMsg]    = useState("");
  const [shake,       setShake]       = useState(false);
  const [trustDevice, setTrustDevice] = useState(false);
  const [copied,      setCopied]      = useState(false);
  const inputsRef     = useRef([]);
  const successRef    = useRef(false);

  // Guard: redirect if no session
  useEffect(() => {
    if (!loginToken && !successRef.current) { navigate("/login", { replace: true }); return; }
    if (successRef.current) return;

    // Fetch QR code
    (async () => {
      try {
        const res = await fetch(apiUrl("/api/auth/totp-setup"), {
          headers: { Authorization: `Bearer ${loginToken}` },
          cache: "no-store",
        });
        if (!res.ok) throw new Error("Failed to load setup data");
        const data = await res.json();
        const rawQr = sanitizeText(data.qrCode, 4096);
        if (rawQr.startsWith("data:image/") || rawQr.startsWith("https://")) setQrCode(rawQr);
        if (data.secret) setSecretKey(sanitizeText(data.secret, 64));
      } catch {
        navigate("/login", { replace: true });
      } finally {
        setLoading(false);
      }
    })();
  }, [loginToken, navigate]);

  const handleChange = (value, index) => {
    if (!/^\d?$/.test(value)) return;
    const updated = [...otp];
    updated[index] = value;
    setOtp(updated);
    setErrorMsg("");
    if (value && index < 5) inputsRef.current[index + 1]?.focus();
  };

  const handleKeyDown = (e, index) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) inputsRef.current[index - 1]?.focus();
  };

  const triggerShake = () => {
    setShake(true);
    setTimeout(() => setShake(false), 520);
  };

  const handleCopySecret = () => {
    if (!secretKey) return;
    navigator.clipboard.writeText(secretKey).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  };

  const handleVerifyTotp = async (e) => {
    e.preventDefault();
    if (otp.some((d) => d === "")) return;
    const code = otp.join("");
    if (!/^\d{6}$/.test(code)) { setErrorMsg("Enter a valid 6-digit code."); return; }

    setVerifying(true);
    setErrorMsg("");
    try {
      const csrf = await getCsrfToken();
      const res  = await fetch(apiUrl("/api/auth/totp-verify"), {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
        body: JSON.stringify({ login_token: loginToken, otp_code: code, trust_device: trustDevice }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Verification failed");
      }
      const data = await res.json();
      const accessToken = sanitizeText(data.access_token, 2048);
      const responseEmail = sanitizeText(data?.user?.email || storedUser?.email || "", 254);
      const responseUser = {
        ...storedUser,
        ...(data?.user || {}),
        email: responseEmail || storedUser?.email,
        token_type: data.token_type,
      };
      if (!accessToken) throw new Error("Invalid token response");

      if (data.trusted_device_token && responseEmail) {
        const key = `td_${String(responseEmail).trim().toLowerCase()}`;
        localStorage.setItem(key, JSON.stringify({
          token: sanitizeText(data.trusted_device_token, 128),
          expiresAt: Date.now() + 30 * 24 * 60 * 60 * 1000,
        }));
      }

      // Backend /auth/totp-verify already enables MFA and sets the auth cookie.
      // Avoid a second "setup complete" call here: it is redundant and can fail
      // during the login handoff, which incorrectly bounces the user back out.

      successRef.current = true;
      localStorage.setItem("access_token", accessToken);
      localStorage.setItem("user", JSON.stringify(responseUser));
      sessionStorage.removeItem("mfa_token");
      sessionStorage.removeItem("mfa_user");

      const responseRole = sanitizeText(responseUser?.role || storedUser?.role || "customer", 32).toLowerCase();
      const dest = responseRole === "customer" ? "/customer/dashboard" : `/${responseRole}`;
      setVerified(true);
      setTimeout(() => navigate(dest, { replace: true }), 1500);
    } catch {
      triggerShake();
      setErrorMsg("Invalid or expired code. Please try again.");
      setOtp(["", "", "", "", "", ""]);
      inputsRef.current[0]?.focus();
    } finally {
      setVerifying(false);
    }
  };

  const s = isStaff ? {
    // ── Staff: white / light-purple theme (matches .loginBg--staff) ──────────
    page: {
      minHeight: "100vh", background: "#f0ebff", display: "flex", alignItems: "center",
      justifyContent: "center", padding: "40px 16px", position: "relative", overflow: "hidden",
      fontFamily: "'Segoe UI', Arial, sans-serif",
    },
    neb1: {
      position: "fixed", width: 700, height: 700, top: "-280px", left: "-220px",
      borderRadius: "50%", background: "radial-gradient(circle,rgba(89,36,180,.13),transparent 65%)",
      pointerEvents: "none", zIndex: 0, filter: "blur(10px)",
    },
    neb2: {
      position: "fixed", width: 500, height: 500, bottom: "-180px", right: "-130px",
      borderRadius: "50%", background: "radial-gradient(circle,rgba(124,58,237,.1),transparent 65%)",
      pointerEvents: "none", zIndex: 0, filter: "blur(10px)",
    },
    card: {
      position: "relative", zIndex: 10, width: "min(460px,100%)",
      background: "#ffffff", border: "1px solid rgba(89,36,180,.14)",
      borderRadius: 20, padding: "24px 28px 28px",
      boxShadow: "0 0 0 1px rgba(89,36,180,.1), 0 2px 4px rgba(89,36,180,.06), 0 12px 40px rgba(89,36,180,.12)",
      animation: "mfaSetupEnter .65s cubic-bezier(.22,1,.36,1) both",
    },
    stepBadge: {
      display: "inline-flex", alignItems: "center", gap: 5,
      background: "rgba(109,40,217,.08)", border: "1px solid rgba(109,40,217,.2)",
      borderRadius: 20, padding: "3px 12px", fontSize: 11, color: "#6d28d9",
      fontWeight: 600, letterSpacing: ".04em", marginBottom: 10,
    },
    title: { margin: "0 0 4px", fontSize: 20, fontWeight: 800, color: "#1e0a4a", letterSpacing: "-.02em" },
    sub: { margin: "0 0 12px", fontSize: 13, color: "#6b7280", lineHeight: 1.5 },
    emailBox: {
      background: "rgba(109,40,217,.05)", border: "1px solid rgba(109,40,217,.15)",
      borderRadius: 10, padding: "12px 14px", marginBottom: 14,
      display: "flex", alignItems: "center", gap: 10,
    },
    emailIcon: { width: 32, height: 32, borderRadius: "50%", background: "rgba(109,40,217,.1)",
      display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 },
    emailText: { fontSize: 13, color: "#5b21b6", lineHeight: 1.4 },
    activeBadge: {
      display: "inline-flex", alignItems: "center", gap: 4,
      background: "rgba(22,163,74,.1)", border: "1px solid rgba(22,163,74,.25)",
      borderRadius: 20, padding: "2px 8px", fontSize: 11, color: "#15803d", fontWeight: 600,
    },
    warning: {
      background: "rgba(234,179,8,.06)", border: "1px solid rgba(234,179,8,.25)",
      borderRadius: 10, padding: "10px 14px", marginBottom: 12,
    },
    warningText: { margin: 0, fontSize: 12, color: "#92400e", lineHeight: 1.5 },
    qrWrap: { textAlign: "center", marginBottom: 10 },
    qrImg: { borderRadius: 10, border: "2px solid rgba(109,40,217,.2)", background: "#fff", padding: 5 },
    secretBox: {
      background: "rgba(109,40,217,.04)", border: "1px solid rgba(109,40,217,.15)",
      borderRadius: 8, padding: "8px 12px", marginBottom: 10,
    },
    secretKey: { fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: "#5b21b6", letterSpacing: ".08em", wordBreak: "break-all" },
    otpGroup: { display: "flex", gap: 8, justifyContent: "center", marginBottom: 12 },
    otpInput: {
      width: 42, height: 50, borderRadius: 10, border: "2px solid rgba(109,40,217,.25)",
      background: "rgba(109,40,217,.04)", color: "#1e0a4a", fontSize: 20, fontWeight: 700,
      textAlign: "center", outline: "none", transition: "border-color .2s, box-shadow .2s",
    },
    error: {
      background: "rgba(220,38,38,.06)", border: "1px solid rgba(220,38,38,.2)",
      borderRadius: 8, padding: "8px 12px", marginBottom: 12,
      color: "#b91c1c", fontSize: 12,
    },
    btn: {
      width: "100%", padding: "12px", background: "linear-gradient(135deg,#6d28d9,#9333ea,#a855f7)",
      color: "#fff", border: "none", borderRadius: 12, fontSize: 14, fontWeight: 700,
      cursor: "pointer", transition: "opacity .2s, transform .15s",
      boxShadow: "0 4px 20px rgba(109,40,217,.3)",
    },
    btnSecondary: {
      width: "100%", padding: "10px", background: "transparent",
      color: "#7c3aed", border: "1px solid rgba(109,40,217,.25)",
      borderRadius: 12, fontSize: 13, fontWeight: 600, cursor: "pointer",
      marginTop: 8, transition: "color .2s, border-color .2s",
    },
    stepper: { display: "flex", gap: 8, marginBottom: 20 },
    stepDot: (active, done) => ({
      flex: 1, height: 3, borderRadius: 4,
      background: done ? "#7c3aed" : active ? "rgba(109,40,217,.4)" : "rgba(109,40,217,.12)",
      transition: "background .4s",
    }),
  } : {
    // ── Customer: dark galaxy theme (unchanged) ──────────────────────────────
    page: {
      minHeight: "100vh", background: "#03010a", display: "flex", alignItems: "center",
      justifyContent: "center", padding: "40px 16px", position: "relative", overflow: "hidden",
      fontFamily: "'Segoe UI', Arial, sans-serif",
    },
    neb1: {
      position: "fixed", width: 520, height: 520, top: "-120px", left: "-100px",
      borderRadius: "50%", background: "radial-gradient(circle,rgba(147,51,234,.18),transparent 70%)",
      pointerEvents: "none", zIndex: 1,
    },
    neb2: {
      position: "fixed", width: 400, height: 400, bottom: "-80px", right: "-60px",
      borderRadius: "50%", background: "radial-gradient(circle,rgba(232,121,249,.1),transparent 70%)",
      pointerEvents: "none", zIndex: 1,
    },
    card: {
      position: "relative", zIndex: 10, width: "min(460px,100%)",
      background: "rgba(13,5,32,0.96)", border: "1px solid rgba(139,92,246,.28)",
      borderRadius: 20, padding: "24px 28px 28px",
      boxShadow: "0 0 0 1px rgba(168,85,247,.12), 0 8px 40px rgba(0,0,0,.6), 0 0 80px rgba(147,51,234,.12)",
      animation: "mfaSetupEnter .65s cubic-bezier(.22,1,.36,1) both",
    },
    stepBadge: {
      display: "inline-flex", alignItems: "center", gap: 5,
      background: "rgba(139,92,246,.12)", border: "1px solid rgba(139,92,246,.25)",
      borderRadius: 20, padding: "3px 12px", fontSize: 11, color: "#c4b5fd",
      fontWeight: 600, letterSpacing: ".04em", marginBottom: 10,
    },
    title: { margin: "0 0 4px", fontSize: 20, fontWeight: 800, color: "#f3e8ff", letterSpacing: "-.02em" },
    sub: { margin: "0 0 12px", fontSize: 13, color: "#9ca3af", lineHeight: 1.5 },
    emailBox: {
      background: "rgba(139,92,246,.08)", border: "1px solid rgba(139,92,246,.2)",
      borderRadius: 10, padding: "12px 14px", marginBottom: 14,
      display: "flex", alignItems: "center", gap: 10,
    },
    emailIcon: { width: 32, height: 32, borderRadius: "50%", background: "rgba(139,92,246,.2)",
      display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 },
    emailText: { fontSize: 13, color: "#c4b5fd", lineHeight: 1.4 },
    activeBadge: {
      display: "inline-flex", alignItems: "center", gap: 4,
      background: "rgba(34,197,94,.12)", border: "1px solid rgba(34,197,94,.25)",
      borderRadius: 20, padding: "2px 8px", fontSize: 11, color: "#86efac", fontWeight: 600,
    },
    warning: {
      background: "rgba(245,158,11,.06)", border: "1px solid rgba(245,158,11,.2)",
      borderRadius: 10, padding: "10px 14px", marginBottom: 12,
    },
    warningText: { margin: 0, fontSize: 12, color: "rgba(251,191,36,.8)", lineHeight: 1.5 },
    qrWrap: { textAlign: "center", marginBottom: 10 },
    qrImg: { borderRadius: 10, border: "2px solid rgba(139,92,246,.3)", background: "#fff", padding: 5 },
    secretBox: {
      background: "rgba(0,0,0,.3)", border: "1px solid rgba(139,92,246,.2)",
      borderRadius: 8, padding: "8px 12px", marginBottom: 10,
    },
    secretKey: { fontFamily: "'JetBrains Mono', monospace", fontSize: 12, color: "#c4b5fd", letterSpacing: ".08em", wordBreak: "break-all" },
    otpGroup: { display: "flex", gap: 8, justifyContent: "center", marginBottom: 12 },
    otpInput: {
      width: 42, height: 50, borderRadius: 10, border: "2px solid rgba(139,92,246,.3)",
      background: "rgba(139,92,246,.08)", color: "#f3e8ff", fontSize: 20, fontWeight: 700,
      textAlign: "center", outline: "none", transition: "border-color .2s, box-shadow .2s",
    },
    error: {
      background: "rgba(239,68,68,.1)", border: "1px solid rgba(239,68,68,.25)",
      borderRadius: 8, padding: "8px 12px", marginBottom: 12,
      color: "#fca5a5", fontSize: 12,
    },
    btn: {
      width: "100%", padding: "12px", background: "linear-gradient(135deg,#6d28d9,#9333ea,#a855f7)",
      color: "#fff", border: "none", borderRadius: 12, fontSize: 14, fontWeight: 700,
      cursor: "pointer", transition: "opacity .2s, transform .15s",
      boxShadow: "0 4px 20px rgba(147,51,234,.4)",
    },
    btnSecondary: {
      width: "100%", padding: "10px", background: "transparent",
      color: "rgba(196,181,253,.6)", border: "1px solid rgba(139,92,246,.2)",
      borderRadius: 12, fontSize: 13, fontWeight: 600, cursor: "pointer",
      marginTop: 8, transition: "color .2s, border-color .2s",
    },
    stepper: { display: "flex", gap: 8, marginBottom: 20 },
    stepDot: (active, done) => ({
      flex: 1, height: 3, borderRadius: 4,
      background: done ? "#9333ea" : active ? "rgba(147,51,234,.5)" : "rgba(139,92,246,.15)",
      transition: "background .4s",
    }),
  };

  if (loading) {
    return (
      <div style={s.page}>
        {!isStaff && <Starfield />}
        <div style={{ ...s.neb1 }} /><div style={{ ...s.neb2 }} />
        <div style={{ ...s.card, textAlign: "center" }}>
          <p style={{ color: isStaff ? "#5b21b6" : "#c4b5fd", fontSize: 15 }}>Loading setup…</p>
        </div>
      </div>
    );
  }

  return (
    <div style={s.page}>
      <style>{`
        @keyframes mfaSetupEnter { from { opacity:0; transform:translateY(28px) scale(.97); } to { opacity:1; transform:translateY(0) scale(1); } }
        @keyframes mfaShake {
          0%,100%{transform:translateX(0)}
          15%{transform:translateX(-8px)}
          30%{transform:translateX(8px)}
          45%{transform:translateX(-6px)}
          60%{transform:translateX(6px)}
          75%{transform:translateX(-3px)}
          90%{transform:translateX(3px)}
        }
        @keyframes mfaSuccessPop { from { transform:scale(.5); opacity:0; } to { transform:scale(1); opacity:1; } }
        @keyframes mfaFadeUp { from { opacity:0; transform:translateY(16px); } to { opacity:1; transform:translateY(0); } }
        .mfa-setup-card--shake { animation: mfaShake 0.52s ease !important; }
        .mfa-otp-input:focus { border-color: #a855f7 !important; box-shadow: 0 0 0 3px rgba(168,85,247,.2); }
        .mfa-otp-input:not(:placeholder-shown) { border-color: rgba(168,85,247,.5) !important; }
        .mfa-btn:hover { opacity: .88; transform: translateY(-1px); }
        .mfa-btn-sec:hover { color: ${isStaff ? "#7c3aed" : "#c4b5fd"} !important; border-color: rgba(139,92,246,.5) !important; }
      `}</style>

      {!isStaff && <Starfield />}
      <div style={{ ...s.neb1 }} />
      <div style={{ ...s.neb2 }} />

      <div style={s.card} className={shake ? "mfa-setup-card--shake" : ""}>

        {/* ── VERIFIED state ── */}
        {verified ? (
          <div role="status" aria-live="polite" style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 20, padding: "32px 0", animation: "mfaFadeUp .5s ease both" }}>
            <div style={{ width: 100, height: 100, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", animation: "mfaSuccessPop .5s cubic-bezier(.22,1,.36,1) both", background: "linear-gradient(135deg,#6d28d9,#9333ea)" }}>
              <svg style={{ width: 80, height: 80 }} xmlns="http://www.w3.org/2000/svg" viewBox="0 0 52 52">
                <circle fill="none" stroke="none" cx="26" cy="26" r="25" />
                <path fill="none" stroke="#fff" strokeWidth="5" d="M14 27l7 7 17-17" />
              </svg>
            </div>
            <p style={{ fontSize: 16, fontWeight: 700, margin: 0, letterSpacing: "-.01em", color: isStaff ? "#1e0a4a" : "rgba(255,255,255,.85)" }}>
              Verification successful!
            </p>
          </div>
        ) : (
          <>
        {/* Step progress bar */}
        <div style={s.stepper}>
          <div style={s.stepDot(step === 1, step > 1)} />
          <div style={s.stepDot(step === 2, false)} />
        </div>

        {/* ── STEP 1: Email backup ── */}
        {step === 1 && (
          <>
            <div style={s.stepBadge}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>
              Step 1 of 2 — Backup Method
            </div>
            <h1 style={s.title}>Email OTP enabled</h1>
            <p style={s.sub}>
              As a backup, we've enabled email-based one-time codes for your account.
              You can use this if you ever lose access to your authenticator app.
            </p>

            <div style={s.emailBox}>
              <div style={s.emailIcon}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#a855f7" strokeWidth="2"><rect x="2" y="4" width="20" height="16" rx="2"/><polyline points="2,4 12,13 22,4"/></svg>
              </div>
              <div>
                <div style={{ ...s.emailText, color: "#e9d5ff", fontWeight: 600, marginBottom: 4 }}>
                  {storedUser?.email || "your email"}
                </div>
                <div style={s.activeBadge}>
                  <svg width="9" height="9" viewBox="0 0 24 24" fill="currentColor"><circle cx="12" cy="12" r="12"/></svg>
                  Active
                </div>
              </div>
            </div>

            <div style={s.warning}>
              <p style={s.warningText}>
                <strong style={{ color: "#fbbf24" }}>Next step:</strong> You'll scan a QR code to set up your authenticator app (Google Authenticator, Authy, etc.).
                This is your primary MFA method.
              </p>
            </div>

            <button className="mfa-btn" style={s.btn} onClick={() => setStep(2)}>
              Continue to Authenticator Setup →
            </button>
          </>
        )}

        {/* ── STEP 2: TOTP QR setup ── */}
        {step === 2 && (
          <>
            <div style={s.stepBadge}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
              Step 2 of 2 — Authenticator Setup
            </div>
            <h1 style={s.title}>Scan QR code</h1>
            <p style={s.sub}>
              Open Google Authenticator, Authy, or any TOTP app and scan the code below.
              Then enter the 6-digit code it shows.
            </p>

            <div style={s.warning}>
              <p style={s.warningText}>
                <strong style={{ color: isStaff ? "#92400e" : "#fbbf24" }}>Save this now.</strong> This QR code will not be shown again after setup.
                If you lose access to your authenticator app, contact{" "}
                <span style={{ color: "#7c3aed" }}>support@innovacx.net</span>.
              </p>
            </div>

            {qrCode && (
              <div style={s.qrWrap}>
                <img src={qrCode} alt="QR code for authenticator setup" width={180} height={180} style={s.qrImg} />
              </div>
            )}

            {secretKey && (
              <div style={s.secretBox}>
                <div style={{ fontSize: 11, color: isStaff ? "#6b7280" : "#6b7280", marginBottom: 5, letterSpacing: ".08em", textTransform: "uppercase", display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <span>Manual setup key</span>
                  <button
                    type="button"
                    onClick={handleCopySecret}
                    title="Copy secret key"
                    style={{
                      display: "inline-flex", alignItems: "center", gap: 4,
                      background: copied ? (isStaff ? "rgba(22,163,74,.12)" : "rgba(34,197,94,.12)") : (isStaff ? "rgba(109,40,217,.08)" : "rgba(139,92,246,.1)"),
                      border: `1px solid ${copied ? (isStaff ? "rgba(22,163,74,.3)" : "rgba(34,197,94,.3)") : (isStaff ? "rgba(109,40,217,.2)" : "rgba(139,92,246,.2)")}`,
                      borderRadius: 6, padding: "2px 8px", fontSize: 11, fontWeight: 600,
                      color: copied ? (isStaff ? "#15803d" : "#86efac") : (isStaff ? "#6d28d9" : "#c4b5fd"),
                      cursor: "pointer", transition: "all .2s",
                    }}
                  >
                    {copied ? (
                      <><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"><polyline points="20 6 9 17 4 12"/></svg>Copied!</>
                    ) : (
                      <><svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>Copy</>
                    )}
                  </button>
                </div>
                <div style={s.secretKey}>{secretKey}</div>
              </div>
            )}

            {errorMsg && <div style={s.error}>{errorMsg}</div>}

            <form onSubmit={handleVerifyTotp}>
              <div style={{ fontSize: 13, color: "#9ca3af", marginBottom: 8, textAlign: "center" }}>
                Enter the 6-digit code from your app
              </div>
              <div style={s.otpGroup} role="group" aria-label="One-time password">
                {otp.map((digit, index) => (
                  <input
                    key={index}
                    ref={(el) => (inputsRef.current[index] = el)}
                    type="text"
                    inputMode="numeric"
                    maxLength={1}
                    className="mfa-otp-input"
                    style={s.otpInput}
                    value={digit}
                    onChange={(e) => handleChange(e.target.value, index)}
                    onKeyDown={(e) => handleKeyDown(e, index)}
                    aria-label={`Digit ${index + 1} of 6`}
                    autoComplete="one-time-code"
                  />
                ))}
              </div>

              <label style={{ display: "flex", alignItems: "center", gap: 8, margin: "0 0 10px", color: "#c4b5fd", fontSize: 13 }}>
                <input
                  type="checkbox"
                  checked={trustDevice}
                  onChange={(e) => setTrustDevice(e.target.checked)}
                  style={{ accentColor: "#7c3aed" }}
                />
                Trust this device for 30 days
              </label>

              <button
                type="submit"
                className="mfa-btn"
                style={{ ...s.btn, opacity: otp.some((d) => d === "") ? 0.5 : 1 }}
                disabled={verifying || otp.some((d) => d === "")}
              >
                {verifying ? "Verifying…" : "Complete Setup →"}
              </button>
            </form>

            <button className="mfa-btn-sec" style={s.btnSecondary} onClick={() => setStep(1)}>
              ← Back
            </button>
          </>
        )}
          </>
        )}

      </div>
    </div>
  );
}