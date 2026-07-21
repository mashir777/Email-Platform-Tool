import { tokenStorage } from "@/lib/storage";
import type { ApiError, ApiResponse, AuthTokens } from "@/types/auth";

const API_BASE = String(import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");

export class ApiClientError extends Error {
  errors: Record<string, string[] | string>;

  constructor(errors: Record<string, string[] | string>) {
    const first = Object.values(errors)[0];
    const message = Array.isArray(first) ? first[0] : String(first ?? "Request failed");
    super(message);
    this.errors = errors;
  }
}

function buildUrl(path: string): string {
  return `${API_BASE}${path}`;
}

function parseErrors(data: unknown): Record<string, string[] | string> {
  if (data && typeof data === "object" && "errors" in data) {
    return (data as ApiError).errors;
  }
  return { detail: ["Request failed"] };
}

async function refreshAccessToken(): Promise<string | null> {
  const refresh = tokenStorage.getRefresh();
  if (!refresh) return null;

  const response = await fetch(buildUrl("/api/v1/auth/token/refresh/"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });

  if (!response.ok) {
    tokenStorage.clear();
    return null;
  }

  const data = (await response.json()) as ApiResponse<{ tokens: AuthTokens } & AuthTokens>;
  if (!data.success) {
    tokenStorage.clear();
    return null;
  }

  const tokens = "tokens" in data.data ? data.data.tokens : data.data;
  tokenStorage.setTokens(tokens.access, tokens.refresh);
  return tokens.access;
}

async function request<T>(
  url: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  const access = tokenStorage.getAccess();
  if (access) {
    headers.set("Authorization", `Bearer ${access}`);
  }

  let response: Response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch {
    throw new ApiClientError({
      detail: [
        "Network error reaching the API. Hard-refresh the page (Ctrl+Shift+R), confirm you are on the Vercel production URL, then try again.",
      ],
    });
  }

  if (response.status === 401 && retry && access) {
    const newAccess = await refreshAccessToken();
    if (newAccess) {
      return request<T>(url, options, false);
    }
  }

  const raw = await response.text();
  let data: ApiResponse<T> | null = null;
  try {
    data = raw ? (JSON.parse(raw) as ApiResponse<T>) : null;
  } catch {
    throw new ApiClientError({
      detail: [
        response.ok
          ? "Server returned an invalid response. Restart the backend and try again."
          : `Backend error (${response.status}). Is the Django server running?`,
      ],
    });
  }

  if (!data) {
    throw new ApiClientError({
      detail: [
        `Empty response from API (${response.status}). Open DevTools → Network → register request and retry after a hard refresh.`,
      ],
    });
  }

  if (!response.ok || !data.success) {
    throw new ApiClientError(parseErrors(data));
  }

  return data.data;
}

export function authUrl(path: string): string {
  return buildUrl(`/api/v1/auth${path}`);
}

export function apiV1Url(path: string): string {
  return buildUrl(`/api/v1${path}`);
}

/** Backend URL used in tracking pixels/links inside sent emails. */
export function getTrackingBaseUrl(): string {
  const configured = import.meta.env.VITE_TRACKING_PUBLIC_BASE_URL;
  if (configured) return String(configured).replace(/\/$/, "");

  if (typeof window !== "undefined") {
    const { hostname, origin, protocol } = window.location;
    const isLocal = hostname === "localhost" || hostname === "127.0.0.1";
    // Vercel / production: API and /t/ tracking are same-origin.
    if (!isLocal && protocol.startsWith("http")) {
      return origin;
    }
    if (API_BASE) {
      try {
        const api = new URL(API_BASE, window.location.origin);
        if (api.hostname !== "localhost" && api.hostname !== "127.0.0.1") {
          return api.origin;
        }
      } catch {
        // ignore invalid API_BASE
      }
    }
    return `http://${hostname}:8000`;
  }
  return "http://127.0.0.1:8000";
}

export async function authRequest<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  return request<T>(authUrl(path), options, retry);
}

export async function apiV1Request<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  return request<T>(apiV1Url(path), options, retry);
}

// Backward-compatible alias used by auth module
export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  retry = true,
): Promise<T> {
  return authRequest<T>(path, options, retry);
}
