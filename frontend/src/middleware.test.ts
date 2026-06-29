import { afterEach, describe, expect, it } from "vitest";
import { NextRequest } from "next/server";

import { middleware } from "./middleware";

function requestFor(path: string, cookie?: string) {
  return new NextRequest(`http://localhost:3000${path}`, {
    headers: cookie ? { cookie } : undefined,
  });
}

describe("middleware", () => {
  afterEach(() => {
    delete process.env.CODRUT_FRONTEND_DEMO_FALLBACK;
    delete process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK;
  });

  it("allows the trainer login route without a session", () => {
    const response = middleware(requestFor("/trainer/login"));

    expect(response.status).toBe(200);
    expect(response.headers.get("location")).toBeNull();
  });

  it("allows protected localhost routes without a session when demo fallback is automatic", () => {
    const response = middleware(requestFor("/trainer"));

    expect(response.status).toBe(200);
    expect(response.headers.get("location")).toBeNull();
  });

  it("redirects protected trainer routes without a session when demo fallback is explicitly disabled", () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";

    const response = middleware(requestFor("/trainer"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/login");
  });

  it("honors an explicit server false when the public fallback env is empty", () => {
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "";
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";

    const response = middleware(requestFor("/trainer"));

    expect(response.status).toBe(307);
    expect(response.headers.get("location")).toBe("http://localhost:3000/login");
  });

  it("allows protected routes with a session cookie", () => {
    const response = middleware(requestFor("/trainer/email", "codrut_session=test-token"));

    expect(response.status).toBe(200);
    expect(response.headers.get("location")).toBeNull();
  });
});
