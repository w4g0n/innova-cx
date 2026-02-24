import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { apiUrl } from "../../config/apiBase";
import "./CustomerAuthPage.css";

export default function CustomerAuthPage() {
  const navigate = useNavigate();

  // Temporary login token from initial login
  const loginToken = sessionStorage.getItem("mfa_token");
  const storedUser = JSON.parse(sessionStorage.getItem("mfa_user") || "{}");
  const role = storedUser?.role;

  const [qrCode, setQrCode] = useState(null);
  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [verified, setVerified] = useState(false);
  const [needsSetup, setNeedsSetup] = useState(false);
  const [loading, setLoading] = useState(true);

  const inputsRef = useRef([]);

  // ===============================
  // Check TOTP status on mount
  // ===============================
  useEffect(() => {
    if (!loginToken || !role) {
      navigate("/", { replace: true });
      return;
    }

    const checkTOTPStatus = async () => {
      try {
        const res = await fetch(
          apiUrl("/api/auth/totp-status"),
          {
            headers: { Authorization: `Bearer ${loginToken}` },
          }
        );

        if (!res.ok) throw new Error("Failed to fetch TOTP status");

        const data = await res.json();
        setNeedsSetup(data.needsSetup || false);

        if (data.needsSetup) {
          const qrRes = await fetch(
            apiUrl("/api/auth/totp-setup"),
            {
              headers: { Authorization: `Bearer ${loginToken}` },
            }
          );

          if (!qrRes.ok) throw new Error("Failed to fetch QR code");

          const qrData = await qrRes.json();
          setQrCode(qrData.qrCode);
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

  // ===============================
  // OTP Input Handling
  // ===============================
  const handleChange = (value, index) => {
    if (!/^\d?$/.test(value)) return;

    const updated = [...otp];
    updated[index] = value;
    setOtp(updated);

    if (value && index < 5) {
      inputsRef.current[index + 1]?.focus();
    }
  };

  const handleKeyDown = (e, index) => {
    if (e.key === "Backspace" && !otp[index] && index > 0) {
      inputsRef.current[index - 1]?.focus();
    }
  };

  // ===============================
  // Verify OTP
  // ===============================
  const handleSubmit = async (e) => {
    e.preventDefault();
    if (otp.some((d) => d === "")) return;

    const otpCode = otp.join("");

    try {
      const res = await fetch(
        apiUrl("/api/auth/totp-verify"),
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            login_token: loginToken,
            otp_code: otpCode,
          }),
        }
      );

      if (!res.ok) throw new Error("Verification failed");

      const data = await res.json();

      // Show success animation FIRST
      setVerified(true);

      // Delay token storage and redirect
      setTimeout(async () => {
        try {
          // Mark setup complete if needed
          if (needsSetup) {
            await fetch(
              apiUrl("/api/auth/totp-setup-complete"),
              {
                method: "POST",
                headers: { Authorization: `Bearer ${loginToken}` },
              }
            );
          }

          // Store final access token
          localStorage.setItem("access_token", data.access_token);
          localStorage.setItem(
            "user",
            JSON.stringify({
              ...storedUser,
              token_type: data.token_type,
            })
          );

          // Clear temporary session storage
          sessionStorage.removeItem("mfa_token");
          sessionStorage.removeItem("mfa_user");

          // Navigate cleanly
          navigate(
            role === "customer"
              ? "/customer/dashboard"
              : `/${role}`,
            { replace: true }
          );
        } catch (err) {
          console.error("Post-verification error:", err);
          navigate("/", { replace: true });
        }
      }, 1500);
    } catch (err) {
      console.error("TOTP verification failed:", err);
      alert("Invalid or expired code. Try again.");
      setOtp(["", "", "", "", "", ""]);
      inputsRef.current[0]?.focus();
    }
  };

  // ===============================
  // Loading State
  // ===============================
  if (loading) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <p>Loading...</p>
        </div>
      </div>
    );
  }

  // ===============================
  // UI
  // ===============================
  return (
    <div className="auth-page">
      <div className="auth-card">
        <h1 className="auth-title">Verify your identity</h1>

        {needsSetup && qrCode && !verified && (
          <div style={{ textAlign: "center", marginBottom: "1rem" }}>
            <p>Scan this QR code with your authenticator app:</p>
            <img src={qrCode} alt="TOTP QR Code" style={{ width: "180px" }} />
          </div>
        )}

        {!verified ? (
          <>
            <p className="auth-subtext">
              Enter the 6-digit code from your authenticator app.
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
          </>
        ) : (
          <div className="auth-success">
            <div className="tick-circle">
              <svg
                className="tick"
                xmlns="http://www.w3.org/2000/svg"
                viewBox="0 0 52 52"
              >
                <circle
                  fill="none"
                  stroke="none"
                  cx="26"
                  cy="26"
                  r="25"
                />
                <path
                  fill="none"
                  stroke="#fff"
                  strokeWidth="5"
                  d="M14 27l7 7 17-17"
                />
              </svg>
            </div>
            <p>Verification successful!</p>
          </div>
        )}
      </div>
    </div>
  );
}
