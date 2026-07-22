import { afterEach, describe, expect, it, vi } from "vitest";

import { apiFetch, ensureCsrfToken } from "./http";

function clearCookie(name: string): void {
  document.cookie = `${name}=; Max-Age=0; path=/`;
}

describe("apiFetch", () => {
  afterEach(() => {
    clearCookie("codrut_csrf");
    window.history.replaceState(null, "", "/");
    delete process.env.CODRUT_LOCAL_AUTH_BYPASS;
    delete process.env.NEXT_PUBLIC_CODRUT_LOCAL_AUTH_BYPASS;
    vi.unstubAllGlobals();
    vi.unstubAllEnvs();
  });

  it("does not attach CSRF headers to safe requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}"));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("http://localhost:3000/api/health/live", { cache: "no-store" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:3000/api/health/live",
      { cache: "no-store" },
    );
  });

  it.each([
    ["/trainer/companies", "trainer"],
    ["/participant/results", "participant"],
  ])("attaches the local route role for %s", async (pathname, expectedRole) => {
    process.env.CODRUT_LOCAL_AUTH_BYPASS = "true";
    window.history.replaceState(null, "", pathname);
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}"));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("http://localhost:3000/api/auth/me", { cache: "no-store" });

    const finalInit = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(finalInit.headers).get("X-Codrut-Dev-Role")).toBe(expectedRole);
  });

  it("keeps the local role header when attaching CSRF", async () => {
    process.env.CODRUT_LOCAL_AUTH_BYPASS = "true";
    window.history.replaceState(null, "", "/trainer/companies");
    document.cookie = "codrut_csrf=cookie-token; path=/";
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}"));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("http://localhost:3000/api/companies", { method: "POST" });

    const finalInit = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = new Headers(finalInit.headers);
    expect(headers.get("X-Codrut-Dev-Role")).toBe("trainer");
    expect(headers.get("X-CSRF-Token")).toBe("cookie-token");
  });

  it("does not bootstrap CSRF for deliberate public auth mutations", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}"));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("http://localhost:3000/api/auth/login", { method: "POST" });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:3000/api/auth/login",
      { method: "POST" },
    );
  });

  it("bootstraps CSRF tokens when requested by authenticated shells", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ csrf_token: "csrf-token" })));
    vi.stubGlobal("fetch", fetchMock);

    await expect(ensureCsrfToken()).resolves.toBe("csrf-token");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith("http://localhost:3000/api/auth/csrf", {
      cache: "no-store",
      credentials: "include",
    });
  });

  it("reuses an existing CSRF cookie before mutating", async () => {
    document.cookie = "codrut_csrf=cookie-token; path=/";
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}"));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("http://localhost:3000/api/forms/assignments/a1/response", {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
    });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const finalInit = fetchMock.mock.calls[0][1] as RequestInit;
    const headers = new Headers(finalInit.headers);
    expect(headers.get("X-CSRF-Token")).toBe("cookie-token");
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it("attaches CSRF headers to authenticated campaign recipient events", async () => {
    document.cookie = "codrut_csrf=cookie-token; path=/";
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}"));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("http://localhost:3000/api/communications/campaigns/recipients/r1/events", {
      method: "POST",
    });

    const finalInit = fetchMock.mock.calls[0][1] as RequestInit;
    expect(new Headers(finalInit.headers).get("X-CSRF-Token")).toBe("cookie-token");
  });

  it("refreshes the CSRF token and retries once after a CSRF failure", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ error: { code: "csrf_failed" } }), { status: 403 }),
      )
      .mockResolvedValueOnce(new Response(JSON.stringify({ csrf_token: "fresh-token" })))
      .mockResolvedValueOnce(new Response("{}"));
    vi.stubGlobal("fetch", fetchMock);

    const response = await apiFetch("http://localhost:3000/api/auth/logout", {
      method: "POST",
      credentials: "include",
    });

    expect(response.ok).toBe(true);
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[1][0]).toBe("http://localhost:3000/api/auth/csrf");
    expect(fetchMock.mock.calls[2][0]).toBe("http://localhost:3000/api/auth/logout");
    const retryInit = fetchMock.mock.calls[2][1] as RequestInit;
    expect(new Headers(retryInit.headers).get("X-CSRF-Token")).toBe("fresh-token");
  });
});
