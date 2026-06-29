import { NextResponse, type NextRequest } from "next/server";

const protectedPrefixes = ["/participant", "/trainer"];
const publicPaths = new Set(["/trainer/login"]);

function isDemoFallbackEnabled(request: NextRequest): boolean {
  const explicitSetting = [
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK,
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK,
  ].find((value): value is string => Boolean(value));
  if (explicitSetting === "false") return false;
  if (explicitSetting === "true") return true;

  if (process.env.CI === "true") return false;

  if (process.env.NODE_ENV === "development") return true;

  return ["localhost", "127.0.0.1", "::1"].includes(request.nextUrl.hostname);
}

export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-codrut-pathname", pathname);

  const isProtectedPath = protectedPrefixes.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
  if (!isProtectedPath || publicPaths.has(pathname)) {
    return NextResponse.next({
      request: {
        headers: requestHeaders,
      },
    });
  }

  if (!request.cookies.has("codrut_session") && !isDemoFallbackEnabled(request)) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    loginUrl.search = "";
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next({
    request: {
      headers: requestHeaders,
    },
  });
}

export const config = {
  matcher: ["/trainer/:path*", "/participant/:path*"],
};
