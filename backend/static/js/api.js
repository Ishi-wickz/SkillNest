// One place for every request: CSRF header, JSON, and consistent errors.
function getCookie(name) {
  // Read fresh on every call: Django rotates the token at login
  const match = document.cookie.split("; ").find((c) => c.startsWith(name + "="));
  return match ? decodeURIComponent(match.split("=")[1]) : null;
}

export class ApiError extends Error {
  constructor(status, data) {
    super((data && data.detail) || "Request failed");
    this.status = status;
    this.data = data; // field errors, e.g. { email: ["..."] }
  }
}

export async function api(path, { method = "GET", body } = {}) {
  const headers = { Accept: "application/json" };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (method !== "GET") headers["X-CSRFToken"] = getCookie("csrftoken") || "";

  const res = await fetch("/api" + path, {
    method,
    headers,
    credentials: "same-origin",
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, data);
  return data;
}

// Call once per page so the browser holds a csrftoken cookie
export const ensureCsrf = () => api("/auth/csrf/");
export const getMe = () => api("/me/").catch(() => null); // null = logged out