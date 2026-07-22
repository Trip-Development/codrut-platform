import { NextResponse, type NextRequest } from "next/server";

import { THEME_PREPAINT_CSP_HASH } from "@/lib/theme-prepaint";

const protectedPrefixes = ["/participant", "/trainer"];
const publicPaths = new Set(["/trainer/login"]);
const localHosts = new Set(["localhost", "127.0.0.1", "::1"]);

function isDemoFallbackEnabled(): boolean {
  const explicitSetting = [
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK,
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK,
  ].find((value): value is string => Boolean(value));
  if (process.env.NODE_ENV === "production") return false;
  return explicitSetting === "true";
}

function requestHostname(request: NextRequest): string {
  const host =
    request.headers.get("x-forwarded-host") ??
    request.headers.get("host") ??
    request.nextUrl.hostname;
  if (localHosts.has(host)) return host;
  try {
    return new URL(`http://${host}`).hostname;
  } catch {
    return host;
  }
}

function isLocalAuthBypassEnabled(request: NextRequest): boolean {
  const explicitSetting = [
    process.env.NEXT_PUBLIC_CODRUT_LOCAL_AUTH_BYPASS,
    process.env.CODRUT_LOCAL_AUTH_BYPASS,
  ].find((value): value is string => Boolean(value));
  if (process.env.NODE_ENV === "production") return false;
  return explicitSetting === "true" && localHosts.has(requestHostname(request));
}

function buildContentSecurityPolicy(nonce: string): string {
  const developmentScriptPolicy = process.env.NODE_ENV === "production" ? "" : " 'unsafe-eval'";
  const upgradeInsecureRequests = process.env.NODE_ENV === "production" ? " upgrade-insecure-requests;" : "";

  return [
    "default-src 'self';",
    `script-src 'self' 'nonce-${nonce}' ${THEME_PREPAINT_CSP_HASH} 'strict-dynamic'${developmentScriptPolicy};`,
    "style-src 'self' 'unsafe-inline';",
    "img-src 'self' blob: data: https:;",
    "font-src 'self' data:;",
    "connect-src 'self' ws: wss:;",
    "media-src 'self' blob: https:;",
    "frame-src 'self' https://www.youtube.com https://www.youtube-nocookie.com https://player.vimeo.com;",
    "object-src 'none';",
    "base-uri 'self';",
    "form-action 'self' mailto:;",
    "frame-ancestors 'none';",
    upgradeInsecureRequests,
  ]
    .filter(Boolean)
    .join(" ")
    .replace(/\s{2,}/g, " ")
    .trim();
}

function applyPageSecurityHeaders(response: NextResponse, contentSecurityPolicy: string): NextResponse {
  response.headers.set("Content-Security-Policy", contentSecurityPolicy);
  response.headers.set("Cross-Origin-Opener-Policy", "same-origin");
  response.headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "DENY");
  return response;
}

export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const nonce = btoa(crypto.randomUUID());
  const contentSecurityPolicy = buildContentSecurityPolicy(nonce);
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-codrut-pathname", pathname);
  requestHeaders.set("x-nonce", nonce);
  requestHeaders.set("Content-Security-Policy", contentSecurityPolicy);

  const isProtectedPath = protectedPrefixes.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
  if (!isProtectedPath || publicPaths.has(pathname)) {
    return applyPageSecurityHeaders(NextResponse.next({
      request: {
        headers: requestHeaders,
      },
    }), contentSecurityPolicy);
  }

  if (
    !request.cookies.has("codrut_session") &&
    !isDemoFallbackEnabled() &&
    !isLocalAuthBypassEnabled(request)
  ) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    loginUrl.search = "";
    return applyPageSecurityHeaders(NextResponse.redirect(loginUrl), contentSecurityPolicy);
  }

  return applyPageSecurityHeaders(NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  }), contentSecurityPolicy);
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|icons/|landing/).*)"],
};
