import { useState, useRef, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import "./CustomerAuthPage.css";

export default function CustomerAuthPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const role = location.state?.role;

  useEffect(() => {
    if (!role) {
      navigate("/", { replace: true });
    }
  }, [role, navigate]);

  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const inputsRef = useRef([]);

  const handleChange = (value, index) => {
    if (!/^\d?$/.test(value)) return;

    const updated = [...otp];
    updated[index] = value;
    setOtp(updated);

    if (value && index < 5) {
      inputsRef.current[index + 1].focus();
    }
  };

  const handleKeyDown = (e, index) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) {
      inputsRef.current[index - 1].focus();
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();

    if (otp.some((d) => d === "")) return;

    if (role === "customer") {
      navigate("/customer");
      return;
    }

    navigate(`/${role}`);
  };

  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-title">Verify your identity</h1>

        <p className="auth-subtext">
          Enter the 6-digit verification code we sent to
          <br />
          <span className="auth-email">your@email.com</span>
        </p>

        <form onSubmit={handleSubmit}>
          <div className="otp-group">
            {otp.map((digit, index) => (
              <input
                key={index}
                ref={(el) => (inputsRef.current[index] = el)}
                type="text"
                inputMode="numeric"
                maxLength={1}
                className="otp-input"
                value={digit}
                onChange={(e) =>
                  handleChange(e.target.value, index)
                }
                onKeyDown={(e) => handleKeyDown(e, index)}
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

        <div className="auth-resend">
          <span>Didn’t receive an email?</span>
          <button className="auth-link-btn">Resend</button>
        </div>

        <button className="auth-secondary-btn">
          Try another method
        </button>
      </div>
    </div>
  );
}