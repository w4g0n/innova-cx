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

export function useUnreadCount(role, intervalMs = 60_000) {
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!role) return;

    let cancelled = false;

    const load = () => {
      const token = getAuthToken();
      if (!token) return;

      fetch(apiUrl(`/api/${role}/notifications`), {
        headers: { Authorization: `Bearer ${token}` },
      })
        .then((res) => (res.ok ? res.json() : null))
        .then((data) => {
          if (cancelled || !data) return;
          const unread = (data.notifications || []).filter((n) => !n.read).length;
          setCount(unread);
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

  return [count, setCount];
}