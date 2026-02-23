import { useState } from "react";
import { useNavigate } from "react-router-dom";
import logo from "../assets/nova-logo.png";
import "./Login.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export default function Login() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      // Step 1: Login with email/password
      const res = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Login failed. Check your credentials.");
        setLoading(false);
        return;
      }

      const data = await res.json();

      // DISABLE_MFA bypass: backend returns token_type "bearer" when DISABLE_MFA=true in .env
      // To re-enable full MFA: remove DISABLE_MFA from .env and restart backend —
      //   sed -i '/DISABLE_MFA/d' ~/innova-cx/.env
      //   docker-compose --profile pipeline restart backend
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
    } catch (error) {
      console.error("Login error:", error);
      alert("Network error or backend not running.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="loginBg">
      <button
        type="button"
        onClick={() => navigate("/skip")}
        style={{ position: "absolute", top: 12, right: 12, zIndex: 10 }}
      >
        Skip
      </button>
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
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </div>

            <div className="field">
              <label className="label">Password</label>
              <input
                className="input"
                type="password"
                placeholder="Enter your Password here"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

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
