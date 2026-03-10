// src/utils/auth.ts

// Keys used in localStorage
const TOKEN_KEY = "access_token";
const TEMP_TOKEN_KEY = "temp_token";

// -----------------------------
// Store tokens
// -----------------------------
export function setToken(token: string, temporary = false) {
  if (temporary) {
    localStorage.setItem(TEMP_TOKEN_KEY, token);
  } else {
    localStorage.setItem(TOKEN_KEY, token);
    localStorage.removeItem(TEMP_TOKEN_KEY); // remove temp token once full token is issued
  }
}

// Get full JWT
export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

// Get temporary token (used before TOTP verification)
export function getTempToken(): string | null {
  return localStorage.getItem(TEMP_TOKEN_KEY);
}

// Remove all tokens (logout)
export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(TEMP_TOKEN_KEY);
}

// Remove every auth-related localStorage key (session expiry / full logout)
export function clearAllAuth() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("user");
  localStorage.removeItem("token");
  localStorage.removeItem("temp_token");
}

// -----------------------------
// Headers for API calls
// -----------------------------
export function authHeader(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// -----------------------------
// Decode JWT payload
// -----------------------------
export function getUser(): { sub: string; role: string; email: string } | null {
  const token = getToken();
  if (!token) return null;

  try {
    const payload = JSON.parse(atob(token.split(".")[1]));
    return {
      sub: payload.sub,
      role: payload.role,
      email: payload.email,
    };
  } catch (e) {
    console.error("Failed to decode JWT", e);
    return null;
  }
}

// -----------------------------
// Helper: check if user is logged in
// -----------------------------
export function isLoggedIn(): boolean {
  return !!getToken();
}

// -----------------------------
// Helper: check if user must verify MFA
// -----------------------------
export function needsMFA(): boolean {
  return !!getTempToken();
}
