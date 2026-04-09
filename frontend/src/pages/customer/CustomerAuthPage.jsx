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
          ctx.beginPath();
          ctx.moveTo(s.x * c.width, s.y * c.height);
          ctx.lineTo(
            (s.x - (Math.cos(s.angle) * s.len) / c.width)  * c.width,
            (s.y - (Math.sin(s.angle) * s.len) / c.height) * c.height
          );
          ctx.strokeStyle = g;
          ctx.lineWidth   = 1.8;
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

// ─── Staff: animated orbs + ribbons + nodes (identical to Login.jsx) ──────────
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
      { x: 0.15, y: 0.20, r: 0.18, ax: 0.00004, ay: 0.00003, phase: 0.0, color: [180,150,230] },
      { x: 0.80, y: 0.15, r: 0.13, ax: 0.00003, ay: 0.00005, phase: 1.2, color: [200,170,255] },
      { x: 0.65, y: 0.75, r: 0.16, ax: 0.00004, ay: 0.00002, phase: 2.5, color: [170,140,220] },
      { x: 0.25, y: 0.80, r: 0.11, ax: 0.00005, ay: 0.00004, phase: 3.8, color: [210,190,255] },
      { x: 0.50, y: 0.45, r: 0.09, ax: 0.00003, ay: 0.00004, phase: 0.7, color: [190,160,240] },
      { x: 0.90, y: 0.60, r: 0.12, ax: 0.00002, ay: 0.00004, phase: 4.2, color: [220,200,255] },
    ];

    const ribbons = [
      { baseY: 0.28, amp: 0.04, freq: 0.0018, speed: 0.00008, phase: 0.0, color: [180,150,220], alpha: 0.06, thickness: 0.12 },
      { baseY: 0.55, amp: 0.03, freq: 0.0022, speed: 0.00006, phase: 2.1, color: [200,170,255], alpha: 0.04, thickness: 0.09 },
      { baseY: 0.72, amp: 0.05, freq: 0.0015, speed: 0.00010, phase: 4.3, color: [170,140,220], alpha: 0.05, thickness: 0.10 },
    ];

    const particles = Array.from({ length: 55 }, () => ({
      x: Math.random(), y: Math.random(),
      r:           Math.random() * 1.8 + 0.5,
      speed:       Math.random() * 0.000015 + 0.000005,
      drift:       Math.random() * 0.000008 - 0.000004,
      phase:       Math.random() * Math.PI * 2,
      twinkleSpeed:Math.random() * 0.008 + 0.003,
      color: Math.random() > 0.5 ? [210,190,255] : [230,215,255],
    }));

    const nodes = Array.from({ length: 22 }, () => ({
      x:  Math.random(), y: Math.random(),
      vx: (Math.random() - 0.5) * 0.00002,
      vy: (Math.random() - 0.5) * 0.00002,
    }));

    const drawOrb = (orb) => {
      const cx = orb.x * c.width, cy = orb.y * c.height;
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
        const nx   = px / W;
        const wave = Math.sin(nx * Math.PI * 2 * rib.freq * W + rib.phase + t * rib.speed * 1000);
        const py   = (rib.baseY + wave * rib.amp) * H - thick / 2;
        px === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
      }
      for (let px = W; px >= 0; px -= 6) {
        const nx   = px / W;
        const wave = Math.sin(nx * Math.PI * 2 * rib.freq * W + rib.phase + t * rib.speed * 1000);
        const py   = (rib.baseY + wave * rib.amp) * H + thick / 2;
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
          const dx   = (nodes[i].x - nodes[j].x) * W;
          const dy   = (nodes[i].y - nodes[j].y) * H;
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

  const [qrCode,     setQrCode]     = useState(null);
  const [otp,        setOtp]        = useState(["", "", "", "", "", ""]);
  const [verified,   setVerified]   = useState(false);
  const [needsSetup, setNeedsSetup] = useState(false);
  const [loading,    setLoading]    = useState(true);
  const [errorMsg,   setErrorMsg]   = useState("");

  const inputsRef = useRef([]);

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
      const res  = await fetch(apiUrl("/api/auth/totp-verify"), {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          ...(csrf ? { "X-CSRF-Token": csrf } : {}),
        },
        body: JSON.stringify({ login_token: loginToken, otp_code: otpCode }),
      });

      if (!res.ok) throw new Error("Verification failed");

      const data        = await res.json();
      const accessToken = sanitizeText(data.access_token, 2048);
      const tokenType   = sanitizeText(data.token_type,   32);
      if (!accessToken) throw new Error("Invalid token response");

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
    } catch (err) {
      console.error("TOTP verification failed:", err);
      setErrorMsg("Invalid or expired code. Please try again.");
      setOtp(["", "", "", "", "", ""]);
      inputsRef.current[0]?.focus();
    }
  };

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

      {/* Customer-only nebula blobs (CSS ::before/::after handle staff blobs) */}
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

        {/* QR setup */}
        {needsSetup && qrCode && !verified && (
          <div className="auth-qr-section">
            <p>Scan this QR code with your authenticator app:</p>
            <img src={qrCode} alt="QR code for authenticator app setup" />
          </div>
        )}

        {!verified ? (
          <>
            <p className="auth-subtext">
              Enter the 6-digit code from your authenticator app.
            </p>

            {errorMsg && (
              <p role="alert" className="auth-error">
                {errorMsg}
              </p>
            )}

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

              <button
                className="auth-primary-btn"
                type="submit"
                disabled={otp.some((d) => d === "")}
              >
                Continue
              </button>
            </form>
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