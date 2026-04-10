import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiUrl } from "../config/apiBase";
import { getCsrfToken } from "../services/api";

/**
 * OAuthCallback — handles redirect from Google / Microsoft.
 * Route: /auth/callback
 *
 * The backend exchanges the code, creates/finds the user, and returns a JWT.
 * We then store the session and route to the correct dashboard.
 */
export default function OAuthCallback() {
  const navigate = useNavigate();
  const [error, setError] = useState("");

  useEffect(() => {
    const run = async () => {
      const params   = new URLSearchParams(window.location.search);
      const code     = params.get("code");
      const state    = params.get("state");
      const errParam = params.get("error");

      if (errParam) {
        setError("OAuth sign-in was cancelled or denied.");
        return;
      }
      if (!code || !state) {
        setError("Invalid callback — missing code or state.");
        return;
      }

      // Validate state matches what we stored before the redirect
      const storedState = sessionStorage.getItem("oauth_state");
      if (state !== storedState) {
        setError("State mismatch — possible CSRF. Please try again.");
        return;
      }
      sessionStorage.removeItem("oauth_state");

      let provider = "google";
      try {
        const decoded = JSON.parse(atob(state));
        provider = decoded.provider || "google";
      } catch { /* ignore */ }

      try {
        const csrf       = await getCsrfToken();
        const redirectUri = `${window.location.origin}/auth/callback`;
        const res = await fetch(apiUrl(`/api/auth/oauth/${provider}/callback`), {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            ...(csrf ? { "X-CSRF-Token": csrf } : {}),
          },
          body: JSON.stringify({ code, redirect_uri: redirectUri }),
        });

        const data = await res.json().catch(() => ({}));
        if (!res.ok) throw new Error(data?.detail || "Authentication failed.");

        const { access_token, user } = data;
        if (!access_token || !user) throw new Error("Invalid response from server.");

        localStorage.setItem("access_token", access_token);
        localStorage.setItem("user", JSON.stringify(user));

        const role = user.role || "customer";
        navigate(role === "customer" ? "/customer/dashboard" : `/${role}`, { replace: true });
      } catch (err) {
        setError(err.message || "Something went wrong. Please try again.");
      }
    };

    run();
  }, [navigate]);

  return (
    <div style={{
      minHeight: "100vh",
      background: "#03010a",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "'Segoe UI', Arial, sans-serif",
      padding: 24,
    }}>
      <div style={{
        maxWidth: 420, width: "100%",
        background: "#13132a",
        border: "1px solid rgba(139,92,246,.25)",
        borderRadius: 20,
        padding: "44px 40px",
        textAlign: "center",
        boxShadow: "0 8px 40px rgba(0,0,0,.5)",
      }}>
        <div style={{ fontSize: 22, fontWeight: 700, color: "#e9d5ff", marginBottom: 28 }}>
          Innova<span style={{ color: "#a855f7" }}>CX</span>
        </div>

        {!error ? (
          <>
            <div style={{ fontSize: 36, marginBottom: 16 }}>⏳</div>
            <h2 style={{ color: "#f3e8ff", margin: "0 0 10px" }}>Signing you in…</h2>
            <p style={{ color: "#9ca3af", fontSize: 14 }}>Completing authentication, please wait.</p>
          </>
        ) : (
          <>
            <div style={{ fontSize: 36, marginBottom: 16 }}>❌</div>
            <h2 style={{ color: "#f3e8ff", margin: "0 0 10px" }}>Sign-in Failed</h2>
            <p style={{ color: "#c4b5fd", fontSize: 14, marginBottom: 24 }}>{error}</p>
            <button
              onClick={() => window.location.href = "/signup"}
              style={{
                padding: "12px 28px",
                background: "linear-gradient(135deg,#6d28d9,#9333ea)",
                color: "#fff", border: "none",
                borderRadius: 12, fontSize: 14,
                fontWeight: 600, cursor: "pointer",
              }}
            >
              Try Again
            </button>
          </>
        )}
      </div>
    </div>
  );
}
