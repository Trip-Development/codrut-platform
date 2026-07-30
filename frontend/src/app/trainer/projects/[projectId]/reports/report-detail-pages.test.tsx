import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const data = vi.hoisted(() => ({
  getProjectReportAggregateData: vi.fn(),
}));

vi.mock("@/api/server-request", () => ({
  getServerApiRequestOptions: vi.fn(async () => ({ headers: { cookie: "session=test" } })),
}));
vi.mock("@/app/trainer/companies/[companyId]/reports/report-aggregation", () => ({
  adaptReportTeamLenses: vi.fn(() => []),
}));
vi.mock("../project-data", () => data);
vi.mock("./report-detail-sections", () => ({
  LencioniTeamBreakdown: ({ overviewHref }: { overviewHref: string }) => (
    <div data-testid="lencioni-overview-href">{overviewHref}</div>
  ),
}));

import ProjectLencioniReportPage from "./lencioni/page";

const aggregate = {
  hierarchy_ambiguous: false,
  hierarchy_ambiguity_message: null,
  results: [],
  team_lenses: [],
};

describe("project report detail routes", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    data.getProjectReportAggregateData.mockResolvedValue({ aggregate });
  });

  afterEach(cleanup);

  it("scopes Lencioni data and preserves only the selected evaluation in Back", async () => {
    const ui = await ProjectLencioniReportPage({
      params: Promise.resolve({ projectId: "project-1" }),
      searchParams: Promise.resolve({ cycle: "cycle-2", baseline: "cycle-1" }),
    });
    render(ui);

    expect(data.getProjectReportAggregateData).toHaveBeenCalledWith(
      "project-1",
      { headers: { cookie: "session=test" } },
      { assessmentCycleId: "cycle-2" },
    );
    expect(screen.getByTestId("lencioni-overview-href").textContent).toBe(
      "/trainer/projects/project-1/reports?cycle=cycle-2",
    );
  });
});
