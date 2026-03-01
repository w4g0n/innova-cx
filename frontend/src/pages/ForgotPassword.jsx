import { useState } from "react";
import { useNavigate } from "react-router-dom";
import "./ForgotPassword.css";

const API_BASE = "http://localhost:8000/api";

// ── Step indicator ───────────────────────────────────────────────────────────
function Steps({ current }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 24, justifyContent: "center" }}>
      {["Enter Email", "Reset Password"].map((label, i) => {
        const step = i + 1;
        const active = current === step;
        const done   = current > step;
        return (
          <div key={step} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <div style={{
              width: 28, height: 28, borderRadius: "50%", display: "flex",
              alignItems: "center", justifyContent: "center", fontSize: 13,
              fontWeight: 700,
              background: done ? "#401c51" : active ? "#7c3aed" : "#e9d5ff",
              color: done || active ? "#fff" : "#7c3aed",
            }}>
              {done ? "✓" : step}
            </div>
            <span style={{ fontSize: 13, fontWeight: 600,
              color: active ? "#3c0066" : done ? "#401c51" : "#9ca3af" }}>
              {label}
            </span>
            {i < 1 && <div style={{ width: 32, height: 2,
              background: done ? "#401c51" : "#e9d5ff", borderRadius: 2 }} />}
          </div>
        );
      })}
    </div>
  );
}

export default function ForgotPassword() {
  const navigate = useNavigate();

  // Step 1 state
  const [email, setEmail]       = useState("");
  const [sending, setSending]   = useState(false);
  const [step1Done, setStep1Done] = useState(false);
  const [step1Error, setStep1Error] = useState("");

  // Step 2 state
  const [token, setToken]           = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [resetting, setResetting]   = useState(false);
  const [resetError, setResetError] = useState("");
  const [resetDone, setResetDone]   = useState(false);

  const currentStep = resetDone ? 3 : step1Done ? 2 : 1;

  // ── Step 1: request reset token ─────────────────────────────────────────
  const handleSend = async (e) => {
    e.preventDefault();
    setSending(true);
    setStep1Error("");
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
    setSending(true);
    setStep1Error("");
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

  // ── Step 2: submit new password ─────────────────────────────────────────
  const handleReset = async (e) => {
    e.preventDefault();
    setResetError("");

    if (newPassword.length < 8) {
      setResetError("Password must be at least 8 characters.");
      return;
    }
    if (newPassword !== confirmPassword) {
      setResetError("Passwords do not match.");
      return;
    }
    if (!token.trim()) {
      setResetError("Please enter the reset token.");
      return;
    }

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
      <div className="fpContainer">
        <div className="fpCard">

          {/* Back button */}
          <button
            type="button"
            className="fpBack"
            aria-label="Back"
            onClick={() => (step1Done && !resetDone ? setStep1Done(false) : navigate(-1))}
          >
            <svg width="26" height="26" viewBox="0 0 24 24" aria-hidden="true" className="fpBackIcon">
              <path d="M15 18l-6-6 6-6" fill="none" stroke="currentColor"
                strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </button>

          <Steps current={currentStep} />

          {/* ── SUCCESS SCREEN ── */}
          {resetDone ? (
            <div style={{ textAlign: "center", padding: "16px 0" }}>
              <div style={{ fontSize: 52, marginBottom: 12 }}>✅</div>
              <h1 className="fpTitle" style={{ marginBottom: 8 }}>Password Reset!</h1>
              <p className="fpSubtitle" style={{ marginBottom: 24 }}>
                Your password has been updated successfully.
              </p>
              <button className="fpBtn" onClick={() => navigate("/")}>
                Back to Login
              </button>
            </div>
          ) : !step1Done ? (
            /* ── STEP 1: Enter email ── */
            <>
              <h1 className="fpTitle">Reset Password</h1>
              <p className="fpSubtitle">Enter your email to receive a reset token.</p>

              <form onSubmit={handleSend}>
                <div className="fpFormGroup">
                  <label className="fpLabel" htmlFor="fp-email">Email</label>
                  <input
                    id="fp-email"
                    className="fpInput"
                    type="email"
                    placeholder="Enter your email here"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>

                {step1Error && (
                  <p style={{ color: "#b42318", fontSize: 13, marginBottom: 12 }}>
                    {step1Error}
                  </p>
                )}

                <button className="fpBtn" type="submit" disabled={sending}>
                  {sending ? "Sending…" : "Send Reset Token"}
                </button>

                <p className="fpResend">
                  Didn't receive it?{" "}
                  <a href="#" onClick={handleResend}>Click here to resend</a>
                </p>
              </form>
            </>
          ) : (
            /* ── STEP 2: Enter token + new password ── */
            <>
              <h1 className="fpTitle">Enter New Password</h1>
              <p className="fpSubtitle">
                Copy the reset token from the backend logs and enter your new password below.
              </p>

              <form onSubmit={handleReset}>
                <div className="fpFormGroup">
                  <label className="fpLabel" htmlFor="fp-token">Reset Token</label>
                  <input
                    id="fp-token"
                    className="fpInput"
                    type="text"
                    placeholder="Paste your reset token here"
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
                      style={{ paddingRight: 42 }}
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((s) => !s)}
                      style={{ position: "absolute", right: 14, top: "50%",
                        transform: "translateY(-50%)", background: "none",
                        border: "none", cursor: "pointer", padding: 0,
                        color: "#7c3aed", display: "flex", alignItems: "center" }}
                    >
                      {showPassword ? (
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
                          stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/>
                          <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/>
                          <line x1="1" y1="1" x2="23" y2="23"/>
                        </svg>
                      ) : (
                        <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
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

                {resetError && (
                  <p style={{ color: "#b42318", fontSize: 13, marginBottom: 12 }}>
                    {resetError}
                  </p>
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
