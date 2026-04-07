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
 * Returns the number of held pipeline queue items.
 * Only fetches when role === "operator". Polls every 30s.
 */
export function useHeldCount(role, intervalMs = 30_000) {
  const [count, setCount] = useState(0);

  const load = useCallback(() => {
    if (role !== "operator") return;
    const token = getAuthToken();
    if (!token) return;

    fetch(apiUrl("/api/operator/pipeline-queue/stats"), {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && data.held != null) setCount(Number(data.held) || 0);
      })
      .catch(() => {});
  }, [role]);

  useEffect(() => {
    if (role !== "operator") return;
    load();
    const id = setInterval(load, intervalMs);
    return () => clearInterval(id);
  }, [role, intervalMs, load]);

  return count;
}
