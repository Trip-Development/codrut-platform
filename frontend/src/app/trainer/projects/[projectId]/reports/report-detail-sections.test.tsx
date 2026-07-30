import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { TeamLens } from "@/app/trainer/companies/[companyId]/reports/report-aggregation";
import { LencioniTeamBreakdown } from "./report-detail-sections";

afterEach(cleanup);

function team(overrides: Partial<TeamLens> = {}): TeamLens {
  return {
    id: "team-1",
    name: "Echipa Nord",
    memberCount: 5,
    assignedCount: 5,
    completedCount: 4,
    completionRate: 80,
    lencioniCount: 0,
    driverCount: 0,
    boss360Count: 0,
    pcmBaseCount: 0,
    pcmPhaseCount: 0,
    lencioniAverages: [],
    driverAverages: [],
    boss360Averages: [],
    pcmBaseDistribution: [],
    pcmPhaseDistribution: [],
    ...overrides,
  };
}

describe("Lencioni team detail", () => {
  it("keeps a single trainer-visible response and friendly navigation", () => {
    const { rerender } = render(
      <LencioniTeamBreakdown teams={[]} overviewHref="/reports" />,
    );
    expect(screen.getByText("Nu există încă rezultate Lencioni pe echipe.")).toBeTruthy();
    expect(
      screen.getByRole("link", { name: "Înapoi la rezultatele proiectului" }).getAttribute("href"),
    ).toBe("/reports");

    rerender(
      <LencioniTeamBreakdown
        overviewHref="/reports"
        teams={[
          team({
            id: "single",
            name: "Echipa cu un răspuns",
            lencioniCount: 1,
            lencioniAverages: [
              {
                id: "trust",
                label: "Încredere",
                avg: 6.8,
                range_label: "Solid",
                interpretation: "Echipa colaborează.",
              },
            ],
          }),
        ]}
      />,
    );

    const card = screen.getByText("Echipa cu un răspuns").closest("article");
    expect(card).not.toBeNull();
    expect(within(card as HTMLElement).getByText("6.8 / 10")).toBeTruthy();
    expect(within(card as HTMLElement).getByText("Solid: Echipa colaborează.")).toBeTruthy();
    expect(screen.queryByText(/Prag de confidențialitate|Ascuns până există/)).toBeNull();
  });
});
