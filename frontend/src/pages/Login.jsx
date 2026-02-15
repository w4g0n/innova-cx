import { useState } from "react";
import { useNavigate } from "react-router-dom";
import logo from "../assets/nova-logo.png";
import "./Login.css";

export default function Login() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();

    try {
      const base = import.meta.env.VITE_API_BASE_URL;
      if (!base) {
        alert("Missing VITE_API_BASE_URL in your .env file.");
        return;
      }

      const res = await fetch(`${base}/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.detail || "Login failed. Please check your credentials.");
        return;
      }

      const data = await res.json();

      // ✅ store token in a key the employee pages will find
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("token", data.access_token); // optional (extra compatibility)

      // keep user info separately too (nice for UI)
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
      if (role === "customer") {
        navigate("/customer/dashboard");
      } else {
        navigate(`/${role}`);
      }
    } catch (error) {
      console.error(error);
      alert("Network error. Please make sure the backend is running.");
    }
  };

  return (
    <div className="loginBg">
      <div className="loginWrapper">
        <section className="loginLeft">
          <div className="loginOverlay" />
          <div className="loginLeftContent">
            <h1 className="welcomeTitle">Welcome back!</h1>
            <p className="welcomeSub">Sign-in using your given credentials.</p>
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

            <button type="submit" className="loginBtn">
              Log In
            </button>
          </form>
        </section>
      </div>
    </div>
  );
}