import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const data = vi.hoisted(() => ({
  getProjectAssessmentCyclesData: vi.fn(),
  getProjectReportWorkspaceData: vi.fn(),
}));

vi.mock("@/api/server-request", () => ({
  getServerApiRequestOptions: vi.fn(async () => ({ headers: { cookie: "session=test" } })),
}));
vi.mock("../project-data", () => data);
vi.mock("./CycleComparisonControls", () => ({
  CycleComparisonControls: ({ cycleId }: { cycleId: string }) => (
    <div>Evaluare selectată: {cycleId}</div>
  ),
}));
vi.mock("./ReportPrintButton", () => ({ ReportPrintButton: () => null }));

import ProjectReportsPage from "./page";

const aggregate = {
  assessment_cycle_id: "cycle-2",
  total_assigned: 12,
  total_completed: 10,
  completion_rate: 83,
  lencioni_count: 3,
  driver_count: 3,
  boss_360_count: 5,
  pcm_base_count: 0,
  pcm_phase_count: 0,
  lencioni_averages: [{ id: "trust", label: "Încredere", avg: 7.2 }],
  driver_averages: [{ id: "perfect", label: "Fii perfect", avg: 64 }],
  boss_360_averages: [],
  icare_target_summaries: [],
  icare_cohorts: [
    { cohort: "direct_team", response_count: 2, averages: [{ id: "clarity", label: "Claritate", avg: 78 }] },
    { cohort: "leadership_peers", response_count: 1, averages: [{ id: "clarity", label: "Claritate", avg: 72 }] },
    { cohort: "self", response_count: 1, averages: [{ id: "clarity", label: "Claritate", avg: 68 }] },
  ],
  driver_rank_summary: {
    total_people: 3,
    first_rank: [{ id: "perfect", label: "Fii perfect", value: 2 }],
    second_rank: [{ id: "strong", label: "Fii puternic", value: 3 }],
    first_rank_tie_breaks: 1,
    second_rank_tie_breaks: 0,
  },
  leadership_members: [
    { participant_profile_id: "leader-1", full_name: "Ana Lider", position: "Director" },
  ],
  pcm_base_distribution: [],
  pcm_phase_distribution: [],
  team_lenses: [],
  hierarchy_ambiguous: false,
  hierarchy_ambiguity_message: null,
  hierarchy_issues: [],
  results: [],
};

describe("project report overview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    data.getProjectAssessmentCyclesData.mockResolvedValue({
      assessmentCycles: [
        { id: "cycle-1", name: "Evaluare inițială", sequence: 1 },
        { id: "cycle-2", name: "Reevaluare", sequence: 2 },
      ],
    });
    data.getProjectReportWorkspaceData.mockResolvedValue({
      aggregate,
      assignments: [],
      participants: [{ id: "participant-1" }],
      project: { id: "project-1", company_id: "company-1", name: "Proiect Atlas" },
    });
  });

  afterEach(cleanup);

  it("renders the exact aggregate order, three iCARE views, rank pies, and leadership-only drilldown", async () => {
    const ui = await ProjectReportsPage({
      params: Promise.resolve({ projectId: "project-1" }),
      searchParams: Promise.resolve({ cycle: "cycle-2", baseline: "cycle-1" }),
    });
    render(ui);

    const lencioni = screen.getByRole("heading", { name: "Lencioni" });
    const icare = screen.getByRole("heading", { name: "iCARE" });
    const drivers = screen.getByRole("heading", { name: "TA Drivers" });
    expect(lencioni.compareDocumentPosition(icare) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(icare.compareDocumentPosition(drivers) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Cum vede echipa leadershipul" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Cum se văd colegii din leadership" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Cum se evaluează liderii" })).toBeTruthy();
    expect(screen.getByRole("img", { name: "Primul driver dominant" })).toBeTruthy();
    expect(screen.getByRole("img", { name: "Al doilea driver dominant" })).toBeTruthy();
    expect(screen.getByText(/1 departajări pentru primul driver/)).toBeTruthy();
    expect(screen.getByText("Evaluare selectată: cycle-2")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Ana Lider/ }).getAttribute("href")).toBe(
      "/trainer/projects/project-1/reports/leadership/leader-1?cycle=cycle-2",
    );
    expect(screen.queryByText("Răspunsuri individuale iCARE")).toBeNull();
    expect(screen.queryByRole("link", { name: "Detalii" })).toBeNull();
  });

  it("blocks rendering when hierarchy names are ambiguous", async () => {
    data.getProjectAssessmentCyclesData.mockResolvedValue({ assessmentCycles: [] });
    data.getProjectReportWorkspaceData.mockResolvedValue({
      aggregate: {
        ...aggregate,
        hierarchy_ambiguous: true,
        hierarchy_ambiguity_message: null,
      },
      assignments: [],
      participants: [],
      project: { id: "project-1", company_id: "company-1", name: "Proiect Atlas" },
    });

    const ui = await ProjectReportsPage({
      params: Promise.resolve({ projectId: "project-1" }),
      searchParams: Promise.resolve({}),
    });
    render(ui);

    expect(screen.getByText("Structura echipelor are nume ambigue.")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "TA Drivers" })).toBeNull();
  });
});
