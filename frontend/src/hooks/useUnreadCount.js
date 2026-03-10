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

export function useUnreadCount(role, intervalMs = 60_000) {
  const [count, setCount] = useState(0);

  const load = useCallback(() => {
    if (!role) return;
    const token = getAuthToken();
    if (!token) return;

    fetch(apiUrl(`/api/${role}/notifications`), {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!data) return;
        const unread = (data.notifications || []).filter((n) => !n.read).length;
        setCount(unread);
      })
      .catch(() => {});
  }, [role]);

  useEffect(() => {
    if (!role) return;
    const id = setInterval(load, intervalMs);
    load();
    const unsub = onNotifRefresh(load);
    return () => {
      clearInterval(id);
      unsub();
    };
  }, [role, intervalMs, load]);

  return [count, setCount];
}