import { useState } from "react";
import { useNavigate } from "react-router-dom";
import logo from "../assets/nova-logo.png";
import { apiUrl } from "../config/apiBase";
import "./Login.css";

export default function Login() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loginError, setLoginError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoginError("");
    setLoading(true);

    try {
      // Step 1: Login with email/password
      const res = await fetch(apiUrl("/api/auth/login"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        if (res.status === 401) {
          setLoginError("Incorrect email or password.");
        } else {
          setLoginError(err.detail || "Unable to log in right now. Please try again.");
        }
        return;
      }

      const data = await res.json();

      // ✅ DEV FORCE-BYPASS MFA:
      // If your backend has DISABLE_MFA=true (or you're testing locally),
      // skip /verify and go straight to the dashboard.
      // Re-enable MFA later by restoring the "MFA flow" block below.
      sessionStorage.removeItem("mfa_token");
      sessionStorage.removeItem("mfa_user");

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

      const role = data.user?.role;
      navigate(role === "customer" ? "/customer/dashboard" : `/${role}`, { replace: true });
      return;

      /*
      ==========================
      ✅ MFA flow (RESTORE LATER)
      ==========================

      // DISABLE_MFA bypass: backend returns token_type "bearer" when DISABLE_MFA=true in .env
      if (data.token_type === "bearer") {
        localStorage.setItem("access_token", data.access_token);
        localStorage.setItem(
          "user",
          JSON.stringify({
            id: data.user.id,
            email: data.user.email,
            role: data.user.role,
            full_name: data.user.full_name,
            token_type: data.token_type,
          })
        );

        const role = data.user.role;
        navigate(role === "customer" ? "/customer/dashboard" : `/${role}`, {
          replace: true,
        });
        return;
      }

      // Step 2: Store a temporary token for MFA verification
      // This is NOT the final JWT — only used for OTP verification
      sessionStorage.setItem("mfa_token", data.access_token);
      sessionStorage.setItem(
        "mfa_user",
        JSON.stringify({
          id: data.user.id,
          email: data.user.email,
          role: data.user.role,
          full_name: data.user.full_name,
        })
      );

      // Step 3: Redirect to MFA verification page
      navigate("/verify");
      */
    } catch (error) {
      const target = apiUrl("/api/auth/login");
      console.error("Login error:", error, "| target URL:", target);
      setLoginError(`Cannot reach the server at ${target}. Make sure the backend is running on that address.`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="loginBg">
      <div className="loginWrapper">
        <section className="loginLeft">
          <div className="loginOverlay" />
          <div className="loginLeftContent">
            <h1 className="welcomeTitle">Welcome back!</h1>
            <p className="welcomeSub">Sign-in using your credentials.</p>
            <div className="markWrap">
              <img src={logo} alt="InnovaCX logo" className="novaLogo" />
            </div>
          </div>
        </section>

        <section className="loginRight">
          <div className="loginHeader">
            <h2 className="loginTitle">Log In To InnovaCX</h2>
          </div>

          <form className="loginForm" onSubmit={handleSubmit}>
            <div className="field">
              <label className="label">Email</label>
              <input
                className="input"
                type="email"
                placeholder="Enter your Email here"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (loginError) setLoginError("");
                }}
                required
              />
            </div>

            <div className="field">
              <label className="label">Password</label>
              <div className="passwordField">
                <input
                  className="input passwordInput"
                  type={showPassword ? "text" : "password"}
                  placeholder="Enter your Password here"
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (loginError) setLoginError("");
                  }}
                  required
                />
                <button
                  type="button"
                  className="passwordToggleBtn"
                  onClick={() => setShowPassword((prev) => !prev)}
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
            </div>

            {loginError && (
              <p className="loginError" role="alert">
                {loginError}
              </p>
            )}

            <button
              type="button"
              className="forgotLink"
              onClick={() => navigate("/forgot-password")}
            >
              Forgot password?
            </button>

            <button type="submit" className="loginBtn" disabled={loading}>
              {loading ? "Logging in..." : "Log In"}
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}