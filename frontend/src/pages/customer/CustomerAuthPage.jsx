import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { apiUrl } from "../../config/apiBase";
import { safeParseUser, sanitizeText } from "./sanitize";
import { getCsrfToken } from "../../services/api";
import { isStaffHost } from "../../utils/hostUtils";
import "./CustomerAuthPage.css";

// Allowed role values — anything else redirects to "/"
const ALLOWED_ROLES = ["customer", "employee", "manager", "operator"];

// ─── Customer: dark galaxy starfield (identical to Login.jsx) ─────────────────
function Starfield() {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    let raf;
    const resize = () => {
      c.width  = window.innerWidth;
      c.height = window.innerHeight;
    };
    resize();
    const stars = Array.from({ length: 260 }, () => ({
      x:       Math.random(),
      y:       Math.random(),
      r:       Math.random() * 1.4 + 0.2,
      twinkle: Math.random() * Math.PI * 2,
      speed:   Math.random() * 0.016 + 0.004,
      color:
        Math.random() > 0.8
          ? "#c4b5fd"
          : Math.random() > 0.6
          ? "#e9d5ff"
          : "#fff",
    }));
    const shooters = Array.from({ length: 4 }, () => ({
      x:      Math.random() * 0.5,
      y:      Math.random() * 0.4,
      len:    Math.random() * 140 + 80,
      speed:  Math.random() * 5 + 3,
      angle:  Math.PI / 5.5,
      active: false,
      timer:  Math.random() * 300 + 80,
      alpha:  0,
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
        if (s.timer <= 0 && !s.active) { s.active = true; s.alpha = 1; }
        if (s.active) {
          s.x += (Math.cos(s.angle) * s.speed) / c.width;
          s.y += (Math.sin(s.angle) * s.speed) / c.height;
          s.alpha -= 0.018;
          if (s.alpha <= 0 || s.x > 1) {
            s.active = false;
            s.x      = Math.random() * 0.45;
            s.y      = Math.random() * 0.35;
            s.timer  = Math.random() * 400 + 150;
          }
          ctx.save();
          ctx.globalAlpha = s.alpha;
          const g = ctx.createLinearGradient(
            s.x * c.width,
            s.y * c.height,
            (s.x - (Math.cos(s.angle) * s.len) / c.width)  * c.width,
            (s.y - (Math.sin(s.angle) * s.len) / c.height) * c.height
          );
          g.addColorStop(0, "#e9d5ff");
          g.addColorStop(1, "transparent");
          ctx.strokeStyle = g;
          ctx.lineWidth = 1.2;
          ctx.beginPath();
          ctx.moveTo(s.x * c.width, s.y * c.height);
          ctx.lineTo(
            (s.x - (Math.cos(s.angle) * s.len) / c.width)  * c.width,
            (s.y - (Math.sin(s.angle) * s.len) / c.height) * c.height
          );
          ctx.stroke();
          ctx.restore();
        }
      });
      raf = requestAnimationFrame(draw);
    };
    draw();
    window.addEventListener("resize", resize);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); };
  }, []);
  return <canvas ref={ref} className="auth-starfield" />;
}

// ─── Staff: neural-network mesh background ────────────────────────────────────
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

    const nodes = Array.from({ length: 38 }, () => ({
      x: Math.random(), y: Math.random(),
      vx: (Math.random() - 0.5) * 0.00035,
      vy: (Math.random() - 0.5) * 0.00035,
    }));
    const ribbons = Array.from({ length: 5 }, (_, i) => ({
      amp: 0.06 + Math.random() * 0.07,
      freq: 0.6 + Math.random() * 1.2,
      phase: (i / 5) * Math.PI * 2,
      speed: 0.004 + Math.random() * 0.006,
      yBase: 0.2 + (i / 5) * 0.6,
      alpha: 0.025 + Math.random() * 0.035,
      color: `rgba(89,36,180,{a})`,
    }));
    const orbs = [
      { x: 0.15, y: 0.2,  r: 320, col: "rgba(89,36,180,.07)",  ax: 0.00012, ay: 0.00009, phase: 0 },
      { x: 0.82, y: 0.75, r: 260, col: "rgba(124,58,237,.05)", ax: 0.00009, ay: 0.00014, phase: 2 },
      { x: 0.5,  y: 0.5,  r: 180, col: "rgba(167,139,250,.04)",ax: 0.00015, ay: 0.0001,  phase: 4 },
    ];
    const particles = Array.from({ length: 55 }, () => ({
      x: Math.random(), y: Math.random(),
      r: Math.random() * 1.2 + 0.3,
      speed: 0.00018 + Math.random() * 0.00025,
      drift: (Math.random() - 0.5) * 0.00012,
      phase: Math.random() * Math.PI * 2,
      twinkleSpeed: 0.015 + Math.random() * 0.025,
      color: Math.random() > 0.5 ? [89,36,180] : [124,58,237],
    }));

    const drawRibbon = (rib) => {
      ctx.beginPath();
      for (let xi = 0; xi <= 1; xi += 0.005) {
        const yi = rib.yBase + Math.sin(xi * rib.freq * Math.PI * 2 + rib.phase) * rib.amp;
        xi === 0 ? ctx.moveTo(xi * c.width, yi * c.height)
                 : ctx.lineTo(xi * c.width, yi * c.height);
      }
      ctx.strokeStyle = rib.color.replace("{a}", rib.alpha);
      ctx.lineWidth = 1;
      ctx.stroke();
    };
    const drawOrb = (orb) => {
      const g = ctx.createRadialGradient(
        orb.x * c.width, orb.y * c.height, 0,
        orb.x * c.width, orb.y * c.height, orb.r
      );
      g.addColorStop(0, orb.col);
      g.addColorStop(1, "transparent");
      ctx.beginPath();
      ctx.arc(orb.x * c.width, orb.y * c.height, orb.r, 0, Math.PI * 2);
      ctx.fillStyle = g;
      ctx.fill();
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
  return <canvas ref={ref} className="auth-starfield auth-staff-canvas" />;
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function CustomerAuthPage() {
  const navigate = useNavigate();

  // Resolve theme once — null (local dev) falls back to customer galaxy
  const staffHost  = isStaffHost();
  const isStaff    = staffHost === true;
  const themeClass = isStaff ? "auth-page--staff" : "auth-page--customer";

  // Temporary login token from initial login
  const loginToken = sessionStorage.getItem("mfa_token");

  // Safely parse the stored user object — prevents JSON injection from storage
  const storedUser = safeParseUser(sessionStorage.getItem("mfa_user"));

  // Validate role against allowlist before trusting it for navigation
  const rawRole = sanitizeText(storedUser?.role, 20).toLowerCase();
  const role    = ALLOWED_ROLES.includes(rawRole) ? rawRole : null;

  // ── Core state ─────────────────────────────────────────────────────────────
  const [qrCode,        setQrCode]        = useState(null);
  const [otp,           setOtp]           = useState(["", "", "", "", "", ""]);
  const [verified,      setVerified]      = useState(false);
  const [needsSetup,    setNeedsSetup]    = useState(false);
  const [loading,       setLoading]       = useState(true);
  const [errorMsg,      setErrorMsg]      = useState("");

  // ── Trust device ───────────────────────────────────────────────────────────
  const [trustDevice,   setTrustDevice]   = useState(false);

  // ── Email OTP mode ─────────────────────────────────────────────────────────
  // "totp" = use authenticator app, "email" = receive code by email
  const [otpMode,       setOtpMode]       = useState("totp");
  const [emailOtpSent,  setEmailOtpSent]  = useState(false);
  const [emailOtpBusy,  setEmailOtpBusy]  = useState(false);
  const [resendCooldown,setResendCooldown]= useState(0);

  const inputsRef = useRef([]);

  // ── Fetch TOTP status on mount ─────────────────────────────────────────────
  useEffect(() => {
    if (!loginToken || !role) { navigate("/", { replace: true }); return; }

    const checkTOTPStatus = async () => {
      try {
        const res = await fetch(apiUrl("/api/auth/totp-status"), {
          headers: { Authorization: `Bearer ${loginToken}` },
        });
        if (!res.ok) throw new Error("Failed to fetch TOTP status");

        const data = await res.json();
        setNeedsSetup(!!data.needsSetup);

        if (data.needsSetup) {
          const qrRes = await fetch(apiUrl("/api/auth/totp-setup"), {
            headers: { Authorization: `Bearer ${loginToken}` },
          });
          if (!qrRes.ok) throw new Error("Failed to fetch QR code");

          const qrData = await qrRes.json();
          const rawQr  = sanitizeText(qrData.qrCode, 4096);
          if (rawQr.startsWith("data:image/") || rawQr.startsWith("https://")) {
            setQrCode(rawQr);
          }
        }
      } catch (err) {
        console.error("TOTP status error:", err);
        sessionStorage.clear();
        navigate("/", { replace: true });
      } finally {
        setLoading(false);
      }
    };

    checkTOTPStatus();
  }, [loginToken, role, navigate]);

  // ── Resend cooldown ticker ─────────────────────────────────────────────────
  useEffect(() => {
    if (resendCooldown <= 0) return;
    const id = setInterval(() => setResendCooldown((s) => Math.max(0, s - 1)), 1000);
    return () => clearInterval(id);
  }, [resendCooldown]);

  // ── OTP input handlers ─────────────────────────────────────────────────────
  const handleChange = (value, index) => {
    if (!/^\d?$/.test(value)) return;
    const updated = [...otp];
    updated[index] = value;
    setOtp(updated);
    setErrorMsg("");
    if (value && index < 5) inputsRef.current[index + 1]?.focus();
  };

  const handleKeyDown = (e, index) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) {
      inputsRef.current[index - 1]?.focus();
    }
  };

  // ── Handle successful auth (shared by both TOTP and Email OTP paths) ───────
  const handleAuthSuccess = async (data) => {
    const accessToken = sanitizeText(data.access_token, 2048);
    const tokenType   = sanitizeText(data.token_type,   32);
    if (!accessToken) throw new Error("Invalid token response");

    // Store trusted-device token in localStorage for 30 days
    if (data.trusted_device_token && storedUser?.email) {
      const key = `td_${storedUser.email}`;
      localStorage.setItem(key, JSON.stringify({
        token:     sanitizeText(data.trusted_device_token, 128),
        expiresAt: Date.now() + 30 * 24 * 60 * 60 * 1000,
      }));
    }

    setVerified(true);

    setTimeout(async () => {
      try {
        if (needsSetup) {
          const csrf2 = await getCsrfToken();
          await fetch(apiUrl("/api/auth/totp-setup-complete"), {
            method: "POST",
            headers: {
              Authorization: `Bearer ${loginToken}`,
              ...(csrf2 ? { "X-CSRF-Token": csrf2 } : {}),
            },
          });
        }

        localStorage.setItem("access_token", accessToken);
        localStorage.setItem("user", JSON.stringify({ ...storedUser, token_type: tokenType }));
        sessionStorage.removeItem("mfa_token");
        sessionStorage.removeItem("mfa_user");

        navigate(
          role === "customer" ? "/customer/dashboard" : `/${role}`,
          { replace: true }
        );
      } catch (err) {
        console.error("Post-verification error:", err);
        navigate("/", { replace: true });
      }
    }, 1500);
  };

  // ── Send email OTP ─────────────────────────────────────────────────────────
  const handleSendEmailOtp = async () => {
    setEmailOtpBusy(true);
    setErrorMsg("");
    try {
      const csrf = await getCsrfToken();
      const res  = await fetch(apiUrl("/api/auth/email-otp-send"), {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(csrf ? { "X-CSRF-Token": csrf } : {}),
        },
        body: JSON.stringify({ login_token: loginToken }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to send code");
      }
      setEmailOtpSent(true);
      setResendCooldown(60);
      setOtp(["", "", "", "", "", ""]);
      setTimeout(() => inputsRef.current[0]?.focus(), 100);
    } catch (err) {
      console.error("Email OTP send failed:", err);
      setErrorMsg(err.message || "Could not send code. Please try again.");
    } finally {
      setEmailOtpBusy(false);
    }
  };

  // ── Submit TOTP code ───────────────────────────────────────────────────────
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (otp.some((d) => d === "")) return;

    const otpCode = otp.join("");
    if (!/^\d{6}$/.test(otpCode)) {
      setErrorMsg("Please enter a valid 6-digit code.");
      return;
    }
    setErrorMsg("");

    try {
      const csrf = await getCsrfToken();

      if (otpMode === "email") {
        // Email OTP verify path
        const res = await fetch(apiUrl("/api/auth/email-otp-verify"), {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            ...(csrf ? { "X-CSRF-Token": csrf } : {}),
          },
          body: JSON.stringify({
            login_token:  loginToken,
            otp_code:     otpCode,
            trust_device: trustDevice,
          }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || "Verification failed");
        }
        const data = await res.json();
        await handleAuthSuccess(data);
      } else {
        // Authenticator app (TOTP) verify path
        const res = await fetch(apiUrl("/api/auth/totp-verify"), {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            ...(csrf ? { "X-CSRF-Token": csrf } : {}),
          },
          body: JSON.stringify({
            login_token:  loginToken,
            otp_code:     otpCode,
            trust_device: trustDevice,
          }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || "Verification failed");
        }
        const data = await res.json();
        await handleAuthSuccess(data);
      }
    } catch (err) {
      console.error("OTP verification failed:", err);
      setErrorMsg(err.message === "Verification failed"
        ? "Invalid or expired code. Please try again."
        : err.message || "Invalid or expired code. Please try again.");
      setOtp(["", "", "", "", "", ""]);
      inputsRef.current[0]?.focus();
    }
  };

  // ── Switch mode: reset email OTP state ────────────────────────────────────
  const switchMode = (mode) => {
    setOtpMode(mode);
    setOtp(["", "", "", "", "", ""]);
    setErrorMsg("");
    setEmailOtpSent(false);
    setResendCooldown(0);
  };

  // ── Loading state ──────────────────────────────────────────────────────────
  if (loading) {
    return (
      <div className={`auth-page ${themeClass}`}>
        {isStaff ? <StaffBackground /> : <Starfield />}
        {!isStaff && <div className="auth-neb auth-neb1" />}
        {!isStaff && <div className="auth-neb auth-neb2" />}
        <div className="auth-card">
          <p className="auth-loading-text">Loading…</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`auth-page ${themeClass}`}>

      {/* Animated background — swapped by host */}
      {isStaff ? <StaffBackground /> : <Starfield />}

      {/* Customer-only nebula blobs */}
      {!isStaff && <div className="auth-neb auth-neb1" />}
      {!isStaff && <div className="auth-neb auth-neb2" />}

      <div className="auth-card">

        <button
          type="button"
          className="backBtn"
          onClick={() => navigate("/login")}
        >
          ← Back
        </button>

        <div className="auth-header-tag">Identity Verification</div>
        <h1 className="auth-title">Verify your identity</h1>

        {/* QR setup (only shown on first TOTP setup) */}
        {needsSetup && qrCode && !verified && otpMode === "totp" && (
          <div className="auth-qr-section">
            <p>Scan this QR code with your authenticator app:</p>
            <img src={qrCode} alt="QR code for authenticator app setup" />
          </div>
        )}

        {!verified ? (
          <>
            {/* ── Mode toggle: only show when MFA is already set up ── */}
            {!needsSetup && (
              <div className="auth-mode-toggle" role="group" aria-label="Verification method">
                <button
                  type="button"
                  className={`auth-mode-btn${otpMode === "totp"  ? " active" : ""}`}
                  onClick={() => switchMode("totp")}
                >
                  🔑 Authenticator App
                </button>
                <button
                  type="button"
                  className={`auth-mode-btn${otpMode === "email" ? " active" : ""}`}
                  onClick={() => switchMode("email")}
                >
                  ✉ Email Code
                </button>
              </div>
            )}

            <p className="auth-subtext">
              {otpMode === "totp"
                ? needsSetup
                  ? "Scan the QR code above, then enter the 6-digit code from your authenticator app."
                  : "Enter the 6-digit code from your authenticator app."
                : emailOtpSent
                  ? "A 6-digit code was sent to your email. Enter it below."
                  : "We'll send a one-time code to your registered email address."}
            </p>

            {errorMsg && (
              <p role="alert" className="auth-error">
                {errorMsg}
              </p>
            )}

            {/* ── Email OTP: send button ── */}
            {otpMode === "email" && !emailOtpSent && (
              <button
                type="button"
                className="auth-primary-btn"
                onClick={handleSendEmailOtp}
                disabled={emailOtpBusy}
              >
                {emailOtpBusy ? "Sending…" : "Send Code to Email"}
              </button>
            )}

            {/* ── OTP input form ── */}
            {(otpMode === "totp" || emailOtpSent) && (
              <form onSubmit={handleSubmit}>
                <div className="otp-group" role="group" aria-label="One-time password">
                  {otp.map((digit, index) => (
                    <input
                      key={index}
                      ref={(el) => (inputsRef.current[index] = el)}
                      type="text"
                      inputMode="numeric"
                      maxLength={1}
                      className="otp-input"
                      value={digit}
                      onChange={(e) => handleChange(e.target.value, index)}
                      onKeyDown={(e) => handleKeyDown(e, index)}
                      aria-label={`Digit ${index + 1} of 6`}
                      autoComplete="one-time-code"
                    />
                  ))}
                </div>

                {/* ── Trust device checkbox ── */}
                <label className="auth-trust-label">
                  <input
                    type="checkbox"
                    className="auth-trust-checkbox"
                    checked={trustDevice}
                    onChange={(e) => setTrustDevice(e.target.checked)}
                  />
                  <span className="auth-trust-text">
                    Trust this device for 30 days
                  </span>
                </label>

                <button
                  className="auth-primary-btn"
                  type="submit"
                  disabled={otp.some((d) => d === "")}
                  style={{ marginTop: "16px" }}
                >
                  Continue
                </button>

                {/* Resend / retry link for email mode */}
                {otpMode === "email" && (
                  <div className="auth-resend-row">
                    <button
                      type="button"
                      className="auth-resend-btn"
                      onClick={handleSendEmailOtp}
                      disabled={emailOtpBusy || resendCooldown > 0}
                    >
                      {resendCooldown > 0
                        ? `Resend in ${resendCooldown}s`
                        : "Resend code"}
                    </button>
                  </div>
                )}
              </form>
            )}
          </>
        ) : (
          <div className="auth-success" role="status" aria-live="polite">
            <div className="tick-circle">
              <svg className="tick" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 52 52">
                <circle fill="none" stroke="none" cx="26" cy="26" r="25" />
                <path fill="none" stroke="#fff" strokeWidth="5" d="M14 27l7 7 17-17" />
              </svg>
            </div>
            <p>Verification successful!</p>
          </div>
        )}

      </div>
    </div>
  );
}
