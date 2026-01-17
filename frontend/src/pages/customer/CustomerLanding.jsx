import { useNavigate } from "react-router-dom";

export default function CustomerLanding() {
  const navigate = useNavigate();

  return (
    <div style={{ padding: 40 }}>
      <h2>Customer Landing Page</h2>
      <p style={{ marginTop: 10 }}>
        Welcome to InnovaCX. Choose what you want to do.
      </p>

      <div style={{ marginTop: 24, display: "flex", gap: 12 }}>
        <button
          onClick={() => navigate("/customer/dashboard")}
          style={{
            background: "var(--btn-primary)",
            color: "white",
            border: "none",
            padding: "12px 18px",
            borderRadius: 10,
          }}
        >
          Go to Dashboard
        </button>

        <button
          onClick={() => navigate("/customer/chatbot")}
          style={{
            background: "var(--btn-light)",
            color: "var(--sidebar-bg)",
            border: "none",
            padding: "12px 18px",
            borderRadius: 10,
          }}
        >
          Open Chatbot
        </button>
      </div>
    </div>
  );
}
