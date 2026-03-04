import { Navigate } from "react-router-dom";

const isStaffHost = () => window.location.hostname.startsWith("staff.");

export default function ProtectedRoute({ role, children }) {
  let user = null;
  try {
    user = JSON.parse(localStorage.getItem("user") || "null");
  } catch (err) {
    console.error("ProtectedRoute: invalid user in localStorage", err);
    localStorage.removeItem("user");
    return <Navigate to="/" replace />;
  }
  if (!user) return <Navigate to="/" replace />;

  const storedRole = String(user.role || "").trim().toLowerCase();
  const requiredRole = String(role || "").trim().toLowerCase();

  if (requiredRole && storedRole !== requiredRole) {
    return <Navigate to="/" replace />;
  }

  // Block customers from staff subdomain and staff from customer domain
  const staffRoles = ["employee", "manager", "operator"];
  if (isStaffHost() && storedRole === "customer") {
    return <Navigate to="/login" replace />;
  }
  if (!isStaffHost() && staffRoles.includes(storedRole)) {
    return <Navigate to="/login" replace />;
  }

  return children;
}
