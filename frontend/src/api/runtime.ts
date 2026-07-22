export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";
export const LOCAL_AUTH_ROLE_HEADER = "X-Codrut-Dev-Role";
export type LocalAuthRole = "trainer" | "participant";

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

function readExplicitLocalAuthBypassSetting(): boolean {
  const explicitSetting = [
    process.env.NEXT_PUBLIC_CODRUT_LOCAL_AUTH_BYPASS,
    process.env.CODRUT_LOCAL_AUTH_BYPASS,
  ].find((value): value is string => Boolean(value));

  return explicitSetting === "true";
}

function isLoopbackHost(hostname: string): boolean {
  return loopbackHosts.has(hostname);
}

function normalizeHostname(hostOrHostname: string): string {
  if (isLoopbackHost(hostOrHostname)) return hostOrHostname;
  try {
    return new URL(`http://${hostOrHostname}`).hostname;
  } catch {
    return hostOrHostname;
  }
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

function isLocalSeededDemoSurface(): boolean {
  if (process.env.VITEST) return true;

  if (typeof window !== "undefined") {
    const apiHostname = readServerApiHostname();
    if (!apiHostname) {
      return false;
    }

    return (
      isLoopbackHost(window.location.hostname) &&
      (isLoopbackHost(apiHostname) ||
        devStackHosts.has(apiHostname) ||
        apiHostname === window.location.hostname)
    );
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

export function localAuthRoleForPathname(pathname: string): LocalAuthRole | null {
  if (pathname === "/trainer" || pathname.startsWith("/trainer/")) {
    return pathname === "/trainer/login" ? null : "trainer";
  }
  if (pathname === "/participant" || pathname.startsWith("/participant/")) {
    return "participant";
  }
  return null;
}

export function isLocalAuthBypassEnabled(hostOrHostname?: string): boolean {
  if (process.env.NODE_ENV === "production") return false;
  if (hostOrHostname && !isLoopbackHost(normalizeHostname(hostOrHostname))) return false;
  return readExplicitLocalAuthBypassSetting() && isLocalSeededDemoSurface();
}

export function isDemoFallbackEnabled(): boolean {
  const explicitSetting = readExplicitDemoFallbackSetting();
  if (process.env.NODE_ENV === "production") return false;
  if (explicitSetting !== null) return explicitSetting;
  return Boolean(process.env.VITEST);
}

export function isLocalSeededDemoFallbackEnabled(): boolean {
  const explicitSetting = readExplicitDemoFallbackSetting();
  if (process.env.NODE_ENV === "production") return false;
  if (explicitSetting === false) return false;
  if (process.env.VITEST) return true;
  if (explicitSetting !== true) return false;

  return isLocalSeededDemoSurface();
}

export function isSeededDemoFallbackEnabled(): boolean {
  const explicitSetting = readExplicitDemoFallbackSetting();
  if (process.env.NODE_ENV === "production") return false;
  if (explicitSetting === false) return false;
  if (process.env.VITEST) return true;
  return explicitSetting === true && isLocalSeededDemoSurface();
}
