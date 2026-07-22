import { afterEach, describe, expect, it, vi } from "vitest";
import { NextRequest } from "next/server";

import { THEME_PREPAINT_CSP_HASH } from "@/lib/theme-prepaint";
import { middleware } from "./middleware";

function requestFor(path: string, cookie?: string, origin = "http://localhost:3000") {
  return new NextRequest(`${origin}${path}`, {
    headers: cookie ? { cookie } : undefined,
  });
}

describe("middleware", () => {
  afterEach(() => {
    delete process.env.CODRUT_FRONTEND_DEMO_FALLBACK;
    delete process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK;
    delete process.env.CODRUT_LOCAL_AUTH_BYPASS;
    delete process.env.NEXT_PUBLIC_CODRUT_LOCAL_AUTH_BYPASS;
    delete process.env.CI;
    vi.unstubAllEnvs();
  });

  it("allows the trainer login route without a session", () => {
    const response = middleware(requestFor("/trainer/login"));

    expect(response.status).toBe(200);
    expect(response.headers.get("location")).toBeNull();
  });

  it("redirects protected localhost routes without an explicit demo mode", () => {
    const response = middleware(requestFor("/trainer"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/trainer/login");
  });

  it("redirects protected trainer routes without a session when demo fallback is explicitly disabled", () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";

    const response = middleware(requestFor("/trainer"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/trainer/login");
  });

  it("allows an explicit demo mode only on localhost", () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "true";

    const response = middleware(requestFor("/participant"));

    expect(response.status).toBe(200);
    expect(response.headers.get("location")).toBeNull();

    const remoteResponse = middleware(
      requestFor("/participant", undefined, "https://preview.example.com"),
    );
    expect(remoteResponse.status).toBe(307);
  });

  it("allows protected localhost routes with the local auth bypass in an optimized build", () => {
    vi.stubEnv("NODE_ENV", "production");
    process.env.CODRUT_LOCAL_AUTH_BYPASS = "true";

    const response = middleware(requestFor("/participant/results"));

    expect(response.status).toBe(200);
    expect(response.headers.get("location")).toBeNull();
  });

  it("does not allow the local auth bypass on a remote development host", () => {
    process.env.CODRUT_LOCAL_AUTH_BYPASS = "true";

    const response = middleware(requestFor("/trainer", undefined, "https://preview.example.com"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("https://preview.example.com/trainer/login");
  });

  it("honors an explicit server false when the public fallback env is empty", () => {
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "";
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";

    const response = middleware(requestFor("/trainer"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/trainer/login");
  });

  it("allows protected routes with a session cookie", () => {
    const response = middleware(requestFor("/trainer/email", "codrut_session=test-token"));

    expect(response.status).toBe(200);
    expect(response.headers.get("location")).toBeNull();
  });

  it("adds a nonce-based content security policy without inline script permission", () => {
    const response = middleware(requestFor("/login"));
    const policy = response.headers.get("content-security-policy") ?? "";

    expect(policy).toContain("script-src 'self' 'nonce-");
    expect(policy).toContain(THEME_PREPAINT_CSP_HASH);
    expect(policy).toContain("'strict-dynamic'");
    expect(policy).not.toContain("script-src 'self' 'unsafe-inline'");
    expect(response.headers.get("x-content-type-options")).toBe("nosniff");
  });

  it("adds HSTS only outside localhost", () => {
    expect(middleware(requestFor("/login")).headers.get("strict-transport-security")).toBeNull();

    const response = middleware(requestFor("/login", undefined, "https://app.example.com"));

    expect(response.headers.get("strict-transport-security")).toBe(
      "max-age=31536000; includeSubDomains",
    );
  });

});
