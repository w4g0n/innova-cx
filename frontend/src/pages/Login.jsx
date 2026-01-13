import { useNavigate } from "react-router-dom";

function Login() {
  const navigate = useNavigate();

  const loginAs = (role) => {
    localStorage.setItem("user", JSON.stringify({ role }));
    navigate(`/${role}`);
  };

  return (
    <div>
      <h2>Login</h2>
      <button onClick={() => loginAs("customer")}>Customer</button>
      <button onClick={() => loginAs("employee")}>Employee</button>
      <button onClick={() => loginAs("operator")}>Operator</button>
      <button onClick={() => loginAs("manager")}>Manager</button>
    </div>
  );
}

export default Login;
