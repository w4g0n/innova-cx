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

  return (
    <div className="loginBg">
      <Starfield />
      <div className="login-neb login-neb1" />
      <div className="login-neb login-neb2" />
      <div className="login-neb login-neb3" />

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
                  onBlur={() => markTouched("email")}
                  autoComplete="email"
                  aria-invalid={touched.email && !!emailError}
                  aria-describedby="email-msg"
                />
                <span className="input-icon" aria-hidden="true">
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
                  className="input passwordInput"
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter your password"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (loginError) setLoginError("");
                  }}
                  onBlur={() => markTouched("password")}
                  autoComplete="current-password"
                  aria-invalid={touched.password && !!passwordError}
                  aria-describedby="password-msg"
                />
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