import { useState, useEffect } from "react";
import { apiUrl } from "../config/apiBase";

function getAuthToken() {
  try {
    const raw = localStorage.getItem("user");
    if (raw) {
      const user = JSON.parse(raw);
      if (user?.access_token) return user.access_token;
    }
  } catch { /* ignore */ }
  return (
    localStorage.getItem("access_token") ||
    localStorage.getItem("token") ||
    localStorage.getItem("jwt") ||
    localStorage.getItem("authToken") ||
    ""
  );
}

/**
 * Returns the number of pending approvals for a manager.
 * Only fetches when role === "manager". Polls every 60s.
 */
export function usePendingApprovals(role, intervalMs = 60_000) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (role !== "manager") return;

    let cancelled = false;

    const load = () => {
      const token = getAuthToken();
      if (!token) return;

      fetch(apiUrl("/api/manager/approvals"), {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (cancelled || !data) return;
          const pending = data.filter((a) => a.status === "Pending").length;
          setCount(pending);
        })
        .catch(() => {});
    };

    const id = setInterval(load, intervalMs);
    load();

    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, [role, intervalMs]);

  return count;
}
