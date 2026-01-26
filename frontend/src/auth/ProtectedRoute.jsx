import { Navigate } from "react-router-dom";

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

  return children;
}
