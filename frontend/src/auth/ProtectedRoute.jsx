import { Navigate } from "react-router-dom";
import { clearAllAuth } from "../utils/auth";

export default function ProtectedRoute({ role, children }) {
  // Decode the exp claim with proper base64url→base64 conversion before atob().
  // If expired: clear all auth keys and redirect to login with the return path.
  const token = localStorage.getItem("access_token");
  if (token) {
    try {
      const b64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
      const padded = b64 + "===".slice(0, (4 - (b64.length % 4)) % 4);
      const { exp } = JSON.parse(atob(padded));
      // Intentionally impure: route guard must read the real current time.
      // eslint-disable-next-line react-hooks/purity
      if (Date.now() / 1000 > exp) {
        clearAllAuth();
        const next = encodeURIComponent(window.location.pathname + window.location.search);
        return <Navigate to={`/login?sessionExpired=1&next=${next}`} replace />;
      }
    } catch {
      // Malformed token — fall through; user-check below handles it
    }
  }

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
