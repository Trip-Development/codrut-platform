import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getCompanyReportComparison: vi.fn(),
  getIcareAnswerReview: vi.fn(),
}));
const data = vi.hoisted(() => ({
  getProjectAssessmentCyclesData: vi.fn(),
  getProjectReportWorkspaceData: vi.fn(),
}));

vi.mock("@/api/companies", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/companies")>();
  return { ...original, ...api };
});
vi.mock("@/api/server-request", () => ({
  getServerApiRequestOptions: vi.fn(async () => ({ headers: { cookie: "session=test" } })),
}));
vi.mock("../project-data", () => data);
vi.mock("./CycleComparisonControls", () => ({
  CycleComparisonControls: () => <div>Control comparație</div>,
}));
vi.mock("./ReportPrintButton", () => ({ ReportPrintButton: () => null }));

import ProjectReportsPage from "./page";

const emptyAggregate = {
  boss_360_averages: [],
  boss_360_count: 0,
  completion_rate: 0,
  driver_averages: [],
  driver_count: 0,
  hierarchy_ambiguous: false,
  hierarchy_ambiguity_message: null,
  hierarchy_issues: [],
  lencioni_averages: [],
  lencioni_count: 0,
  pcm_base_distribution: [],
  pcm_phase_distribution: [],
  results: [],
  team_lenses: [],
  total_assigned: 0,
  total_completed: 0,
};

const richAggregate = {
  ...emptyAggregate,
  boss_360_averages: [{ id: "clarity", label: "Claritate", avg: 74 }],
  boss_360_count: 2,
  completion_rate: 67,
  driver_averages: [
    { id: "perfect", label: "Fii perfect", avg: 64 },
    { id: "strong", label: "Fii puternic", avg: 42 },
  ],
  driver_count: 2,
  hierarchy_issues: Array.from({ length: 5 }, (_, index) => ({
    code: `missing-${index}`,
    participant_id: index === 0 ? null : `participant-${index}`,
    message: `Relație nemapată ${index + 1}`,
  })),
  lencioni_averages: [
    {
      id: "trust",
      label: "Încredere",
      avg: 7.5,
      range_label: "Funcțional",
      interpretation: "Echipa folosește dialogul direct.",
    },
    { id: "commitment", label: "Angajament", avg: 6 },
  ],
  lencioni_count: 1,
  pcm_base_distribution: [
    { id: "thinker", label: "Gânditor", value: 2, color: null },
    { id: "persister", label: "Perseverent", value: 1, color: "#7c3aed" },
  ],
  pcm_phase_distribution: [{ id: "harmonizer", label: "Armonizator", value: 1, color: null }],
  total_assigned: 3,
  total_completed: 2,
};

describe("project report overview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    data.getProjectAssessmentCyclesData.mockResolvedValue({
      assessmentCycles: [
        { id: "cycle-1", name: "Evaluare inițială", sequence: 1 },
        { id: "cycle-2", name: "Reevaluare 1", sequence: 2 },
      ],
    });
    data.getProjectReportWorkspaceData.mockResolvedValue({
      aggregate: emptyAggregate,
      assignments: [],
      participants: [],
      project: { id: "project-1", company_id: "company-1" },
    });
    api.getIcareAnswerReview.mockResolvedValue({ rows: [] });
    api.getCompanyReportComparison.mockRejectedValue(new Error("comparison unavailable"));
  });

  afterEach(cleanup);

  it("keeps the selected-cycle report available when comparison loading fails", async () => {
    const ui = await ProjectReportsPage({
      params: Promise.resolve({ projectId: "project-1" }),
      searchParams: Promise.resolve({ cycle: "cycle-2", baseline: "cycle-1" }),
    });
    render(ui);

    expect(screen.getByText("Comparația nu s-a încărcat.")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Status răspunsuri" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Reîncearcă comparația." }).getAttribute("href")).toBe(
      "/trainer/projects/project-1/reports?cycle=cycle-2&baseline=cycle-1",
    );
  });

  it("renders a complete two-cycle report without hiding partial comparison data", async () => {
    const baseline = {
      ...richAggregate,
      boss_360_averages: [
        { id: "clarity", label: "Claritate", avg: 61 },
        { id: "support", label: "Sprijin", avg: 55 },
      ],
      driver_averages: [{ id: "perfect", label: "Fii perfect", avg: 51 }],
      lencioni_averages: [
        { id: "trust", label: "Încredere", avg: 5.5 },
        { id: "conflict", label: "Conflict", avg: 4 },
      ],
      pcm_base_distribution: [{ id: "thinker", label: "Gânditor", value: 1, color: null }],
      pcm_phase_distribution: [{ id: "rebel", label: "Rebel", value: 1, color: null }],
    };
    data.getProjectAssessmentCyclesData.mockResolvedValue({
      assessmentCycles: [
        { id: "cycle-2", name: "Reevaluare 1", sequence: 2 },
        { id: "cycle-1", name: "Evaluare inițială", sequence: 1 },
      ],
    });
    data.getProjectReportWorkspaceData.mockResolvedValue({
      aggregate: richAggregate,
      assignments: [
        {
          id: "assignment-1",
          questionnaire_key: "lencioni",
          status: "submitted",
          submitted_at: "2026-07-20T10:00:00Z",
          scored_at: null,
        },
        {
          id: "assignment-2",
          questionnaire_key: "boss_360",
          status: "custom-status",
          submitted_at: null,
          scored_at: "2026-07-21T10:00:00Z",
        },
      ],
      participants: [{ id: "participant-1" }, { id: "participant-2" }],
      project: { id: "project-1", company_id: "company-1" },
    });
    api.getIcareAnswerReview.mockResolvedValue({
      rows: [{
        assignment_id: "assignment-2",
        response_id: "response-1",
        submitted_at: "2026-07-21T10:00:00Z",
        respondent_profile_id: "participant-1",
        respondent_name: "Ana, Pop",
        target_profile_id: null,
        target_name: null,
        target_type: "person",
        section_id: "section-1",
        section_label: "Sprijin",
        measurement_id: "clarity",
        measurement_label: "Claritate",
        statement_id: "statement-1",
        statement_label: "Oferă feedback direct",
        answer_value: 4,
        answer_label: "Aproape întotdeauna",
        answer_description: "Comportamentul este observabil.",
      }],
    });
    api.getCompanyReportComparison.mockResolvedValue({
      baseline_cycle_id: "cycle-1",
      comparison_cycle_id: "cycle-2",
      baseline,
      comparison: richAggregate,
    });

    const ui = await ProjectReportsPage({
      params: Promise.resolve({ projectId: "project-1" }),
      searchParams: Promise.resolve({ cycle: "cycle-2", baseline: "cycle-1" }),
    });
    render(ui);

    expect(screen.getByText("Control comparație")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Evoluție PCM" })).toBeTruthy();
    expect(screen.getByText("Încă 1 diagnostice sunt disponibile în datele raportului.")).toBeTruthy();
    expect(screen.getByText("Comportamentul este observabil.")).toBeTruthy();
    expect(screen.getAllByText("În așteptare").length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /Export CSV/ }).getAttribute("href")).toContain("Ana%2C%20Pop");
    expect(api.getCompanyReportComparison).toHaveBeenCalledWith(
      "company-1",
      "project-1",
      "cycle-1",
      "cycle-2",
      { headers: { cookie: "session=test" } },
    );
  });

  it("blocks report rendering when the project hierarchy is ambiguous", async () => {
    data.getProjectAssessmentCyclesData.mockResolvedValue({ assessmentCycles: [] });
    data.getProjectReportWorkspaceData.mockResolvedValue({
      aggregate: {
        ...emptyAggregate,
        hierarchy_ambiguous: true,
        hierarchy_ambiguity_message: null,
      },
      assignments: [],
      participants: [],
      project: { id: "project-1", company_id: "company-1" },
    });

    const ui = await ProjectReportsPage({
      params: Promise.resolve({ projectId: "project-1" }),
      searchParams: Promise.resolve({ baseline: "missing", cycle: "missing" }),
    });
    render(ui);

    expect(screen.getByText("Structura echipelor are nume ambigue.")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Status răspunsuri" })).toBeNull();
    expect(api.getCompanyReportComparison).not.toHaveBeenCalled();
  });
});
