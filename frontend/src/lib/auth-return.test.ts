import { describe, expect, it } from "vitest";

import { safeTrainerReturnTo, trainerLoginHref } from "./auth-return";

describe("trainer auth return paths", () => {
  it("keeps internal trainer destinations and their query parameters", () => {
    expect(safeTrainerReturnTo("/trainer/projects/project-1?tab=results")).toBe(
      "/trainer/projects/project-1?tab=results",
    );
    expect(trainerLoginHref("/trainer/projects/project-1?tab=results")).toBe(
      "/trainer/login?returnTo=%2Ftrainer%2Fprojects%2Fproject-1%3Ftab%3Dresults",
    );
  });

  it.each([
    null,
    "",
    "/participant",
    "/trainer/login",
    "//example.com/trainer",
    "https://example.com/trainer",
    "javascript:alert(1)",
  ])("falls back to trainer home for unsafe destination %s", (value) => {
    expect(safeTrainerReturnTo(value)).toBe("/trainer");
    expect(trainerLoginHref(value)).toBe("/trainer/login");
  });
});
