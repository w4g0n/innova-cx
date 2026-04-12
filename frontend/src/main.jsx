import { StrictMode, Component } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { clearAllAuth } from './utils/auth'

class GlobalErrorBoundary extends Component {
  state = { hasError: false };

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    // Log privately — never expose error details to the user
    console.error('[ErrorBoundary]', error, info?.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          display: 'flex', flexDirection: 'column', alignItems: 'center',
          justifyContent: 'center', height: '100vh', background: '#06010f', color: '#fff',
          fontFamily: 'sans-serif', gap: '12px'
        }}>
          <p style={{ fontSize: '18px', margin: 0 }}>Something went wrong.</p>
          <p style={{ fontSize: '14px', opacity: 0.6, margin: 0 }}>
            Please refresh the page or contact support if the issue persists.
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              marginTop: '8px', padding: '8px 20px', borderRadius: '8px',
              border: 'none', background: '#5924b4', color: '#fff',
              cursor: 'pointer', fontSize: '14px'
            }}
          >
            Refresh
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

// Catches expired/invalid tokens mid-session so no page stays stuck showing empty data.
// Only fires on 401 (token expired/missing) — NOT 403, which this backend uses for
// "wrong role" (a normal, in-app condition that should never force a logout).
// Guard flag prevents duplicate redirects when concurrent requests all return 401.
//
// Also injects credentials: "include" on every request so httpOnly auth cookies
// are sent automatically — individual pages no longer need to set this per-call.
let _sessionRedirecting = false;
const _origFetch = window.fetch.bind(window);
window.fetch = async (...args) => {
  // Inject credentials: "include" so the httpOnly auth cookie is sent automatically.
  // Exclude pre-MFA flows (/auth/totp-status, /auth/totp-setup, /auth/totp-setup-complete)
  // — those use a short-lived Bearer temp token and must NOT send a stale session cookie,
  // which get_current_user would try first and reject if expired.
  const url = (typeof args[0] === 'string' ? args[0] : args[0]?.url) ?? '';
  const init = args[1] ?? {};
  const isPreMfaFlow =
    url.includes('/auth/totp-status') ||
    url.includes('/auth/totp-setup') ||
    url.includes('/auth/totp-setup-complete');
  if (!init.credentials && !isPreMfaFlow) {
    args = [args[0], { ...init, credentials: 'include' }];
  }
  const res = await _origFetch(...args);
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
    <GlobalErrorBoundary>
      <App />
    </GlobalErrorBoundary>
  </StrictMode>,
)
