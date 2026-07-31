import { render, screen } from "@testing-library/react";
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
    icare_cohorts: [
      { cohort: "direct_team", response_count: 2, averages: [{ id: "clarity", label: "Claritate", avg: 4.2 }], score_unit: "grade_1_to_5", scale_min: 1, scale_max: 5, score_scale_compatible: true, unavailable_reason: null },
      { cohort: "leadership_peers", response_count: 2, averages: [{ id: "clarity", label: "Claritate", avg: 4 }], score_unit: "grade_1_to_5", scale_min: 1, scale_max: 5, score_scale_compatible: true, unavailable_reason: null },
      { cohort: "self", response_count: 1, averages: [{ id: "clarity", label: "Claritate", avg: 3.8 }], score_unit: "grade_1_to_5", scale_min: 1, scale_max: 5, score_scale_compatible: true, unavailable_reason: null },
    ],
    driver_count: 1,
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
    expect(screen.getByText("Cum te vede echipa ta")).toBeTruthy();
    expect(screen.getByText("Cum te văd colegii din leadership")).toBeTruthy();
    expect(screen.getByText("Cum te evaluezi")).toBeTruthy();
    expect(screen.getByText("4.2 din 5")).toBeTruthy();
    expect(screen.queryByText("01")).toBeNull();
    expect(pcm.closest("[data-slot='card']")).toBeTruthy();
    const feedback = screen.getByText("Lasă loc și pentru o variantă suficient de bună.");
    expect(feedback.closest("[data-tone]")?.getAttribute("data-tone")).toBe("danger");
    expect(
      screen.getByRole("link", { name: /Înapoi la rezultatele proiectului/ }).getAttribute("href"),
    ).toBe("/trainer/projects/project-1/reports?cycle=cycle-2");
  });
});
