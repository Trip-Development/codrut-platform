import { NextResponse, type NextRequest } from "next/server";

import { THEME_PREPAINT_CSP_HASH } from "@/lib/theme-prepaint";

const protectedPrefixes = ["/participant", "/trainer"];
const publicPaths = new Set(["/trainer/login"]);
const localHosts = new Set(["localhost", "127.0.0.1", "::1"]);

function isDemoFallbackEnabled(request: NextRequest): boolean {
  const explicitSetting = [
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK,
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK,
  ].find((value): value is string => Boolean(value));
  return explicitSetting === "true" && localHosts.has(requestHostname(request));
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
  return explicitSetting === "true" && localHosts.has(requestHostname(request));
}

function buildContentSecurityPolicy(nonce: string, isLocalRequest: boolean): string {
  const developmentScriptPolicy = isLocalRequest ? " 'unsafe-eval'" : "";
  const upgradeInsecureRequests = isLocalRequest ? "" : " upgrade-insecure-requests;";

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

function applyPageSecurityHeaders(
  response: NextResponse,
  contentSecurityPolicy: string,
  isLocalRequest: boolean,
): NextResponse {
  response.headers.set("Content-Security-Policy", contentSecurityPolicy);
  response.headers.set("Cross-Origin-Opener-Policy", "same-origin");
  response.headers.set("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()");
  response.headers.set("Referrer-Policy", "strict-origin-when-cross-origin");
  if (!isLocalRequest) {
    response.headers.set("Strict-Transport-Security", "max-age=31536000; includeSubDomains");
  }
  response.headers.set("X-Content-Type-Options", "nosniff");
  response.headers.set("X-Frame-Options", "DENY");
  return response;
}

export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const isLocalRequest = localHosts.has(requestHostname(request));
  const nonce = btoa(crypto.randomUUID());
  const contentSecurityPolicy = buildContentSecurityPolicy(nonce, isLocalRequest);
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
    }), contentSecurityPolicy, isLocalRequest);
  }

  if (
    !request.cookies.has("codrut_session") &&
    !isDemoFallbackEnabled(request) &&
    !isLocalAuthBypassEnabled(request)
  ) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = pathname === "/trainer" || pathname.startsWith("/trainer/")
      ? "/trainer/login"
      : "/login";
    loginUrl.search = "";
    return applyPageSecurityHeaders(
      NextResponse.redirect(loginUrl),
      contentSecurityPolicy,
      isLocalRequest,
    );
  }

  return applyPageSecurityHeaders(NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  }), contentSecurityPolicy, isLocalRequest);
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|icons/|landing/).*)"],
};
