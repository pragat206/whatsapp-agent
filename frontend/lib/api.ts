const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

const TOKEN_KEY = "trx_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(TOKEN_KEY);
}

export function setToken(t: string | null) {
  if (typeof window === "undefined") return;
  if (t) window.localStorage.setItem(TOKEN_KEY, t);
  else window.localStorage.removeItem(TOKEN_KEY);
}

export async function api<T = unknown>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers || {});
  if (!headers.has("Content-Type") && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  if (res.status === 401) {
    setToken(null);
    if (typeof window !== "undefined") window.location.href = "/login";
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body.detail ? ` — ${JSON.stringify(body.detail)}` : "";
    } catch {}
    throw new Error(`${res.status} ${res.statusText}${detail}`);
  }
  if (res.status === 204) return undefined as unknown as T;
  return (await res.json()) as T;
}

export const API_BASE_URL = API_BASE;
