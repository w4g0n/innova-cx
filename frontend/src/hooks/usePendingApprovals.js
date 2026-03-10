import { useState, useEffect, useCallback } from "react";
import { apiUrl } from "../config/apiBase";
import { onNotifRefresh } from "../utils/notifRefresh";

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
 * Also re-fetches immediately on notif-refresh events.
 */
export function usePendingApprovals(role, intervalMs = 60_000) {
  const [count, setCount] = useState(0);

  const load = useCallback(() => {
    if (role !== "manager") return;
    const token = getAuthToken();
    if (!token) return;

    fetch(apiUrl("/api/manager/approvals"), {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) return;
        const pending = data.filter((a) => a.status === "Pending").length;
        setCount(pending);
      })
      .catch(() => {});
  }, [role]);

  useEffect(() => {
    if (role !== "manager") return;
    const id = setInterval(load, intervalMs);
    load();
    const unsub = onNotifRefresh(load);
    return () => {
      clearInterval(id);
      unsub();
    };
  }, [role, intervalMs, load]);

  return count;
}