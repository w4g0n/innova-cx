import { Navigate } from "react-router-dom";

export default function ProtectedRoute({ role, children }) {
  const user = JSON.parse(localStorage.getItem("user") || "null");

  // not logged in
  if (!user) return <Navigate to="/" replace />;

  // wrong role
  if (role && user.role !== role) return <Navigate to="/" replace />;

  return children;
}
