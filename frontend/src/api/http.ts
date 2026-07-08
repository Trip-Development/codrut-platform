import { getApiBaseUrl } from "./runtime";

const CSRF_COOKIE_NAME = "codrut_csrf";
const CSRF_HEADER_NAME = "X-CSRF-Token";
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS", "TRACE"]);
const CSRF_EXEMPT_PATHS = new Set([
  "/api/auth/login",
  "/api/auth/register",
  "/api/auth/reset-password",
  "/api/auth/reset-password/confirm",
  "/api/companies/access-code-registration",
]);
const CSRF_EXEMPT_PATTERNS = [
  /^\/api\/communications\/campaigns\/unsubscribe\/[^/]+$/,
];

function requestMethod(init?: RequestInit): string {
  return (init?.method ?? "GET").toUpperCase();
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;

  const prefix = `${name}=`;
  const item = document.cookie
    .split(";")
    .map((entry) => entry.trim())
    .find((entry) => entry.startsWith(prefix));

  return item ? decodeURIComponent(item.slice(prefix.length)) : null;
}

function requestUrl(input: RequestInfo | URL): string {
  if (input instanceof Request) return input.url;
  if (input instanceof URL) return input.toString();
  return input;
}

function apiPathForRequest(input: RequestInfo | URL): string | null {
  if (typeof window === "undefined") return null;

  const apiBase = new URL(getApiBaseUrl(), window.location.href);
  const target = new URL(requestUrl(input), window.location.href);
  const apiBasePath = apiBase.pathname.replace(/\/+$/, "");

  if (target.origin !== apiBase.origin) return null;
  if (!target.pathname.startsWith(`${apiBasePath}/`) && target.pathname !== apiBasePath) {
    return null;
  }

  return target.pathname;
}

function isCsrfExemptPath(path: string): boolean {
  return CSRF_EXEMPT_PATHS.has(path) || CSRF_EXEMPT_PATTERNS.some((pattern) => pattern.test(path));
}

function shouldAttachCsrf(input: RequestInfo | URL, init?: RequestInit): boolean {
  if (SAFE_METHODS.has(requestMethod(init))) return false;

  const path = apiPathForRequest(input);
  return Boolean(path && !isCsrfExemptPath(path));
}

export async function ensureCsrfToken(options: { refresh?: boolean } = {}): Promise<string | null> {
  const existingToken = readCookie(CSRF_COOKIE_NAME);
  if (existingToken && !options.refresh) return existingToken;

  const response = await fetch(`${getApiBaseUrl()}/auth/csrf`, {
    cache: "no-store",
    credentials: "include",
  }).catch(() => null);
  if (!response?.ok) return readCookie(CSRF_COOKIE_NAME);

  const payload = (await response.json().catch(() => null)) as { csrf_token?: unknown } | null;
  return typeof payload?.csrf_token === "string" ? payload.csrf_token : readCookie(CSRF_COOKIE_NAME);
}

function initWithCsrf(init: RequestInit | undefined, csrfToken: string): RequestInit {
  const headers = new Headers(init?.headers);
  headers.set(CSRF_HEADER_NAME, csrfToken);

  return {
    ...init,
    headers,
  };
}

async function isCsrfFailure(response: Response): Promise<boolean> {
  if (response.status !== 403) return false;
  if (typeof response.clone !== "function") return false;
  const payload = (await response.clone().json().catch(() => null)) as {
    error?: { code?: unknown };
  } | null;
  return payload?.error?.code === "csrf_failed";
}

function canRetryRequest(input: RequestInfo | URL, init?: RequestInit): boolean {
  if (typeof Request !== "undefined" && input instanceof Request) return false;
  if (typeof ReadableStream !== "undefined" && init?.body instanceof ReadableStream) {
    return false;
  }
  return true;
}

export async function apiFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  if (!shouldAttachCsrf(input, init)) {
    return fetch(input, init);
  }

  const csrfToken = readCookie(CSRF_COOKIE_NAME);
  const response = await fetch(input, csrfToken ? initWithCsrf(init, csrfToken) : init);
  if (!(await isCsrfFailure(response)) || !canRetryRequest(input, init)) {
    return response;
  }

  const refreshedToken = await ensureCsrfToken({ refresh: true });
  if (!refreshedToken) {
    return response;
  }

  return fetch(input, initWithCsrf(init, refreshedToken));
}
