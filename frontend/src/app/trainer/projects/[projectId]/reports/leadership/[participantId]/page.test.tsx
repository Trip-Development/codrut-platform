import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getCompanyProjectById: vi.fn(async () => ({
    id: "project-1",
    company_id: "company-1",
    name: "Proiect Atlas",
  })),
  getLeadershipMemberReport: vi.fn(async () => ({
    project_id: "project-1",
    assessment_cycle_id: "cycle-2",
    member: {
      participant_profile_id: "leader-1",
      full_name: "Ana Lider",
      position: "Director",
    },
    pcm_base: "thinker",
    pcm_phase: "persister",
    lencioni_count: 2,
    lencioni_averages: [{ id: "trust", label: "Încredere", avg: 7 }],
    lencioni_scale: { score_unit: "score", scale_min: 0, scale_max: 12 },
    icare_cohorts: [
      { cohort: "direct_team", response_count: 2, averages: [{ id: "clarity", label: "Claritate", avg: 4.2 }], score_unit: "grade_1_to_5", scale_min: 1, scale_max: 5, score_scale_compatible: true, unavailable_reason: null },
      { cohort: "leadership_peers", response_count: 2, averages: [{ id: "clarity", label: "Claritate", avg: 4 }], score_unit: "grade_1_to_5", scale_min: 1, scale_max: 5, score_scale_compatible: true, unavailable_reason: null },
      { cohort: "self", response_count: 1, averages: [{ id: "clarity", label: "Claritate", avg: 3.8 }], score_unit: "grade_1_to_5", scale_min: 1, scale_max: 5, score_scale_compatible: true, unavailable_reason: null },
    ],
    icare_unclassified_response_count: 0,
    icare_unclassified_reason: null as "historical_cohort_unavailable" | null,
    driver_count: 1,
    driver_scale: { score_unit: "percent", scale_min: 0, scale_max: 80 },
    driver_averages: [{
      id: "perfect",
      label: "Fii perfect",
      avg: 62,
      feedback: "Lasă loc și pentru o variantă suficient de bună.",
    }],
  })),
}));

vi.mock("@/api/companies", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/companies")>();
  return { ...original, ...api };
});
vi.mock("@/api/server-request", () => ({
  getServerApiRequestOptions: vi.fn(async () => ({ headers: { cookie: "session=test" } })),
}));

import LeadershipMemberReportPage from "./page";

describe("leadership member report", () => {
  it("keeps profile, Lencioni, iCARE, and TA in the approved order", async () => {
    const ui = await LeadershipMemberReportPage({
      params: Promise.resolve({ projectId: "project-1", participantId: "leader-1" }),
      searchParams: Promise.resolve({ cycle: "cycle-2", baseline: "cycle-1" }),
    });
    render(ui);

    expect(screen.getByRole("heading", { name: "Ana Lider" })).toBeTruthy();
    const pcm = screen.getByRole("heading", { name: "PCM" });
    const lencioni = screen.getByRole("heading", { name: "Lencioni" });
    const icare = screen.getByRole("heading", { name: "iCARE" });
    const drivers = screen.getByRole("heading", { name: "TA Drivers" });
    expect(pcm.compareDocumentPosition(lencioni) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(lencioni.compareDocumentPosition(icare) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(icare.compareDocumentPosition(drivers) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText("7 / 12")).toBeTruthy();
    expect(screen.getByText("62%")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Cum te vede echipa ta" })).toBeTruthy();
    expect(screen.getByText("4.2 din 5")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Cum te văd colegii din leadership: 2 răspunsuri" }));
    expect(screen.getByRole("heading", { name: "Cum te văd colegii din leadership" })).toBeTruthy();
    expect(screen.getByText("4 din 5")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "Cum te evaluezi: 1 răspuns" }));
    expect(screen.getByRole("heading", { name: "Cum te evaluezi" })).toBeTruthy();
    expect(screen.getByText("3.8 din 5")).toBeTruthy();
    expect(screen.queryByText("01")).toBeNull();
    expect(pcm.closest("[data-slot='card']")).toBeTruthy();
    const feedback = screen.getByText("Lasă loc și pentru o variantă suficient de bună.");
    expect(feedback.closest("[data-tone]")?.getAttribute("data-tone")).toBe("danger");
    expect(
      screen.getByRole("link", { name: /Înapoi la rezultatele proiectului/ }).getAttribute("href"),
    ).toBe("/trainer/projects/project-1/reports?cycle=cycle-2");
  });

  it("explains a valid minimum iCARE score on the individual report", async () => {
    const report = await api.getLeadershipMemberReport();
    api.getLeadershipMemberReport.mockResolvedValueOnce({
      ...report,
      icare_cohorts: report.icare_cohorts.map((summary) => summary.cohort === "direct_team"
        ? {
            ...summary,
            averages: [{ id: "clarity", label: "Claritate", avg: 0 }],
            score_unit: "percent",
            scale_min: 0,
            scale_max: 100,
          }
        : summary),
    });

    const ui = await LeadershipMemberReportPage({
      params: Promise.resolve({ projectId: "project-1", participantId: "leader-1" }),
      searchParams: Promise.resolve({ cycle: "cycle-2" }),
    });
    render(ui);

    expect(screen.getByText("0%")).toBeTruthy();
    expect(screen.getByText("0% este scorul minim valid pe această scală, nu un rezultat lipsă.")).toBeTruthy();
  });

  it("explains when a legacy cycle cannot identify the historical Lencioni team", async () => {
    const report = await api.getLeadershipMemberReport();
    api.getLeadershipMemberReport.mockResolvedValueOnce({
      ...report,
      lencioni_team_ambiguous: true,
      lencioni_team_ambiguity_message: "Echipa istorică are două rezultate posibile.",
    } as never);

    const ui = await LeadershipMemberReportPage({
      params: Promise.resolve({ projectId: "project-1", participantId: "leader-1" }),
      searchParams: Promise.resolve({ cycle: "cycle-2" }),
    });
    render(ui);

    expect(screen.getByText("Echipa istorică nu poate fi stabilită sigur")).toBeTruthy();
    expect(screen.getByText("Echipa istorică are două rezultate posibile.")).toBeTruthy();
    expect(screen.queryByText("7 din 10")).toBeNull();
  });

  it("keeps an unclassified historical response outside the member perspectives", async () => {
    const report = await api.getLeadershipMemberReport();
    api.getLeadershipMemberReport.mockResolvedValueOnce({
      ...report,
      icare_unclassified_response_count: 1,
      icare_unclassified_reason: "historical_cohort_unavailable",
    });

    const ui = await LeadershipMemberReportPage({
      params: Promise.resolve({ projectId: "project-1", participantId: "leader-1" }),
      searchParams: Promise.resolve({ cycle: "cycle-2" }),
    });
    render(ui);

    const notice = screen.getByRole("note", { name: "Despre răspunsurile iCARE mai vechi" });
    expect(notice.textContent).toContain("Un răspuns mai vechi");
    expect(notice.textContent).toContain("Îl păstrăm separat");
  });
});
