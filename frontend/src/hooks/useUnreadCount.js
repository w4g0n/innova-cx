import { useState, useEffect, useCallback } from "react";
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
 * Returns the number of unread notifications for the given role.
 * Polls every `intervalMs` milliseconds (default 60 s).
 */
export function useUnreadCount(role, intervalMs = 60_000) {
  const [count, setCount] = useState(0);

  const fetch_ = useCallback(async () => {
    const token = getAuthToken();
    if (!token || !role) return;
    try {
      const res = await fetch(apiUrl(`/api/${role}/notifications`), {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) return;
      const data = await res.json();
      const notifications = data.notifications || [];
      setCount(notifications.filter((n) => !n.read).length);
    } catch { /* silently ignore */ }
  }, [role]);

  useEffect(() => {
    fetch_();
    const id = setInterval(fetch_, intervalMs);
    return () => clearInterval(id);
  }, [fetch_, intervalMs]);

  return [count, setCount];
}
