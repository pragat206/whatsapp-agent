const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000/api/v1";

const TOKEN_KEY = "trx_token";

/** Resolved API root (from NEXT_PUBLIC_API_BASE_URL at build time). */
export function getApiBase(): string {
  return API_BASE;
}

function looksLikeNetworkFailure(err: unknown): boolean {
  if (err instanceof TypeError) return true;
  const msg = err instanceof Error ? err.message : String(err);
  return /failed to fetch|networkerror|load failed|network request failed/i.test(msg);
}

function apiUnreachableError(cause: unknown): Error {
  const prefix =
    cause instanceof Error ? cause.message : String(cause);
  return new Error(
    `${prefix}. Cannot reach the backend at ${API_BASE}. ` +
      "On Railway: set NEXT_PUBLIC_API_BASE_URL on the frontend to your API’s public HTTPS URL including /api/v1, then redeploy the frontend. " +
      "On the API service set CORS_ORIGINS to this dashboard’s origin (e.g. https://your-frontend.up.railway.app). " +
      "Use HTTPS for both; mixed http/https is blocked by the browser."
  );
}

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
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch (e) {
    if (looksLikeNetworkFailure(e)) throw apiUnreachableError(e);
    throw e instanceof Error ? e : new Error(String(e));
  }
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

/** POST multipart/form-data; do not set Content-Type (browser sets boundary). */
export async function apiForm<T = unknown>(
  path: string,
  form: FormData,
  init: Omit<RequestInit, "body" | "method"> = {}
): Promise<T> {
  const token = getToken();
  const headers = new Headers(init.headers || {});
  if (token) headers.set("Authorization", `Bearer ${token}`);
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...init,
      method: "POST",
      body: form,
      headers
    });
  } catch (e) {
    if (looksLikeNetworkFailure(e)) throw apiUnreachableError(e);
    throw e instanceof Error ? e : new Error(String(e));
  }
  if (res.status === 401) {
    setToken(null);
    if (typeof window !== "undefined") window.location.href = "/login";
  }
  if (!res.ok) {
    let detail = "";
    try {
      const body = await res.json();
      detail = body.detail ? ` — ${JSON.stringify(body.detail)}` : "";
    } catch {
      try {
        const text = await res.text();
        if (text) detail = ` — ${text}`;
      } catch {
        /* ignore */
      }
    }
    throw new Error(`${res.status} ${res.statusText}${detail}`);
  }
  return (await res.json()) as T;
}

export const API_BASE_URL = API_BASE;
