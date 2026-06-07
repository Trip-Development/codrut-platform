export const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api";

export function getApiBaseUrl(): string {
  if (typeof window === "undefined" && API_BASE_URL.startsWith("/")) {
    return process.env.INTERNAL_API_BASE_URL ?? "http://backend:8000/api";
  }

  return API_BASE_URL;
}

export function isDemoFallbackEnabled(): boolean {
  return (
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK === "true" ||
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK === "true"
  );
}
