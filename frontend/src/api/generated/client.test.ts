import { afterEach, describe, expect, it, vi } from "vitest";

import { generatedApiFetch, generatedApiUrl } from "./client";

describe("generated API client facade", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("normalizes generated schema paths against the central runtime base URL", () => {
    expect(generatedApiUrl("/api/health/live")).toBe(
      "http://localhost:3000/api/health/live",
    );
    expect(generatedApiUrl("/api/companies")).toBe(
      "http://localhost:3000/api/companies",
    );
  });

  it("rejects non-absolute paths", () => {
    expect(() => generatedApiUrl("health/live" as never)).toThrow(
      "Generated API paths must start with '/'.",
    );
  });

  it("delegates fetch through the normalized generated URL", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("{}"));
    vi.stubGlobal("fetch", fetchMock);

    await generatedApiFetch("/api/health/live", { cache: "no-store" });

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:3000/api/health/live",
      { cache: "no-store" },
    );
  });
});
