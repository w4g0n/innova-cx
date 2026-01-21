import { useState } from "react";
import { useNavigate } from "react-router-dom";
import "./ForgotPassword.css";

export default function ForgotPassword() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");

  const handleSend = (e) => {
    e.preventDefault();

    // TODO later: call backend endpoint to send reset email
    // For now: just show a quick confirmation
    alert(`If an account exists for ${email}, we sent reset instructions.`);
  };

  const handleResend = (e) => {
    e.preventDefault();

    // TODO later: call backend resend endpoint
    alert(`Resent (demo). Check your inbox for ${email || "your email"}.`);
  };

  return (
    <div className="fpBg">
      <div className="fpContainer">
        <div className="fpCard">
          <button
            type="button"
            className="fpBack"
            aria-label="Back to login"
            onClick={() => navigate(-1)}
          >
            
            <svg
              width="26"
              height="26"
              viewBox="0 0 24 24"
              aria-hidden="true"
              className="fpBackIcon"
            >
              <path
                d="M15 18l-6-6 6-6"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.6"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>

          <h1 className="fpTitle">Reset Password</h1>
          <p className="fpSubtitle">Enter your email to receive reset instructions.</p>

          <form onSubmit={handleSend}>
            <div className="fpFormGroup">
              <label className="fpLabel" htmlFor="fp-email">
                Email
              </label>
              <input
                id="fp-email"
                className="fpInput"
                type="email"
                placeholder="Enter your Email here"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <button className="fpBtn" type="submit">
              Send
            </button>

            <p className="fpResend">
              Didn’t receive an email?{" "}
              <a href="#" onClick={handleResend}>
                Click here to resend
              </a>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
