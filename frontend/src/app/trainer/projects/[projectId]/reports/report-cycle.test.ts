import { describe, expect, it } from "vitest";

import { buildProjectReportQuery } from "./report-cycle";

describe("report cycle helpers", () => {
  it("builds a stable encoded query for the selected evaluation", () => {
    expect(buildProjectReportQuery({
      cycle: "cycle current",
    })).toBe("?cycle=cycle+current");
    expect(buildProjectReportQuery({})).toBe("");
  });
});
