/**
 * HTTP client for the CareerMatch AI API.
 * - Same-origin requests (`/api/...`) proxied by Vite/Nginx, so session cookies are first-party.
 * - Sends the CSRF double-submit token (`cm_csrf` cookie → `X-CSRF-Token` header)
 *   on every state-changing request.
 * - Never handles AI provider keys: all AI calls happen in the backend.
 */

export const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "/api/v1";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function readCookie(name: string): string | null {
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split("=").slice(1).join("=")) : null;
}

let sessionBootstrap: Promise<void> | null = null;

/** Ensures a session (and CSRF cookie) exists before mutating requests. */
export function ensureSession(): Promise<void> {
  if (readCookie("cm_csrf")) return Promise.resolve();
  sessionBootstrap ??= fetch(`${API_BASE}/sessions/current`, { credentials: "include" })
    .then(() => undefined)
    .finally(() => {
      sessionBootstrap = null;
    });
  return sessionBootstrap;
}

type RequestOptions = Omit<RequestInit, "body"> & { json?: unknown; body?: BodyInit };

export async function apiRaw(path: string, opts: RequestOptions = {}): Promise<Response> {
  const method = (opts.method ?? "GET").toUpperCase();
  const headers = new Headers(opts.headers);
  let body = opts.body;
  if (opts.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(opts.json);
  }
  if (!["GET", "HEAD", "OPTIONS"].includes(method)) {
    await ensureSession();
    const csrf = readCookie("cm_csrf");
    if (csrf) headers.set("X-CSRF-Token", csrf);
  }
  const res = await fetch(`${API_BASE}${path}`, { ...opts, method, headers, body, credentials: "include" });
  if (!res.ok) {
    let code = "http_error";
    let message = `Erro ${res.status}`;
    let details: unknown;
    try {
      const data = await res.json();
      code = data?.error?.code ?? code;
      message = data?.error?.message ?? message;
      details = data?.error?.details;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, code, message, details);
  }
  return res;
}

export async function api<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const res = await apiRaw(path, opts);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
