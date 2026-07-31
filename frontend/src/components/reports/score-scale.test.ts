import { describe, expect, it } from "vitest";

import { reportScaleEmptyCopy, resolveReportScoreScale } from "./score-scale";

describe("trainer report score scales", () => {
  it("uses API bounds and readable suffixes", () => {
    expect(resolveReportScoreScale(
      { score_unit: "score", scale_min: 1, scale_max: 12 },
      { min: 0, max: 10, suffix: "" },
    )).toEqual({ min: 1, max: 12, suffix: " / 12", compatible: true });
    expect(resolveReportScoreScale(
      { score_unit: "percent", scale_min: 0, scale_max: 80 },
      { min: 0, max: 100, suffix: "%" },
    )).toEqual({ min: 0, max: 80, suffix: "%", compatible: true });
  });

  it("preserves legacy fallbacks and explains incompatible scales", () => {
    expect(resolveReportScoreScale(
      undefined,
      { min: 0, max: 10, suffix: "" },
    )).toEqual({ min: 0, max: 10, suffix: "", compatible: true });
    expect(reportScaleEmptyCopy(
      { score_scale_compatible: false, unavailable_reason: "incompatible_score_scales" },
      "Fallback",
    )).toContain("scale diferite");
  });
});
