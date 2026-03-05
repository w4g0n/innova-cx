/**
 * customerTheme.js — Shared theme utility for all customer-facing pages.
 * Import this in every customer page to keep light/dark mode in sync.
 *
 * Usage:
 *   import { getStoredTheme, applyTheme, useTheme } from "./customerTheme";
 *   const [theme, toggleTheme] = useTheme();
 */

import { useState, useEffect } from "react";

export function getStoredTheme() {
  try { return localStorage.getItem("cl_theme") || "dark"; } catch { return "dark"; }
}

export function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  try { localStorage.setItem("cl_theme", theme); } catch {}
}

/** Drop-in hook: returns [theme, toggleFn] and keeps <html> in sync. */
export function useTheme() {
  const [theme, setTheme] = useState(getStoredTheme);

  useEffect(() => {
    // Apply stored theme immediately on mount (covers page navigation)
    applyTheme(getStoredTheme());
  }, []);

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  const toggleTheme = () => setTheme((t) => (t === "dark" ? "light" : "dark"));

  return [theme, toggleTheme];
}

/** Reusable theme toggle button JSX element — just call ThemeToggleBtn({ theme, onToggle }) */
export function ThemeToggleBtn({ theme, onToggle }) {
  return (
    <button
      type="button"
      className="cl-theme-btn"
      onClick={onToggle}
      aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
      title={theme === "dark" ? "Light mode" : "Dark mode"}
    >
      {theme === "dark" ? (
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="5"/>
          <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
        </svg>
      ) : (
        <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
        </svg>
      )}
    </button>
  );
}