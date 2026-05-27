const API = "http://127.0.0.1:8000/api";

// Access token lives in memory only (safer than localStorage for short-lived tokens)
// Refresh token in sessionStorage (cleared when tab closes)
let accessToken = null;

export function getToken() { return accessToken; }
export function isLoggedIn() { return !!accessToken; }

/** Normalize FastAPI error payloads (string or validation array). */
export function formatApiError(data, fallback = "Request failed") {
  const detail = data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item.msg || item.message || JSON.stringify(item)).join("; ");
  }
  if (detail && typeof detail === "object") return JSON.stringify(detail);
  return data?.message || fallback;
}

export async function login(username, password) {
  let res;
  try {
    res = await fetch(`${API}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });
  } catch {
    throw new Error("Cannot reach the API server. Start the backend on http://127.0.0.1:8000");
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(formatApiError(data, "Login failed"));

  accessToken = data.access_token;
  sessionStorage.setItem("refresh_token", data.refresh_token);

  if (data.user?.username) return data.user;
  return await getMe();
}

export async function logout() {
  const refresh = sessionStorage.getItem("refresh_token");
  if (refresh) {
    fetch(`${API}/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refresh }),
    }).catch(() => {});
  }
  accessToken = null;
  sessionStorage.removeItem("refresh_token");
}

export async function tryRestoreSession() {
  const refresh = sessionStorage.getItem("refresh_token");
  if (!refresh) return null;

  const res = await fetch(`${API}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });

  if (!res.ok) {
    sessionStorage.removeItem("refresh_token");
    accessToken = null;
    return null;
  }

  const data = await res.json().catch(() => null);
  if (!data?.access_token) {
    sessionStorage.removeItem("refresh_token");
    accessToken = null;
    return null;
  }

  accessToken = data.access_token;
  sessionStorage.setItem("refresh_token", data.refresh_token);
  return await getMe();
}

export async function getMe() {
  const res = await apiFetch(`${API}/auth/me`);
  if (!res.ok) return null;
  return res.json();
}

// Use this instead of fetch() for all protected API calls
export function apiFetch(url, options = {}) {
  return fetch(url, {
    ...options,
    headers: {
      ...(options.headers || {}),
      Authorization: accessToken ? `Bearer ${accessToken}` : "",
    },
  });
}
