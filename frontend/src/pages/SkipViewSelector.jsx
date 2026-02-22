import { useNavigate } from "react-router-dom";

const VIEW_CONFIG = [
  { label: "Customer View", role: "customer", path: "/customer" },
  { label: "Employee View", role: "employee", path: "/employee" },
  { label: "Manager View", role: "manager", path: "/manager" },
  { label: "Operator View", role: "operator", path: "/operator" },
];

function setBypassSession(role) {
  const email = `skip-${role}@local.dev`;
  const token = `skip-token-${role}`;

  sessionStorage.removeItem("mfa_token");
  sessionStorage.removeItem("mfa_user");
  localStorage.removeItem("temp_token");

  localStorage.setItem("access_token", token);
  localStorage.setItem(
    "user",
    JSON.stringify({
      id: `skip-${role}`,
      email,
      role,
      full_name: `Skip ${role}`,
      access_token: token,
      token_type: "bypass",
    })
  );
}

export default function SkipViewSelector() {
  const navigate = useNavigate();

  const handleSelect = (role, path) => {
    setBypassSession(role);
    navigate(path);
  };

  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
      <div style={{ textAlign: "center" }}>
        <h2>Choose a view</h2>
        <p>Skip login and open directly:</p>
        {VIEW_CONFIG.map((view) => (
          <p key={view.role}>
            <a
              href={view.path}
              onClick={(e) => {
                e.preventDefault();
                handleSelect(view.role, view.path);
              }}
            >
              {view.label}
            </a>
          </p>
        ))}
      </div>
    </main>
  );
}
