import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  audienceAccessNote,
  getCurrentParticipant,
  getCurrentTrainer,
  getParticipantSession,
  getTrainerSession,
} from "./auth";
import { listEmailSurfaceStubs } from "./email";
import { resolveInviteBundle } from "./invites";
import { getParticipantWorkspaceSummary } from "./participants";
import { createCompany, getCompanyList, importCompanyRoster, sendParticipantInvitations } from "./companies";
import {
  getQuestionnaireDefinition,
  listQuestionnaireDefinitionStubs,
  saveQuestionnaireResponse,
  submitQuestionnaireResponse,
} from "./questionnaires";
import { getTrainerDashboardSummary } from "./trainer";

describe("frontend API adapter stubs", () => {
  beforeEach(() => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "true";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "true";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.CODRUT_FRONTEND_DEMO_FALLBACK;
    delete process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK;
  });

  it("returns role-scoped local users", async () => {
    await expect(getCurrentTrainer()).resolves.toMatchObject({ role: "trainer" });
    await expect(getCurrentParticipant()).resolves.toMatchObject({ role: "participant" });
    await expect(getTrainerSession()).resolves.toMatchObject({ state: "fallback" });
    await expect(getParticipantSession()).resolves.toMatchObject({ state: "fallback" });
    expect(audienceAccessNote("invitee")).toContain("linkul securizat");
  });

  it("returns trainer dashboard placeholder data", async () => {
    const summary = await getTrainerDashboardSummary();

    expect(summary.stats).toHaveLength(4);
    expect(summary.cards.map((card) => card.title)).toContain("Email");
  });

  it("returns participant workspace placeholder data", async () => {
    const summary = await getParticipantWorkspaceSummary();

    expect(summary.cards).toHaveLength(3);
    expect(summary.emptyState.title).toContain("Fara");
  });

  it("keeps questionnaire and email surfaces explicit", async () => {
    const questionnaires = await listQuestionnaireDefinitionStubs();

    expect(questionnaires.map((definition) => definition.id)).toEqual(
      expect.arrayContaining(["icare", "boss_360", "pcm_baseline", "phase"]),
    );
    expect(questionnaires.find((definition) => definition.id === "boss_360")).toMatchObject({
      status: "active",
      estimatedItems: 5,
    });
    await expect(listEmailSurfaceStubs()).resolves.toHaveLength(3);
  });

  it("resolves invite bundle fallback states", async () => {
    await expect(resolveInviteBundle("demo-token")).resolves.toMatchObject({
      state: "valid",
      projectName: "Intake Iunie",
      participantEmail: "participant@companie.ro",
    });
    await expect(resolveInviteBundle("expired-demo")).resolves.toMatchObject({
      state: "expired",
    });
    await expect(resolveInviteBundle("missing")).resolves.toMatchObject({
      state: "not_found",
    });
  });

  it("uses seeded questionnaire response fallback for demo assignments", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    await expect(
      saveQuestionnaireResponse("11111111-1111-4111-8111-111111111111", { q1: 1 }),
    ).resolves.toMatchObject({
      status: "draft",
      questionnaire_key: "lencioni",
    });
    await expect(
      submitQuestionnaireResponse("11111111-1111-4111-8111-111111111111", { q1: 1 }),
    ).resolves.toMatchObject({
      status: "submitted",
      questionnaire_key: "lencioni",
    });

  });

  it("does not report seeded questionnaire saves as successful outside demo mode", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    await expect(
      saveQuestionnaireResponse("11111111-1111-4111-8111-111111111111", { q1: 1 }),
    ).rejects.toThrow("Nu am putut salva draftul.");
    await expect(
      submitQuestionnaireResponse("11111111-1111-4111-8111-111111111111", { q1: 1 }),
    ).rejects.toThrow("Nu am putut trimite raspunsurile.");
  });

  it("resolves the seeded boss 360 questionnaire as a runnable fallback", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    await expect(getQuestionnaireDefinition("boss_360")).resolves.toMatchObject({
      key: "boss_360",
      schema: {
        sections: [
          {
            questions: expect.arrayContaining([
              expect.objectContaining({ id: "boss_360_q01" }),
            ]),
          },
        ],
      },
    });

  });

  it("does not fall back to demo sessions when fallback is disabled", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    await expect(getTrainerSession()).rejects.toThrow("Trainer authentication required");
    await expect(getParticipantSession()).rejects.toThrow("Participant authentication required");
  });

  it("creates companies through the backend only", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ id: "company-1", name: "Test Company" }),
    } as Response);

    await expect(createCompany("Test Company")).resolves.toEqual({
      id: "company-1",
      name: "Test Company",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/companies"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({ name: "Test Company" }),
      }),
    );
  });

  it("keeps company list rendering when one company enrichment fails", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [{ id: "company-1", name: "Michelin" }],
      } as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 400,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      } as Response);

    await expect(getCompanyList()).resolves.toEqual([
      expect.objectContaining({
        id: "company-1",
        name: "Michelin",
        dataUnavailable: true,
      }),
    ]);
  });

  it("imports roster first and sends participant access through an explicit batch action", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          participants: [{ id: "participant-1", full_name: "Ana", email: "ana@example.com" }],
          email_results: [],
          total_imported: 1,
          emails_sent: 0,
          emails_failed: 0,
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          results: [
            {
              participant_id: "participant-1",
              full_name: "Ana",
              email: "ana@example.com",
              delivery_mode: "secure_links",
              email_sent: false,
              error: null,
              invite_url: "https://app.example.com/invite/token",
            },
          ],
          total: 1,
          emails_sent: 0,
          emails_failed: 0,
          links_generated: 1,
        }),
      } as Response);

    await expect(
      importCompanyRoster("company-1", [
        {
          Name: "Ana",
          "Reports To": "",
          Position: "Member",
          Location: "Bucharest",
          email: "ana@example.com",
          "Profil PCM": "",
        },
      ]),
    ).resolves.toMatchObject({ total_imported: 1, emails_sent: 0 });

    await expect(
      sendParticipantInvitations("company-1", {
        participantIds: ["participant-1"],
        mode: "secure_links",
      }),
    ).resolves.toMatchObject({ links_generated: 1 });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining("/companies/company-1/participants/roster"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: expect.stringContaining('"send_invites":false'),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining("/companies/company-1/participants/invitations"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({
          participant_ids: ["participant-1"],
          mode: "secure_links",
          force_rotate: false,
        }),
      }),
    );
  });

  it("lists only active questionnaire definitions", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => [
        {
          key: "boss_360",
          version: 1,
          title: "Boss / manager 360",
          description: "Feedback form",
          schema: {
            schema_version: "questionnaire.v1",
            audience: "participant",
            sections: [],
          },
        },
      ],
    } as Response);

    await expect(listQuestionnaireDefinitionStubs()).resolves.toEqual([
      expect.objectContaining({
        id: "boss_360",
        name: "Boss / manager 360",
        status: "active",
      }),
    ]);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/forms\/definitions$/),
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
      }),
    );
  });
});
