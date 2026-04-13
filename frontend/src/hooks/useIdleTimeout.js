import { useEffect, useRef, useCallback } from "react";
import { clearAllAuth, getToken } from "../utils/auth";

// 15 minutes of inactivity triggers logout.
const IDLE_MS = 15 * 60 * 1000;

// Events that count as user activity.
const ACTIVITY_EVENTS = [
  "mousemove",
  "mousedown",
  "keydown",
  "touchstart",
  "scroll",
  "click",
];

/**
 * Mounts a global idle-timeout guard for the duration of the app.
 * When the user has been inactive for IDLE_MS, clears all auth state and
 * redirects to login with sessionExpired=1.
 *
 * The timer only runs while a valid token exists in localStorage. Navigation
 * and any user interaction (mouse, keyboard, touch, scroll) reset the timer.
 * Background tabs are covered because the timer continues ticking regardless
 * of tab visibility — the user must actively interact to stay logged in.
 *
 * Call this hook once at the App level.
 */
export function useIdleTimeout() {
  const timer = useRef(null);

  const expire = useCallback(() => {
    clearAllAuth();
    const next = encodeURIComponent(
      window.location.pathname + window.location.search
    );
    window.location.href = `/login?sessionExpired=1&next=${next}`;
  }, []);

  const reset = useCallback(() => {
    // No token present means the user is not logged in — do nothing.
    if (!getToken()) {
      clearTimeout(timer.current);
      return;
    }
    clearTimeout(timer.current);
    timer.current = setTimeout(expire, IDLE_MS);
  }, [expire]);

  useEffect(() => {
    // Attempt to start the timer immediately (no-op when not logged in).
    reset();

    ACTIVITY_EVENTS.forEach((evt) =>
      window.addEventListener(evt, reset, { passive: true })
    );

    return () => {
      clearTimeout(timer.current);
      ACTIVITY_EVENTS.forEach((evt) =>
        window.removeEventListener(evt, reset)
      );
    };
  }, [reset]);
}
