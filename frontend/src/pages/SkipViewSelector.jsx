import { useNavigate } from "react-router-dom";
import { SKIP_ACCOUNTS } from "../data/skip";

function setBypassSession(account) {
  const token = `skip-token-${account.role}`;

  sessionStorage.removeItem("mfa_token");
  sessionStorage.removeItem("mfa_user");
  localStorage.removeItem("temp_token");

  localStorage.setItem("access_token", token);
  localStorage.setItem(
    "user",
    JSON.stringify({
      id: account.id,
      email: account.email,
      role: account.role,
      full_name: account.full_name,
      access_token: token,
      token_type: "bypass",
    })
  );
}

export default function SkipViewSelector() {
  const navigate = useNavigate();

  const handleSelect = (account) => {
    setBypassSession(account);
    navigate(account.path);
  };

  return (
    <main style={{ minHeight: "100vh", display: "grid", placeItems: "center" }}>
      <div style={{ textAlign: "center" }}>
        <h2>Choose a view</h2>
        <p>Skip login and open directly:</p>
        {SKIP_ACCOUNTS.map((account) => (
          <p key={account.id}>
            <a
              href={account.path}
              onClick={(e) => {
                e.preventDefault();
                handleSelect(account);
              }}
            >
              {account.label}
            </a>
          </p>
        ))}
      </div>
    </main>
  );
}
