import { Navigate } from "react-router-dom";
import { clearAllAuth, isTokenExpired } from "../utils/auth";

export default function ProtectedRoute({ role, children }) {
  let user = null;
  try {
    user = JSON.parse(localStorage.getItem("user") || "null");
  } catch (err) {
    console.error("ProtectedRoute: invalid user in localStorage", err);
    clearAllAuth();
    return <Navigate to="/login" replace />;
  }

  if (!user) return <Navigate to="/login" replace />;

  // Enforce real token expiry on every navigation so a user can never browse
  // protected pages after their JWT has expired — even without making an API call.
  if (isTokenExpired()) {
    clearAllAuth();
    return <Navigate to="/login?sessionExpired=1" replace />;
  }

  const storedRole = String(user.role || "").trim().toLowerCase();
  const requiredRole = String(role || "").trim().toLowerCase();

  if (requiredRole && storedRole !== requiredRole) {
    return <Navigate to="/login" replace />;
  }

  return children;
}
