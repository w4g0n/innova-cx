// src/utils/auth.ts

// Get the JWT token from localStorage
export function getToken(): string | null {
  return localStorage.getItem("access_token");
}

// Return an Authorization header object for axios/fetch
export function authHeader(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Optional: decode the JWT payload
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
