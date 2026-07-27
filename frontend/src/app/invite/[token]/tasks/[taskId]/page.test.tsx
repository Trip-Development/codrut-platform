import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getSecureQuestionnaireDefinition,
  getSecureQuestionnaireResponse,
  type QuestionnaireDefinition,
} from "@/api/questionnaires";
import { resolveInviteBundle } from "@/api/invites";
import { getServerApiRequestOptions } from "@/api/server-request";
import SecureTaskRunnerPage from "./page";

vi.mock("@/api/questionnaires", () => ({
  getSecureQuestionnaireDefinition: vi.fn(),
  getSecureQuestionnaireResponse: vi.fn(),
}));

vi.mock("@/api/invites", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/invites")>();
  return {
    ...actual,
    resolveInviteBundle: vi.fn(),
  };
});

vi.mock("@/api/server-request", () => ({
  getServerApiRequestOptions: vi.fn(),
}));

vi.mock("@/components/questionnaires/lazy-questionnaire-runner", () => ({
  LazyQuestionnaireRunner: ({
    assignmentId,
    returnHref,
    returnLabel,
    secureInviteToken,
    targetLabel,
    nextTaskHref,
  }: {
    assignmentId?: string;
    returnHref?: string;
    returnLabel?: string;
    secureInviteToken?: string;
    targetLabel?: string;
    nextTaskHref?: string;
  }) => (
    <div
      data-testid="secure-questionnaire-runner"
      data-assignment-id={assignmentId}
      data-return-href={returnHref}
      data-secure-token={secureInviteToken}
      data-next-task-href={nextTaskHref}
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
    vi.mocked(getServerApiRequestOptions).mockResolvedValue({
      headers: new Headers({ Cookie: "codrut_session=secure-session" }),
    });
    vi.mocked(getSecureQuestionnaireDefinition).mockResolvedValue(definition);
    vi.mocked(getSecureQuestionnaireResponse).mockResolvedValue({
      id: "response-1",
      assignment_id: "assignment-1",
      questionnaire_key: "boss_360",
      questionnaire_version: 2,
      status: "draft",
      answers: { q1: 3 },
    });
    vi.mocked(resolveInviteBundle).mockResolvedValue({
      state: "valid",
      token: "invite-token",
      projectName: "Pilot",
      participantEmail: "participant@example.com",
      participantFullName: "Participant Pilot",
      anonymousName: "SignalPilot",
      isLeadership: false,
      alreadyRegistered: false,
      deadlineLabel: "31 iulie",
      tasks: [
        {
          id: "assignment-1",
          assignmentId: "assignment-1",
          title: "Feedback confidențial",
          status: "in_progress",
          detail: "",
          href: "/participant/tasks/assignment-1?access=secure",
          targetLabel: "Bianca Pavel",
          estimatedMinutes: 10,
          questionnaireKey: "boss_360",
          projectId: "project-1",
          assignmentRoundId: "round-1",
        },
        {
          id: "assignment-2",
          assignmentId: "assignment-2",
          title: "Feedback confidențial",
          status: "not_started",
          detail: "",
          href: "/participant/tasks/assignment-2?access=secure",
          targetLabel: "Darius Neagu",
          estimatedMinutes: 10,
          questionnaireKey: "boss_360",
          projectId: "project-1",
          assignmentRoundId: "round-1",
        },
      ],
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
    expect(runner.getAttribute("data-next-task-href")).toContain(
      "/invite/invite-token/tasks/assignment-2",
    );
    expect(screen.getByText("Înapoi la invitație")).toBeDefined();
    expect(screen.getByText("Bianca Pavel")).toBeDefined();
    expect(screen.queryByText("Chestionar securizat")).toBeNull();
    expect(getServerApiRequestOptions).toHaveBeenCalledWith("participant");
    expect(getSecureQuestionnaireResponse).toHaveBeenCalledWith(
      "invite-token",
      "assignment-1",
      expect.objectContaining({ headers: expect.any(Headers) }),
    );
    expect(getSecureQuestionnaireDefinition).toHaveBeenCalledWith(
      "invite-token",
      "assignment-1",
      expect.objectContaining({ headers: expect.any(Headers) }),
    );
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
