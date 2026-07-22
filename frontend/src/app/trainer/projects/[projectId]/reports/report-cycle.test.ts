import { describe, expect, it, vi } from "vitest";

import { buildProjectReportQuery, loadOptionalComparison } from "./report-cycle";

describe("report cycle helpers", () => {
  it("builds a stable encoded query for cycle comparisons", () => {
    expect(buildProjectReportQuery({
      cycle: "cycle current",
      baseline: "cycle/initial",
      compare: "dimensions",
    })).toBe("?cycle=cycle+current&baseline=cycle%2Finitial&compare=dimensions");
    expect(buildProjectReportQuery({})).toBe("");
  });

  it("isolates an optional comparison failure from the current report", async () => {
    const load = vi.fn().mockRejectedValue(new Error("comparison unavailable"));

    await expect(loadOptionalComparison(load)).resolves.toEqual({
      comparison: null,
      failed: true,
    });
    expect(load).toHaveBeenCalledOnce();
  });

  it("returns an available comparison without changing it", async () => {
    const comparison = { baseline_cycle_id: "cycle-1" };

    await expect(loadOptionalComparison(() => Promise.resolve(comparison))).resolves.toEqual({
      comparison,
      failed: false,
    });
    await expect(loadOptionalComparison(null)).resolves.toEqual({
      comparison: null,
      failed: false,
    });
  });
});
