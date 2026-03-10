import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { clearAllAuth } from './utils/auth'

// ── Global 401 interceptor ────────────────────────────────────────────────────
// Catches expired/invalid tokens mid-session so no page stays stuck showing empty data.
// Only fires on 401 (token expired/missing) — NOT 403, which this backend uses for
// "wrong role" (a normal, in-app condition that should never force a logout).
// Guard flag prevents duplicate redirects when concurrent requests all return 401.
let _sessionRedirecting = false;
const _origFetch = window.fetch.bind(window);
window.fetch = async (...args) => {
  const res = await _origFetch(...args);
  const url = (typeof args[0] === 'string' ? args[0] : args[0]?.url) ?? '';
  if (
    res.status === 401 &&
    !url.includes('/auth/login') &&
    !url.includes('/auth/totp') &&
    !_sessionRedirecting
  ) {
    _sessionRedirecting = true;
    clearAllAuth();
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.href = `/login?sessionExpired=1&next=${next}`;
  }
  return res; // return untouched so callers can still read the body
};

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)