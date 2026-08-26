import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  getCompanyAssignments,
  getCompanyDetail,
  getCompanyProjectById,
  getCompanyReportAggregate,
  getParticipantAccountLinkStatus,
  getProjectParticipants,
} from "@/api/companies";
import TrainerParticipantReportPage from "./page";

vi.mock("@/api/server-request", () => ({
  getServerApiRequestOptions: vi.fn().mockResolvedValue({ headers: {} }),
}));

vi.mock("@/api/companies", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/companies")>();
  return {
    ...original,
    getCompanyProjectById: vi.fn(),
    getProjectParticipants: vi.fn(),
    getCompanyAssignments: vi.fn(),
    getCompanyDetail: vi.fn(),
    getCompanyReportAggregate: vi.fn(),
    getParticipantAccountLinkStatus: vi.fn(),
  };
});

describe("TrainerParticipantReportPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders 'Vezi ca participant' action button next to participant name with audit notice", async () => {
    vi.mocked(getCompanyProjectById).mockResolvedValue({
      id: "project-1",
      company_id: "company-1",
      company_name: "Michelin",
      name: "Leadership 2026",
      description: null,
      project_type: "leadership",
      status: "active",
      starts_at: null,
      due_at: null,
      form_opens_at: null,
      form_closes_at: null,
      created_at: "2026-06-01T00:00:00Z",
      updated_at: "2026-06-01T00:00:00Z",
    });

    vi.mocked(getProjectParticipants).mockResolvedValue([
      {
        id: "participant-1",
        full_name: "Elena Popescu",
        email: "elena@example.test",
        reports_to_name: null,
        position: "Director General",
        location: "București",
        role_group: "leadership",
        pcm_profile: "persister",
        user_id: null,
      },
    ]);

    vi.mocked(getCompanyAssignments).mockResolvedValue([]);
    vi.mocked(getCompanyDetail).mockResolvedValue(null);
    vi.mocked(getCompanyReportAggregate).mockResolvedValue({
      total_assigned: 0,
      total_completed: 0,
      reportable_scored_count: 0,
      reportable_pending_score_count: 0,
      reportable_failed_score_count: 0,
      reportable_orphaned_score_count: 0,
      completion_rate: 0,
      lencioni_count: 0,
      driver_count: 0,
      boss_360_count: 0,
      pcm_base_count: 0,
      pcm_phase_count: 0,
      lencioni_averages: [],
      driver_averages: [],
      boss_360_averages: [],
      icare_target_summaries: [],
      icare_cohorts: [],
      icare_unclassified_response_count: 0,
      icare_unclassified_reason: null,
      driver_rank_summary: {
        total_respondents: 0,
        ranked_drivers: [],
      },
      leadership_members: [],
      pcm_base_distribution: [],
      pcm_phase_distribution: [],
      team_lenses: [],
      hierarchy_ambiguous: false,
      hierarchy_ambiguity_message: null,
      hierarchy_issues: [],
      results: [],
    } as unknown as Awaited<ReturnType<typeof getCompanyReportAggregate>>);


    vi.mocked(getParticipantAccountLinkStatus).mockResolvedValue(null);

    const PageComponent = await TrainerParticipantReportPage({
      params: Promise.resolve({ projectId: "project-1", participantId: "participant-1" }),
    });

    render(PageComponent);

    expect(screen.getByRole("heading", { level: 2, name: "Elena Popescu" })).toBeTruthy();

    const previewButton = screen.getByRole("link", { name: /Vezi ca participant/i });
    expect(previewButton).toBeTruthy();
    expect(previewButton.getAttribute("href")).toBe(
      "/trainer/companies/company-1/participants/participant-1/preview?projectId=project-1",
    );
    expect(previewButton.getAttribute("title")).toBe(
      "Se deschide în mod citire și se înregistrează în jurnalul de acces",
    );
    expect(
      screen.getByText("Mod citire · Se înregistrează în jurnalul de acces"),
    ).toBeTruthy();
  });
});
