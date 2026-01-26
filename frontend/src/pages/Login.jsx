import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import logo from "../assets/nova-logo.png";
import "./Login.css";

function resolveRoleFromEmail(email) {
  const e = (email || "").toLowerCase().trim();

  if (e.includes("manager")) return "manager";
  if (e.includes("operator")) return "operator";
  if (e.includes("employee")) return "employee";

  return "customer";
}

export default function Login() {
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const role = useMemo(() => resolveRoleFromEmail(email), [email]);

  const handleSubmit = (e) => {
    e.preventDefault();

    localStorage.setItem(
      "user",
      JSON.stringify({
        role,
        email,
      })
    );

    if (role === "customer") {
      navigate("/customer/dashboard");
      return;
    }

    navigate(`/${role}`);
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
