import { Navigate } from "react-router-dom";
import { clearAllAuth } from "../utils/auth";

export default function ProtectedRoute({ role, children }) {
  // Token is now an httpOnly cookie — not readable by JS.
  // Session expiry is enforced by the backend (401 on any API call).
  // Here we only check that user metadata is present and the role matches.
  let user = null;
  try {
    user = JSON.parse(localStorage.getItem("user") || "null");
  } catch (err) {
    console.error("ProtectedRoute: invalid user in localStorage", err);
    clearAllAuth();
    return <Navigate to="/login" replace />;
  }

  if (!user) return <Navigate to="/login" replace />;

  const storedRole = String(user.role || "").trim().toLowerCase();
  const requiredRole = String(role || "").trim().toLowerCase();

  if (requiredRole && storedRole !== requiredRole) {
    return <Navigate to="/login" replace />;
  }

  return children;
}
