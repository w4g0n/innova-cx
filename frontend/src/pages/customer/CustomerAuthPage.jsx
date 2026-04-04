import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { apiUrl } from "../../config/apiBase";
import { safeParseUser, sanitizeText } from "./sanitize";
import { getCsrfToken } from "../../services/api";
import "./CustomerAuthPage.css";

// Allowed role values — anything else redirects to "/"
const ALLOWED_ROLES = ["customer", "employee", "manager", "admin"];

export default function CustomerAuthPage() {
  const navigate = useNavigate();

  // Temporary login token from initial login
  const loginToken = sessionStorage.getItem("mfa_token");

  // Safely parse the stored user object — prevents JSON injection from storage
  const storedUser = safeParseUser(sessionStorage.getItem("mfa_user"));

  // Validate role against allowlist before trusting it for navigation
  const rawRole = sanitizeText(storedUser?.role, 20).toLowerCase();
  const role = ALLOWED_ROLES.includes(rawRole) ? rawRole : null;

  const [qrCode, setQrCode] = useState(null);
  const [otp, setOtp] = useState(["", "", "", "", "", ""]);
  const [verified, setVerified] = useState(false);
  const [needsSetup, setNeedsSetup] = useState(false);
  const [loading, setLoading] = useState(true);

  // State-based error display replaces alert() — avoids UI injection via error messages
  const [errorMsg, setErrorMsg] = useState("");

  const inputsRef = useRef([]);

  // ===============================
  // Check TOTP status on mount
  // ===============================
  useEffect(() => {
    // Redirect immediately if token or valid role is missing
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
        setNeedsSetup(!!data.needsSetup);

        if (data.needsSetup) {
          const qrRes = await fetch(
            apiUrl("/api/auth/totp-setup"),
            {
              headers: { Authorization: `Bearer ${loginToken}` },
            }
          );

          if (!qrRes.ok) throw new Error("Failed to fetch QR code");

          const qrData = await qrRes.json();
          // Validate the QR code value — must be a data: or https: URL, never user-supplied
          const rawQr = sanitizeText(qrData.qrCode, 4096);
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

  // ===============================
  // OTP Input Handling
  // ===============================
  const handleChange = (value, index) => {
    // Strictly enforce single-digit numeric input — reject anything else
    if (!/^\d?$/.test(value)) return;

    const updated = [...otp];
    updated[index] = value;
    setOtp(updated);
    setErrorMsg("");

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

    // Re-validate that every character is a digit before sending
    const otpCode = otp.join("");
    if (!/^\d{6}$/.test(otpCode)) {
      setErrorMsg("Please enter a valid 6-digit code.");
      return;
    }

    setErrorMsg("");

    try {
      const csrf = await getCsrfToken();
      const res = await fetch(
        apiUrl("/api/auth/totp-verify"),
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(csrf ? { "X-CSRF-Token": csrf } : {}),
          },
          body: JSON.stringify({
            login_token: loginToken,
            otp_code: otpCode,
          }),
        }
      );

      if (!res.ok) throw new Error("Verification failed");

      const data = await res.json();

      // Validate the returned access token is a non-empty string
      const accessToken = sanitizeText(data.access_token, 2048);
      const tokenType   = sanitizeText(data.token_type, 32);
      if (!accessToken) throw new Error("Invalid token response");

      setVerified(true);

      setTimeout(async () => {
        try {
          if (needsSetup) {
            const csrf2 = await getCsrfToken();
            await fetch(
              apiUrl("/api/auth/totp-setup-complete"),
              {
                method: "POST",
                headers: {
                  Authorization: `Bearer ${loginToken}`,
                  ...(csrf2 ? { "X-CSRF-Token": csrf2 } : {}),
                },
              }
            );
          }

          localStorage.setItem("access_token", accessToken);
          localStorage.setItem(
            "user",
            JSON.stringify({
              ...storedUser,
              // Store only the validated token type, not raw server data
              token_type: tokenType,
            })
          );

          sessionStorage.removeItem("mfa_token");
          sessionStorage.removeItem("mfa_user");

          // Navigate to role-specific path — role is already validated against the allowlist above
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
      // State-based error instead of alert() — alert content could be spoofed via
      // injected error messages in some environments
      setErrorMsg("Invalid or expired code. Please try again.");
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
            {/* qrCode is validated to start with data:image/ or https:// above */}
            <img src={qrCode} alt="TOTP QR Code" style={{ width: "180px" }} />
          </div>
        )}

        {!verified ? (
          <>
            <p className="auth-subtext">
              Enter the 6-digit code from your authenticator app.
            </p>

            {errorMsg && (
              <p
                role="alert"
                style={{
                  color: "#ef4444",
                  fontSize: "0.875rem",
                  marginBottom: "0.75rem",
                  textAlign: "center",
                }}
              >
                {/* errorMsg is set internally — never from raw server responses */}
                {errorMsg}
              </p>
            )}

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