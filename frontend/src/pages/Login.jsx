import { useNavigate } from "react-router-dom";

export default function Login() {
  const navigate = useNavigate();

  const loginAs = (role) => {
    localStorage.setItem("user", JSON.stringify({ role }));

    // Customer should start on landing page
    if (role === "customer") {
      navigate("/customer");
      return;
    }

    // Others go to their dashboards
    navigate(`/${role}`);
  };

  return (
    <div style={{ padding: 40 }}>
      <h2>Login</h2>
      <p style={{ marginTop: 10 }}>Choose a view:</p>

      <div style={{ marginTop: 20, display: "flex", gap: 12, flexWrap: "wrap" }}>
        <button onClick={() => loginAs("customer")}>Customer</button>
        <button onClick={() => loginAs("employee")}>Employee</button>
        <button onClick={() => loginAs("operator")}>Operator</button>
        <button onClick={() => loginAs("manager")}>Manager</button>
      </div>
    </div>
  );
}
