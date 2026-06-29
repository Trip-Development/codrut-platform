export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

const loopbackHosts = new Set(["localhost", "127.0.0.1", "::1"]);
const devStackHosts = new Set(["backend", "frontend"]);

export function getApiBaseUrl(): string {
  if (process.env.VITEST && API_BASE_URL.startsWith("/")) {
    return `http://localhost:3000${API_BASE_URL}`;
  }
  if (typeof window === "undefined" && API_BASE_URL.startsWith("/")) {
    return process.env.INTERNAL_API_BASE_URL ?? "http://backend:8000/api";
  }

  return API_BASE_URL;
}

function readExplicitDemoFallbackSetting(): boolean | null {
  const explicitSetting = [
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK,
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK,
  ].find((value): value is string => Boolean(value));

  if (explicitSetting === "false") return false;
  if (explicitSetting === "true") return true;

  return null;
}

function isLoopbackHost(hostname: string): boolean {
  return loopbackHosts.has(hostname);
}

function readServerApiHostname(): string | null {
  const baseUrl = getApiBaseUrl();
  if (baseUrl.startsWith("/")) {
    return "backend";
  }

  try {
    return new URL(baseUrl).hostname;
  } catch {
    return null;
  }
}

export function isDemoFallbackEnabled(): boolean {
  const explicitSetting = readExplicitDemoFallbackSetting();
  if (explicitSetting !== null) return explicitSetting;

  if (process.env.VITEST) return true;

  if (process.env.NODE_ENV === "development") return true;

  if (typeof window !== "undefined") {
    return isLoopbackHost(window.location.hostname);
  }

  return (
    process.env.NEXT_PUBLIC_VERCEL_ENV === "development" ||
    process.env.VERCEL_ENV === "development"
  );
}

export function isSeededDemoFallbackEnabled(): boolean {
  const explicitSetting = readExplicitDemoFallbackSetting();
  if (explicitSetting !== null) return explicitSetting;

  if (process.env.VITEST) return true;

  if (typeof window !== "undefined") {
    return isLoopbackHost(window.location.hostname);
  }

  if (process.env.NODE_ENV !== "development") {
    return false;
  }

  const apiHostname = readServerApiHostname();
  if (!apiHostname) {
    return false;
  }

  return isLoopbackHost(apiHostname) || devStackHosts.has(apiHostname);
}
