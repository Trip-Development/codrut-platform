import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cookies, headers } from "next/headers";

import { getServerApiRequestOptions } from "./server-request";

vi.mock("server-only", () => ({}));
vi.mock("next/headers", () => ({
  cookies: vi.fn(),
  headers: vi.fn(),
}));

function mockRequestContext(
  pathname: string,
  sessionCookie?: string,
  host = "localhost",
): void {
  vi.mocked(cookies).mockResolvedValue({
    get: vi.fn().mockReturnValue(
      sessionCookie ? { name: "codrut_session", value: sessionCookie } : undefined,
    ),
  } as never);
  vi.mocked(headers).mockResolvedValue(
    new Headers({ host, "x-codrut-pathname": pathname }) as never,
  );
}

describe("getServerApiRequestOptions", () => {
  beforeEach(() => {
    process.env.CODRUT_LOCAL_AUTH_BYPASS = "true";
  });

  afterEach(() => {
    delete process.env.CODRUT_LOCAL_AUTH_BYPASS;
    delete process.env.NEXT_PUBLIC_CODRUT_LOCAL_AUTH_BYPASS;
    vi.clearAllMocks();
    vi.unstubAllEnvs();
  });

  it("adds the participant role without requiring a session cookie", async () => {
    mockRequestContext("/participant/results");

    const options = await getServerApiRequestOptions();
    const requestHeaders = new Headers(options.headers);

    expect(requestHeaders.get("X-Codrut-Dev-Role")).toBe("participant");
    expect(requestHeaders.get("Cookie")).toBeNull();
  });

  it("uses an explicit participant role when the route header is unavailable", async () => {
    vi.mocked(cookies).mockResolvedValue({
      get: vi.fn().mockReturnValue(undefined),
    } as never);
    vi.mocked(headers).mockResolvedValue(new Headers({ host: "localhost" }) as never);

    const options = await getServerApiRequestOptions("participant");
    const requestHeaders = new Headers(options.headers);

    expect(requestHeaders.get("X-Codrut-Dev-Role")).toBe("participant");
  });

  it("lets the local trainer role override an existing participant cookie", async () => {
    mockRequestContext("/trainer/projects", "participant-session");

    const options = await getServerApiRequestOptions();
    const requestHeaders = new Headers(options.headers);

    expect(requestHeaders.get("X-Codrut-Dev-Role")).toBe("trainer");
    expect(requestHeaders.get("Cookie")).toBe("codrut_session=participant-session");
  });

  it("returns no auth headers when the bypass is disabled and no cookie exists", async () => {
    process.env.CODRUT_LOCAL_AUTH_BYPASS = "false";
    mockRequestContext("/participant");

    await expect(getServerApiRequestOptions("participant")).resolves.toEqual({});
  });

  it("does not add a local role on a remote development host", async () => {
    mockRequestContext("/trainer", undefined, "preview.example.com");

    await expect(getServerApiRequestOptions("trainer")).resolves.toEqual({});
  });
});
