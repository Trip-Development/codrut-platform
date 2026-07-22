import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getSecureQuestionnaireDefinition,
  getSecureQuestionnaireResponse,
  type QuestionnaireDefinition,
} from "@/api/questionnaires";
import SecureTaskRunnerPage from "./page";

vi.mock("@/api/questionnaires", () => ({
  getSecureQuestionnaireDefinition: vi.fn(),
  getSecureQuestionnaireResponse: vi.fn(),
}));

vi.mock("@/components/questionnaires/lazy-questionnaire-runner", () => ({
  LazyQuestionnaireRunner: ({
    assignmentId,
    returnHref,
    returnLabel,
    secureInviteToken,
    targetLabel,
  }: {
    assignmentId?: string;
    returnHref?: string;
    returnLabel?: string;
    secureInviteToken?: string;
    targetLabel?: string;
  }) => (
    <div
      data-testid="secure-questionnaire-runner"
      data-assignment-id={assignmentId}
      data-return-href={returnHref}
      data-secure-token={secureInviteToken}
    >
      <span>{returnLabel}</span>
      <span>{targetLabel}</span>
    </div>
  ),
}));

const definition = {
  key: "boss_360",
  version: 2,
  title: "Feedback iCARE",
  description: "",
  schema: {
    schema_version: "1.0",
    instructions: "",
    sections: [],
  },
} satisfies QuestionnaireDefinition;

describe("SecureTaskRunnerPage", () => {
  beforeEach(() => {
    vi.mocked(getSecureQuestionnaireDefinition).mockResolvedValue(definition);
    vi.mocked(getSecureQuestionnaireResponse).mockResolvedValue({
      id: "response-1",
      assignment_id: "assignment-1",
      questionnaire_key: "boss_360",
      questionnaire_version: 2,
      status: "draft",
      answers: { q1: 3 },
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("keeps secure persistence, target context, and the invite return path wired to the runner", async () => {
    const ui = await SecureTaskRunnerPage({
      params: Promise.resolve({ token: "invite-token", taskId: "assignment-1" }),
      searchParams: Promise.resolve({
        returnTo: "/invite/invite-token",
        target: "Bianca Pavel",
      }),
    });

    render(ui);

    const runner = screen.getByTestId("secure-questionnaire-runner");
    expect(runner.getAttribute("data-assignment-id")).toBe("assignment-1");
    expect(runner.getAttribute("data-secure-token")).toBe("invite-token");
    expect(runner.getAttribute("data-return-href")).toBe("/invite/invite-token");
    expect(screen.getByText("Înapoi la invitație")).toBeDefined();
    expect(screen.getByText("Bianca Pavel")).toBeDefined();
    expect(screen.queryByText("Chestionar securizat")).toBeNull();
  });

  it("rejects an external return path", async () => {
    const ui = await SecureTaskRunnerPage({
      params: Promise.resolve({ token: "invite-token", taskId: "assignment-1" }),
      searchParams: Promise.resolve({ returnTo: "https://example.com/steal" }),
    });

    render(ui);

    expect(screen.getByTestId("secure-questionnaire-runner").getAttribute("data-return-href")).toBe("/invite/invite-token");
  });
});
