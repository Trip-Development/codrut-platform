import { describe, expect, it } from "vitest";

import { getCurrentParticipant, getCurrentTrainer } from "./auth";
import { listEmailSurfaceStubs } from "./email";
import { getParticipantWorkspaceSummary } from "./participants";
import { listQuestionnaireDefinitionStubs } from "./questionnaires";
import { getTrainerDashboardSummary } from "./trainer";

describe("frontend API adapter stubs", () => {
  it("returns role-scoped local users", async () => {
    await expect(getCurrentTrainer()).resolves.toMatchObject({ role: "trainer" });
    await expect(getCurrentParticipant()).resolves.toMatchObject({ role: "participant" });
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
    await expect(listQuestionnaireDefinitionStubs()).resolves.toHaveLength(3);
    await expect(listEmailSurfaceStubs()).resolves.toHaveLength(3);
  });
});
