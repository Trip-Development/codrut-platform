import { cleanup, fireEvent, render, screen } from "@testing-library/react";
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
  reportable_scored_count: 10,
  reportable_pending_score_count: 0,
  reportable_failed_score_count: 0,
  reportable_orphaned_score_count: 0,
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
    { cohort: "direct_team", response_count: 2, averages: [{ id: "clarity", label: "Claritate", avg: 78 }], score_unit: "percent", scale_min: 0, scale_max: 100, score_scale_compatible: true, unavailable_reason: null },
    { cohort: "leadership_peers", response_count: 1, averages: [{ id: "clarity", label: "Claritate", avg: 72 }], score_unit: "percent", scale_min: 0, scale_max: 100, score_scale_compatible: true, unavailable_reason: null },
    { cohort: "self", response_count: 1, averages: [{ id: "clarity", label: "Claritate", avg: 68 }], score_unit: "percent", scale_min: 0, scale_max: 100, score_scale_compatible: true, unavailable_reason: null },
  ],
  driver_rank_summary: {
    total_people: 3,
    first_rank: [
      { id: "perfect", label: "Fii perfect", value: 2 },
      { id: "strong", label: "Fii puternic", value: 1 },
    ],
    second_rank: [{ id: "strong", label: "Fii puternic", value: 3 }],
    first_rank_tie_breaks: 1,
    second_rank_tie_breaks: 0,
    insufficient_driver_score_count: 0,
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
        { id: "cycle-1", name: "Evaluare inițială", sequence: 1, status: "closed" },
        { id: "cycle-2", name: "Reevaluare", sequence: 2, status: "active" },
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
    const peersTab = screen.getByRole("tab", { name: "Cum se văd colegii din leadership: 1 răspuns" });
    const selfTab = screen.getByRole("tab", { name: "Cum se evaluează liderii: 1 răspuns" });
    fireEvent.click(peersTab);
    expect(screen.getByRole("heading", { name: "Cum se văd colegii din leadership" })).toBeTruthy();
    fireEvent.click(selfTab);
    expect(screen.getByRole("heading", { name: "Cum se evaluează liderii" })).toBeTruthy();
    expect(screen.getByRole("img", { name: /Primul driver dominant.*3 persoane incluse/ })).toBeTruthy();
    expect(screen.getByRole("img", { name: /Al doilea driver dominant.*3 persoane incluse/ })).toBeTruthy();
    expect(screen.getByText("2 persoane · 67%")).toBeTruthy();
    expect(screen.getByText("3 persoane · 100%")).toBeTruthy();
    expect(screen.getByText(/o departajare pentru primul driver/)).toBeTruthy();
    expect(screen.getByText("Evaluare selectată: cycle-2")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Ana Lider/ }).getAttribute("href")).toBe(
      "/trainer/projects/project-1/reports/leadership/leader-1?cycle=cycle-2",
    );
    expect(screen.queryByText("Răspunsuri individuale iCARE")).toBeNull();
    expect(screen.queryByRole("link", { name: "Detalii" })).toBeNull();
    expect(screen.queryByText("01")).toBeNull();
    expect(screen.getByRole("heading", { name: "Rezultatul întregului proiect" }).closest("[data-slot='card']")).toBeTruthy();
  });

  it("keeps project-wide results visible and limits only hierarchy-dependent views", async () => {
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

    expect(screen.getByText("Rezultatele pe echipe sunt momentan indisponibile")).toBeTruthy();
    expect(screen.getByText("Perspectivele bazate pe organigramă sunt momentan indisponibile")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Rezultatul întregului proiect" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "TA Drivers" })).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Cum se evaluează liderii: 1 răspuns" }));
    expect(screen.getByRole("heading", { name: "Cum se evaluează liderii" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Vezi rezultatele pe echipe/ })).toBeNull();
  });

  it("renders iCARE grades on their declared scale", async () => {
    data.getProjectReportWorkspaceData.mockResolvedValue({
      aggregate: {
        ...aggregate,
        icare_cohorts: aggregate.icare_cohorts.map((summary) => ({
          ...summary,
          averages: [{ id: "clarity", label: "Claritate", avg: 4.2 }],
          score_unit: "grade_1_to_5",
          scale_min: 1,
          scale_max: 5,
        })),
      },
      assignments: [],
      participants: [],
      project: { id: "project-1", company_id: "company-1", name: "Proiect Atlas" },
    });

    const ui = await ProjectReportsPage({
      params: Promise.resolve({ projectId: "project-1" }),
      searchParams: Promise.resolve({ cycle: "cycle-2" }),
    });
    render(ui);

    expect(screen.getByRole("tabpanel").textContent).toContain("4.2 din 5");
    fireEvent.click(screen.getByRole("tab", { name: "Cum se văd colegii din leadership: 1 răspuns" }));
    expect(screen.getByRole("tabpanel").textContent).toContain("4.2 din 5");
    fireEvent.click(screen.getByRole("tab", { name: "Cum se evaluează liderii: 1 răspuns" }));
    expect(screen.getByRole("tabpanel").textContent).toContain("4.2 din 5");
    expect(screen.queryByText("4.2%")).toBeNull();
  });

  it("renders Lencioni and TA averages on their declared definition scales", async () => {
    data.getProjectReportWorkspaceData.mockResolvedValue({
      aggregate: {
        ...aggregate,
        lencioni_scale: { score_unit: "score", scale_min: 0, scale_max: 12 },
        driver_scale: { score_unit: "percent", scale_min: 0, scale_max: 80 },
      },
      assignments: [],
      participants: [],
      project: { id: "project-1", company_id: "company-1", name: "Proiect Atlas" },
    });

    const ui = await ProjectReportsPage({
      params: Promise.resolve({ projectId: "project-1" }),
      searchParams: Promise.resolve({ cycle: "cycle-2" }),
    });
    render(ui);

    expect(screen.getByText("7.2 / 12")).toBeTruthy();
    const driverValue = screen.getByText("64%");
    const driverBar = driverValue.parentElement?.nextElementSibling?.firstElementChild;
    expect(driverBar?.getAttribute("style")).toContain("width: 80%");
  });

  it("does not present mixed scale averages as missing results", async () => {
    data.getProjectReportWorkspaceData.mockResolvedValue({
      aggregate: {
        ...aggregate,
        lencioni_averages: [],
        lencioni_scale: {
          score_scale_compatible: false,
          unavailable_reason: "incompatible_score_scales",
        },
      },
      assignments: [],
      participants: [],
      project: { id: "project-1", company_id: "company-1", name: "Proiect Atlas" },
    });

    const ui = await ProjectReportsPage({
      params: Promise.resolve({ projectId: "project-1" }),
      searchParams: Promise.resolve({ cycle: "cycle-2" }),
    });
    render(ui);

    expect(screen.getByText(/Aceste rezultate folosesc scale diferite/)).toBeTruthy();
  });

  it("explains that a displayed zero is a valid minimum, not a missing result", async () => {
    data.getProjectReportWorkspaceData.mockResolvedValue({
      aggregate: {
        ...aggregate,
        icare_cohorts: aggregate.icare_cohorts.map((summary) => summary.cohort === "direct_team"
          ? { ...summary, averages: [{ id: "clarity", label: "Claritate", avg: 0 }] }
          : summary),
      },
      assignments: [],
      participants: [],
      project: { id: "project-1", company_id: "company-1", name: "Proiect Atlas" },
    });

    const ui = await ProjectReportsPage({
      params: Promise.resolve({ projectId: "project-1" }),
      searchParams: Promise.resolve({ cycle: "cycle-2" }),
    });
    render(ui);

    expect(screen.getByText("0%")).toBeTruthy();
    expect(screen.getByText("0% este scorul minim valid pe această scală, nu un rezultat lipsă.")).toBeTruthy();
  });

  it("explains pending scores without hiding available results", async () => {
    data.getProjectReportWorkspaceData.mockResolvedValue({
      aggregate: {
        ...aggregate,
        reportable_pending_score_count: 1,
        icare_cohorts: aggregate.icare_cohorts.map((summary) => summary.cohort === "direct_team"
          ? {
              ...summary,
              response_count: 0,
              averages: [],
              score_scale_compatible: false,
              unavailable_reason: "incompatible_score_scales",
            }
          : summary),
      },
      assignments: [],
      participants: [],
      project: { id: "project-1", company_id: "company-1", name: "Proiect Atlas" },
    });

    const ui = await ProjectReportsPage({
      params: Promise.resolve({ projectId: "project-1" }),
      searchParams: Promise.resolve({ cycle: "cycle-2" }),
    });
    render(ui);

    expect(screen.getByText("Unele rezultate sunt încă în curs de pregătire")).toBeTruthy();
    expect(screen.getByText(/Un răspuns trimis este încă în curs de procesare/)).toBeTruthy();
    expect(screen.getByText(/Aceste răspunsuri folosesc scale diferite/)).toBeTruthy();
    expect(screen.getByRole("heading", { name: "TA Drivers" })).toBeTruthy();
  });

  it("separates failed and unassociated results from work still processing", async () => {
    data.getProjectReportWorkspaceData.mockResolvedValue({
      aggregate: {
        ...aggregate,
        reportable_failed_score_count: 2,
        reportable_orphaned_score_count: 1,
      },
      assignments: [],
      participants: [],
      project: { id: "project-1", company_id: "company-1", name: "Proiect Atlas" },
    });

    const ui = await ProjectReportsPage({
      params: Promise.resolve({ projectId: "project-1" }),
      searchParams: Promise.resolve({ cycle: "cycle-2" }),
    });
    render(ui);

    expect(screen.getByText("Unele rezultate nu pot fi asociate cu evaluarea")).toBeTruthy();
    expect(screen.getByText(/2 răspunsuri sunt păstrate, dar rezultatele nu au putut fi pregătite/)).toBeTruthy();
    expect(screen.getByText(/Un răspuns trimis este păstrat, dar nu are încă un rezultat asociat/)).toBeTruthy();
    expect(screen.queryByText(/în curs de procesare/)).toBeNull();
  });

  it("defaults reports to the latest non-draft cycle", async () => {
    data.getProjectAssessmentCyclesData.mockResolvedValue({
      assessmentCycles: [
        { id: "cycle-1", name: "Evaluare inițială", sequence: 1, status: "closed" },
        { id: "cycle-2", name: "Reevaluare", sequence: 2, status: "active" },
        { id: "cycle-3", name: "Evaluare în pregătire", sequence: 3, status: "draft" },
      ],
    });

    const ui = await ProjectReportsPage({
      params: Promise.resolve({ projectId: "project-1" }),
      searchParams: Promise.resolve({}),
    });
    render(ui);

    expect(data.getProjectReportWorkspaceData).toHaveBeenCalledWith(
      "project-1",
      expect.anything(),
      { assessmentCycleId: "cycle-2" },
    );
    expect(screen.getByText("Evaluare selectată: cycle-2")).toBeTruthy();
    expect(screen.queryByText("Evaluare selectată: cycle-3")).toBeNull();
  });

  it("explains when a person has no completed TA result that can be ranked", async () => {
    data.getProjectReportWorkspaceData.mockResolvedValue({
      aggregate: {
        ...aggregate,
        driver_rank_summary: {
          ...aggregate.driver_rank_summary,
          insufficient_driver_score_count: 1,
        },
      },
      assignments: [],
      participants: [{ id: "participant-1" }],
      project: { id: "project-1", company_id: "company-1", name: "Proiect Atlas" },
    });

    const ui = await ProjectReportsPage({
      params: Promise.resolve({ projectId: "project-1" }),
      searchParams: Promise.resolve({ cycle: "cycle-2" }),
    });
    render(ui);

    expect(screen.getByText(/O persoană nu a putut fi inclusă/)).toBeTruthy();
    expect(screen.getByText(/nu are un rezultat TA finalizat cu suficiente scoruri/)).toBeTruthy();
  });

  it("uses honest chart copy when every finalized TA result is excluded", async () => {
    data.getProjectReportWorkspaceData.mockResolvedValue({
      aggregate: {
        ...aggregate,
        driver_count: 0,
        driver_averages: [],
        driver_rank_summary: {
          total_people: 0,
          first_rank: [],
          second_rank: [],
          first_rank_tie_breaks: 0,
          second_rank_tie_breaks: 0,
          insufficient_driver_score_count: 1,
        },
      },
      assignments: [],
      participants: [{ id: "participant-1" }],
      project: { id: "project-1", company_id: "company-1", name: "Proiect Atlas" },
    });

    const ui = await ProjectReportsPage({
      params: Promise.resolve({ projectId: "project-1" }),
      searchParams: Promise.resolve({ cycle: "cycle-2" }),
    });
    render(ui);

    expect(screen.getAllByText("Nu există rezultate TA care pot fi incluse în aceste grafice.")).toHaveLength(2);
    expect(screen.queryByText("Nu există încă rezultate TA finalizate pentru această evaluare.")).toBeNull();
    expect(screen.getByText(/O persoană nu a putut fi inclusă/)).toBeTruthy();
  });
});
