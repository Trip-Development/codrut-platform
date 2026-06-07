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
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    delete process.env.CODRUT_FRONTEND_DEMO_FALLBACK;
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
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    await expect(getTrainerSession()).rejects.toThrow("Trainer authentication required");
    await expect(getParticipantSession()).rejects.toThrow("Participant authentication required");
  });
});
