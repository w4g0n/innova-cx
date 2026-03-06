/**
 * customerThemeUtils.js — Non-component theme utilities.
 * Kept separate from CustomerTheme.jsx so fast-refresh works correctly.
 */

export function getStoredTheme() {
  try { return localStorage.getItem("cl_theme") || "dark"; } catch (_err) { return "dark"; }
}

export function applyTheme(theme) {
  document.documentElement.setAttribute("data-theme", theme);
  try { localStorage.setItem("cl_theme", theme); } catch (_err) { /* ignore */ }
}