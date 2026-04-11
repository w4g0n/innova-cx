import { useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";

// ─── Google OAuth redirect ────────────────────────────────────────────────────
function initiateGoogleOAuth() {
  const clientId    = import.meta.env.VITE_GOOGLE_CLIENT_ID;
  const redirectUri = `${window.location.origin}/auth/callback`;
  const state       = btoa(JSON.stringify({ provider: "google", nonce: crypto.randomUUID() }));
  sessionStorage.setItem("oauth_state", state);

  const params = new URLSearchParams({
    client_id:     clientId,
    redirect_uri:  redirectUri,
    response_type: "code",
    scope:         "openid email profile",
    state,
    access_type:   "online",
    prompt:        "select_account",
  });
  window.location.href = `https://accounts.google.com/o/oauth2/v2/auth?${params}`;
}

// ─── Starfield canvas ─────────────────────────────────────────────────────────
function Starfield() {
  const ref = useRef(null);
  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext("2d");
    let raf;
    const resize = () => { c.width = window.innerWidth; c.height = window.innerHeight; };
    resize();
    const stars = Array.from({ length: 240 }, () => ({
      x: Math.random(), y: Math.random(),
      r: Math.random() * 1.3 + 0.2,
      twinkle: Math.random() * Math.PI * 2,
      speed: Math.random() * 0.014 + 0.004,
      color: Math.random() > 0.8 ? "#c4b5fd" : Math.random() > 0.6 ? "#e9d5ff" : "#fff",
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
      raf = requestAnimationFrame(draw);
    };
    draw();
    window.addEventListener("resize", resize);
    return () => { cancelAnimationFrame(raf); window.removeEventListener("resize", resize); };
  }, []);
  return (
    <canvas
      ref={ref}
      style={{
        position: "fixed", inset: 0,
        width: "100%", height: "100%",
        zIndex: 0, pointerEvents: "none",
      }}
    />
  );
}

// ─── Main component ───────────────────────────────────────────────────────────
export default function SignUp() {
  const navigate = useNavigate();

  return (
    <div style={{
      minHeight: "100vh",
      background: "#03010a",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "'Segoe UI', Arial, sans-serif",
      padding: "40px 16px",
      position: "relative",
      overflow: "hidden",
    }}>
      <Starfield />

      {/* Nebula blobs */}
      <div style={{
        position: "fixed", width: 700, height: 700,
        left: -200, top: -150, borderRadius: "50%",
        background: "radial-gradient(circle,rgba(147,51,234,.2),transparent 70%)",
        pointerEvents: "none", zIndex: 0, filter: "blur(110px)",
      }} />
      <div style={{
        position: "fixed", width: 500, height: 500,
        right: -120, bottom: -100, borderRadius: "50%",
        background: "radial-gradient(circle,rgba(232,121,249,.12),transparent 70%)",
        pointerEvents: "none", zIndex: 0, filter: "blur(110px)",
      }} />

      {/* Card */}
      <div style={{
        position: "relative", zIndex: 10,
        width: "min(440px,100%)",
        background: "rgba(5,1,14,.97)",
        border: "1px solid rgba(168,85,247,.22)",
        borderRadius: 26,
        padding: "48px 48px 52px",
        textAlign: "center",
        boxShadow: "0 0 0 1px rgba(168,85,247,.1), 0 8px 32px rgba(0,0,0,.5), 0 40px 100px rgba(0,0,0,.7), 0 0 80px rgba(147,51,234,.18)",
      }}>
        {/* Back button */}
        <button
          onClick={() => navigate("/login")}
          style={{
            position: "absolute", top: 20, left: 20,
            background: "transparent", border: "none",
            color: "rgba(255,255,255,.5)", fontSize: 14,
            fontWeight: 600, cursor: "pointer",
          }}
        >
          ← Back
        </button>

        {/* Logo */}
        <div style={{ fontSize: 22, fontWeight: 700, color: "#e9d5ff", marginBottom: 6, letterSpacing: 0.5 }}>
          Innova<span style={{ color: "#a855f7" }}>CX</span>
        </div>

        {/* Badge */}
        <div style={{
          display: "inline-block",
          fontFamily: "monospace", fontSize: 10, fontWeight: 600,
          letterSpacing: "0.2em", textTransform: "uppercase",
          color: "#a855f7", background: "rgba(147,51,234,.1)",
          border: "1px solid rgba(168,85,247,.2)",
          borderRadius: 999, padding: "5px 14px",
          marginBottom: 20,
        }}>
          Create Account
        </div>

        <h1 style={{
          fontSize: "clamp(22px,2.8vw,28px)",
          fontWeight: 900, letterSpacing: "-0.03em",
          color: "#fff", margin: "0 0 10px", lineHeight: 1.1,
        }}>
          Join InnovaCX
        </h1>

        <p style={{ fontSize: 13.5, color: "rgba(255,255,255,.38)", margin: "0 0 36px", lineHeight: 1.65 }}>
          Sign up with your Google account.<br />
          No password required.
        </p>

        {/* Google button */}
        <button
          onClick={initiateGoogleOAuth}
          style={{
            display: "flex", alignItems: "center", justifyContent: "center", gap: 12,
            width: "100%", padding: "14px 20px",
            background: "rgba(255,255,255,.04)",
            border: "1.5px solid rgba(255,255,255,.12)",
            borderRadius: 13, cursor: "pointer",
            color: "#fff", fontSize: 15, fontWeight: 600,
            marginBottom: 28,
            transition: "background .2s, border-color .2s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "rgba(255,255,255,.08)";
            e.currentTarget.style.borderColor = "rgba(255,255,255,.22)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "rgba(255,255,255,.04)";
            e.currentTarget.style.borderColor = "rgba(255,255,255,.12)";
          }}
        >
          {/* Google SVG logo */}
          <svg width="20" height="20" viewBox="0 0 48 48">
            <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
            <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
            <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
            <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
            <path fill="none" d="M0 0h48v48H0z"/>
          </svg>
          Continue with Google
        </button>

        {/* Divider + login link */}
        <div style={{
          borderTop: "1px solid rgba(168,85,247,.12)",
          paddingTop: 20,
          fontSize: 13,
          color: "rgba(255,255,255,.35)",
        }}>
          Already have an account?{" "}
          <button
            onClick={() => navigate("/login")}
            style={{
              background: "none", border: "none",
              color: "#a855f7", fontWeight: 600,
              fontSize: 13, cursor: "pointer", padding: 0,
            }}
          >
            Sign in
          </button>
        </div>

        {/* Info note */}
        <p style={{
          marginTop: 16, fontSize: 12,
          color: "rgba(255,255,255,.2)", lineHeight: 1.5,
        }}>
          By signing up you agree to the InnovaCX Terms of Service.<br />
          Accounts are subject to operator approval.
        </p>
      </div>
    </div>
  );
}
