import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { apiUrl } from "../config/apiBase";
import { getCsrfToken } from "../services/api";

export default function ConfirmMfaReset() {
  const navigate = useNavigate();
  const [status, setStatus]   = useState("idle"); // idle | loading | success | error
  const [message, setMessage] = useState("");

  useEffect(() => {
    // Token is in the URL fragment (#token=...) — never sent to server logs
    const fragment = window.location.hash.slice(1); // strip leading #
    const params   = new URLSearchParams(fragment);
    const token    = params.get("token");

    if (!token || token.length < 40) {
      setStatus("error");
      setMessage("This link is invalid or has already been used. Please ask your administrator to send a new reset request.");
      return;
    }

    const confirm = async () => {
      setStatus("loading");
      try {
        const csrf = await getCsrfToken();
        const res  = await fetch(apiUrl("/api/auth/confirm-mfa-reset"), {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(csrf ? { "X-CSRF-Token": csrf } : {}),
          },
          body: JSON.stringify({ token }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data?.detail || "This link is invalid or has expired.");
        }
        setStatus("success");
        setMessage(data.message || "MFA reset confirmed. You will be prompted to set up a new authenticator on your next login.");
      } catch (err) {
        setStatus("error");
        setMessage(err.message || "Something went wrong. Please try again.");
      }
    };

    confirm();
  }, []);

  return (
    <div style={{
      minHeight: "100vh",
      background: "#0d0d1a",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "'Segoe UI', Arial, sans-serif",
      padding: "24px 16px",
    }}>
      <div style={{
        maxWidth: 480,
        width: "100%",
        background: "#13132a",
        borderRadius: 20,
        border: "1px solid rgba(139,92,246,.25)",
        padding: "44px 40px",
        textAlign: "center",
        boxShadow: "0 8px 40px rgba(0,0,0,.5)",
      }}>
        {/* Logo */}
        <div style={{ fontSize: 22, fontWeight: 700, color: "#e9d5ff", marginBottom: 32, letterSpacing: 0.5 }}>
          Innova<span style={{ color: "#a855f7" }}>CX</span>
        </div>

        {status === "loading" && (
          <>
            <div style={{ fontSize: 40, marginBottom: 16 }}>🔐</div>
            <h2 style={{ color: "#f3e8ff", margin: "0 0 12px" }}>Confirming reset…</h2>
            <p style={{ color: "#9ca3af", fontSize: 14 }}>Please wait while we process your request.</p>
          </>
        )}

        {status === "success" && (
          <>
            <div style={{ fontSize: 52, marginBottom: 16 }}>✅</div>
            <h2 style={{ color: "#f3e8ff", margin: "0 0 12px" }}>MFA Reset Confirmed</h2>
            <p style={{ color: "#c4b5fd", fontSize: 15, lineHeight: 1.6, marginBottom: 28 }}>{message}</p>
            <button
              onClick={() => navigate("/login")}
              style={{
                padding: "13px 36px",
                background: "linear-gradient(135deg,#6d28d9,#9333ea)",
                color: "#fff",
                border: "none",
                borderRadius: 12,
                fontSize: 15,
                fontWeight: 700,
                cursor: "pointer",
                boxShadow: "0 6px 24px rgba(147,51,234,.4)",
              }}
            >
              Go to Login
            </button>
          </>
        )}

        {status === "error" && (
          <>
            <div style={{ fontSize: 52, marginBottom: 16 }}>❌</div>
            <h2 style={{ color: "#f3e8ff", margin: "0 0 12px" }}>Link Invalid or Expired</h2>
            <p style={{ color: "#c4b5fd", fontSize: 15, lineHeight: 1.6, marginBottom: 28 }}>{message}</p>
            <button
              onClick={() => navigate("/login")}
              style={{
                padding: "13px 36px",
                background: "rgba(139,92,246,.15)",
                color: "#a855f7",
                border: "1px solid rgba(139,92,246,.3)",
                borderRadius: 12,
                fontSize: 15,
                fontWeight: 700,
                cursor: "pointer",
              }}
            >
              Back to Login
            </button>
          </>
        )}

        {status === "idle" && (
          <p style={{ color: "#9ca3af" }}>Loading…</p>
        )}
      </div>
    </div>
  );
}
