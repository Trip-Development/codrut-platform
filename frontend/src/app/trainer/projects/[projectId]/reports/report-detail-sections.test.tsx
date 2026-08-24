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
  it("renders teams with data and provides friendly navigation", () => {
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
            id: "scored-team",
            name: "Echipa Scilence",
            lencioniCount: 3,
            lencioniScale: { score_unit: "score", scale_min: 0, scale_max: 10 },
            lencioniAverages: [
              {
                id: "trust",
                label: "Încredere",
                avg: 8.5,
                range_label: "Solid",
                interpretation: "Echipa colaborează.",
              },
            ],
          }),
        ]}
      />,
    );

    const card = screen.getByText("Echipa Scilence").closest("article");
    expect(card).not.toBeNull();
    expect(within(card as HTMLElement).getByText("8.5 / 10")).toBeTruthy();
    expect(within(card as HTMLElement).getByText("Solid: Echipa colaborează.")).toBeTruthy();
  });

  it("renders teams with 0 responses without hiding them", () => {
    render(
      <LencioniTeamBreakdown
        overviewHref="/reports"
        teams={[
          team({
            id: "zero-responses",
            name: "Echipa Fără Răspunsuri",
            lencioniCount: 0,
            lencioniAverages: [],
            lencioniUnavailableReason: "no_responses",
            lencioniUnavailableMessage: "Nu există încă răspunsuri",
          }),
        ]}
      />,
    );

    expect(screen.getByText("Echipa Fără Răspunsuri")).toBeTruthy();
    expect(screen.getByText("Nu există încă răspunsuri")).toBeTruthy();
  });

  it("renders privacy threshold message when responses are below threshold", () => {
    render(
      <LencioniTeamBreakdown
        overviewHref="/reports"
        teams={[
          team({
            id: "single-response",
            name: "Echipa Cu Un Răspuns",
            lencioniCount: 1,
            lencioniAverages: [],
            lencioniUnavailableReason: "privacy_threshold",
            lencioniUnavailableMessage:
              "Rezultatele sunt ascunse deoarece numărul de evaluări (1) este sub pragul minim de confidențialitate (2).",
          }),
        ]}
      />,
    );

    expect(screen.getByText("Echipa Cu Un Răspuns")).toBeTruthy();
    expect(
      screen.getByText(
        "Rezultatele sunt ascunse deoarece numărul de evaluări (1) este sub pragul minim de confidențialitate (2).",
      ),
    ).toBeTruthy();
  });

  it("explains a team whose pinned scales cannot be combined", () => {
    render(
      <LencioniTeamBreakdown
        overviewHref="/reports"
        teams={[team({
          lencioniCount: 2,
          lencioniScale: {
            score_scale_compatible: false,
            unavailable_reason: "incompatible_score_scales",
          },
        })]}
      />,
    );

    expect(screen.getByText(/Aceste rezultate folosesc scale diferite/)).toBeTruthy();
  });

  it("displays team work and leadership work separately for functional teams", () => {
    render(
      <LencioniTeamBreakdown
        overviewHref="/reports"
        teams={[
          team({
            id: "manager-team-1",
            name: "Echipa Vânzări",
            teamType: "functional",
            memberCount: 5,
            assignedCount: 5,
            completedCount: 4,
            completionRate: 80,
            leaderAssignedCount: 4,
            leaderCompletedCount: 2,
            leaderCompletionRate: 50,
          }),
        ]}
      />,
    );

    expect(screen.getByText("Echipa Vânzări")).toBeTruthy();
    expect(screen.getByText("Muncă echipă:")).toBeTruthy();
    expect(screen.getByText(/4\/5 \(80%\)/)).toBeTruthy();
    expect(screen.getByText("Muncă conducere:")).toBeTruthy();
    expect(screen.getByText(/2\/4 \(50%\)/)).toBeTruthy();
  });

  it("displays single completion rate without separation for leadership team", () => {
    render(
      <LencioniTeamBreakdown
        overviewHref="/reports"
        teams={[
          team({
            id: "leadership",
            name: "Leadership",
            teamType: "leadership",
            memberCount: 4,
            assignedCount: 8,
            completedCount: 6,
            completionRate: 75,
            leaderAssignedCount: 4,
            leaderCompletedCount: 2,
            leaderCompletionRate: 50,
          }),
        ]}
      />,
    );

    expect(screen.getByText("Leadership")).toBeTruthy();
    expect(screen.getByText("75% completat")).toBeTruthy();
    expect(screen.queryByText("Muncă echipă:")).toBeNull();
    expect(screen.queryByText("Muncă conducere:")).toBeNull();
  });
});
