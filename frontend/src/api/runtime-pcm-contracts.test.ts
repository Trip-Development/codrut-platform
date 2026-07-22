import { afterEach, describe, expect, it, vi } from "vitest";

import {
  formatPcmLabel,
  getPcmBadgeClassName,
  getPcmColor,
  getPcmProfile,
} from "./pcm";

describe("PCM presentation contracts", () => {
  it("normalizes Romanian, English, spaced, and underscored profile aliases", () => {
    expect(getPcmProfile(" GÂNDITOR ")).toMatchObject({ key: "thinker", label: "Gânditor" });
    expect(getPcmProfile("per_sister")).toMatchObject({ key: "persister", label: "Perseverent" });
    expect(getPcmProfile("architect")).toBeNull();
    expect(getPcmProfile("promoter")).toMatchObject({ key: "promoter", label: "Promotor" });
    expect(getPcmProfile(null)).toBeNull();
  });

  it("keeps unknown values readable while using safe visual fallbacks", () => {
    expect(formatPcmLabel()).toBe("Necompletată");
    expect(formatPcmLabel("custom_profile")).toBe("Custom Profile");
    expect(getPcmColor("thinker")).toBe("#2563eb");
    expect(getPcmColor("custom_profile")).toBeUndefined();
    expect(getPcmBadgeClassName("custom_profile")).toContain("bg-surface-muted");
    expect(getPcmBadgeClassName("harmonizer")).toContain("orange");
  });
});

describe("runtime safety contracts", () => {
  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("classifies role routes without treating trainer login as an authenticated workspace", async () => {
    const { localAuthRoleForPathname } = await import("./runtime");
    expect(localAuthRoleForPathname("/trainer")).toBe("trainer");
    expect(localAuthRoleForPathname("/trainer/projects")).toBe("trainer");
    expect(localAuthRoleForPathname("/trainer/login")).toBeNull();
    expect(localAuthRoleForPathname("/participant/results")).toBe("participant");
    expect(localAuthRoleForPathname("/login")).toBeNull();
  });

  it("requires an explicit bypass and a loopback host even in an optimized build", async () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("CODRUT_LOCAL_AUTH_BYPASS", "true");
    const { isLocalAuthBypassEnabled } = await import("./runtime");
    expect(isLocalAuthBypassEnabled("localhost:3000")).toBe(true);
    expect(isLocalAuthBypassEnabled("app.codrut.ro")).toBe(false);

    vi.stubEnv("NEXT_PUBLIC_CODRUT_LOCAL_AUTH_BYPASS", "false");
    vi.stubEnv("CODRUT_LOCAL_AUTH_BYPASS", "false");
    expect(isLocalAuthBypassEnabled("localhost")).toBe(false);
  });

  it("honors explicit fallback disablement and test-only defaults", async () => {
    const runtime = await import("./runtime");
    vi.stubEnv("CODRUT_FRONTEND_DEMO_FALLBACK", "false");
    expect(runtime.isDemoFallbackEnabled()).toBe(false);
    expect(runtime.isSeededDemoFallbackEnabled()).toBe(false);

    vi.stubEnv("CODRUT_FRONTEND_DEMO_FALLBACK", "");
    expect(runtime.isDemoFallbackEnabled()).toBe(true);
    expect(runtime.isLocalSeededDemoFallbackEnabled()).toBe(true);
  });
});
