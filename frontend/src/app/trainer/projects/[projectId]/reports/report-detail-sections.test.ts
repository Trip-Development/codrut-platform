import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { CompanyAssignment, CompanyParticipant } from "@/api/companies";
import type { ScoringResultRecord } from "@/api/trainer";
import type { TeamLens } from "@/app/trainer/companies/[companyId]/reports/report-aggregation";
import {
  buildDriverIndividualResults,
  DriverDetailBreakdown,
  LencioniTeamBreakdown,
} from "./report-detail-sections";

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

describe("buildDriverIndividualResults", () => {
  it("orders individual drivers by score so attention items appear first", () => {
    const assignment: CompanyAssignment = {
      id: "assignment-1",
      company_id: "company-1",
      project_id: "project-1",
      respondent_profile_id: "participant-1",
      questionnaire_key: "distress_drivers",
      target_type: "self",
      target_person_id: null,
      target_team_id: null,
      status: "scored",
      submitted_at: "2026-07-15T08:00:00Z",
      scored_at: "2026-07-15T08:05:00Z",
    };
    const participant: CompanyParticipant = {
      id: "participant-1",
      full_name: "Ana Pop",
      email: "ana@example.test",
      reports_to_name: null,
      position: "Manager",
      location: "București",
      role_group: "leadership",
      pcm_profile: null,
      user_id: null,
    };
    const result: ScoringResultRecord = {
      id: "result-1",
      assignment_id: assignment.id,
      primary_result: "work_signal_a",
      scores: {
        work_signal_a: { score: 82, label: "Semnal A" },
        work_signal_b: { score: 42, label: "Semnal B" },
        work_signal_c: { score: 65, label: "Semnal C" },
        work_signal_d: { score: 21, label: "Semnal D" },
        work_signal_e: { score: 54, label: "Semnal E" },
      },
    };

    const [individual] = buildDriverIndividualResults(
      [assignment],
      new Map([[assignment.id, result]]),
      [participant],
    );

    expect(individual.scores.map((score) => score.avg)).toEqual([82, 65, 54, 42, 21]);
    expect(individual.scores[0].label).toBe("Semnal A");
    expect(individual.scores[0].interpretation).toBeNull();
    expect(individual.scores[4].interpretation).toBeNull();
  });

  it("excludes incomplete score payloads and supplies safe participant fallbacks", () => {
    const baseAssignment: CompanyAssignment = {
      id: "assignment-1",
      company_id: "company-1",
      project_id: "project-1",
      respondent_profile_id: "missing-participant",
      questionnaire_key: "distress_drivers_en",
      target_type: "person",
      target_person_id: "target-1",
      target_team_id: null,
      status: "submitted",
      submitted_at: null,
      scored_at: null,
    };
    const result: ScoringResultRecord = {
      id: "result-1",
      assignment_id: baseAssignment.id,
      primary_result: null,
      scores: {
        valid_string: "71.26",
        labelled: { score: 55, label: "  Claritate  ", interpretation: "  Semnal util  " },
        invalid_string: "not-a-number",
        missing_score: { label: "Fără scor" },
        empty_string: "",
        absent: null,
      },
    };

    const ignoredAssignments: CompanyAssignment[] = [
      { ...baseAssignment, id: "assigned", status: "assigned" },
      { ...baseAssignment, id: "other", questionnaire_key: "lencioni" },
      { ...baseAssignment, id: "no-result" },
    ];
    const [individual] = buildDriverIndividualResults(
      [baseAssignment, ...ignoredAssignments],
      new Map([[baseAssignment.id, result]]),
      [],
    );

    expect(individual).toMatchObject({
      participantName: "Participant necunoscut",
      participantEmail: "Email indisponibil",
      targetLabel: "Evaluare individuală",
      submittedAt: null,
    });
    expect(individual.scores).toEqual([
      expect.objectContaining({ id: "valid_string", label: "Valid String", avg: 71.3 }),
      expect.objectContaining({ id: "labelled", label: "Claritate", avg: 55, interpretation: "Semnal util" }),
    ]);
  });
});

describe("report detail sections", () => {
  it("renders Lencioni aggregates from the first scored response", () => {
    const { rerender } = render(LencioniTeamBreakdown({ teams: [], overviewHref: "/reports" }));
    expect(screen.getByText("Nu există încă rezultate Lencioni pe echipe.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Înapoi la sumar" }).getAttribute("href")).toBe("/reports");

    rerender(LencioniTeamBreakdown({
      overviewHref: "/reports",
      teams: [
        team({
          id: "single",
          name: "Echipa cu un răspuns",
          lencioniCount: 1,
          lencioniAverages: [
            { id: "trust-single", label: "Încredere individuală", avg: 6.8 },
          ],
        }),
        team({ id: "unscored", name: "Echipa Nescorată", lencioniCount: 3 }),
        team({
          id: "ready",
          name: "Echipa Pregătită",
          lencioniCount: 4,
          completionRate: 100,
          lencioniAverages: [
            { id: "trust", label: "Încredere", avg: 7.4, range_label: "Solid", interpretation: "Echipa colaborează." },
            { id: "conflict", label: "Conflict", avg: 5.2 },
          ],
        }),
      ],
    }));

    const singleResponseTeam = screen.getByText("Echipa cu un răspuns").closest("article");
    expect(singleResponseTeam).not.toBeNull();
    expect(within(singleResponseTeam as HTMLElement).getByText("6.8 / 0-10")).toBeTruthy();
    expect(screen.queryByText(/Prag de confidențialitate|Ascuns până există/)).toBeNull();
    expect(screen.getByText("Nu există încă rezultate scorate pentru echipă.")).toBeTruthy();
    const readyTeam = screen.getByText("Echipa Pregătită").closest("article");
    expect(readyTeam).not.toBeNull();
    expect(within(readyTeam as HTMLElement).getByText("Solid: Echipa colaborează.")).toBeTruthy();
    expect(within(readyTeam as HTMLElement).getByText("7.4 / 0-10")).toBeTruthy();
  });

  it("renders aggregate and individual driver states without exposing raw answers", () => {
    const { rerender } = render(DriverDetailBreakdown({ teams: [], individuals: [], overviewHref: "/reports" }));
    expect(screen.getByText("Nu există încă rezultate de driveri asociate echipelor proiectului.")).toBeTruthy();
    expect(screen.getByText("Nu există încă autoevaluări de driveri scorate.")).toBeTruthy();

    rerender(DriverDetailBreakdown({
      overviewHref: "/reports",
      teams: [
        team({
          id: "single",
          name: "Driver cu un răspuns",
          driverCount: 1,
          driverAverages: [
            { id: "single-pressure", label: "Presiune individuală", avg: 73 },
          ],
        }),
        team({
          id: "ready",
          name: "Driver disponibil",
          driverCount: 3,
          driverAverages: [
            { id: "pressure", label: "Presiune", avg: 68, range_label: "Ridicat", interpretation: "Necesită atenție." },
          ],
        }),
      ],
      individuals: [
        {
          assignmentId: "assignment-1",
          participantName: "Ana Pop",
          participantEmail: "ana@example.test",
          targetLabel: "Autoevaluare",
          submittedAt: null,
          scores: [
            { id: "pressure", label: "Presiune", avg: 68, interpretation: "Semnal aprobat.", range_label: "Ridicat" },
            { id: "pace", label: "Ritm", avg: 44, interpretation: null, range_label: null },
          ],
        },
      ],
    }));

    expect(screen.getByText("Ridicat: Necesită atenție.")).toBeTruthy();
    const singleResponseTeam = screen.getByText("Driver cu un răspuns").closest("article");
    expect(singleResponseTeam).not.toBeNull();
    expect(within(singleResponseTeam as HTMLElement).getByText("73%")).toBeTruthy();
    expect(screen.getByText("Ridicat: Semnal aprobat.")).toBeTruthy();
    expect(screen.getByText("Autoevaluare / Fără dată")).toBeTruthy();
    expect(screen.queryByText(/Agregatele cer|Ascuns până există/)).toBeNull();
  });
});
