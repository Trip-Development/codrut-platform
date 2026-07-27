import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  getAssignedQuestionnaireDefinition,
  getQuestionnaireResponse,
  QuestionnaireRequestError,
  type QuestionnaireDefinition,
} from "@/api/questionnaires";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import ParticipantQuestionnaireRunPage from "./page";

vi.mock("@/api/questionnaires", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api/questionnaires")>();
  return {
    ...actual,
    getAssignedQuestionnaireDefinition: vi.fn(),
    getQuestionnaireResponse: vi.fn(),
  };
});

vi.mock("@/api/server-request", () => ({
  getServerApiRequestOptions: vi.fn().mockResolvedValue({ headers: { cookie: "session=test" } }),
}));

vi.mock("@/api/participants", () => ({
  getParticipantWorkspaceSummary: vi.fn(),
}));

vi.mock("@/components/questionnaires/lazy-questionnaire-runner", () => ({
  LazyQuestionnaireRunner: ({
    assignmentId,
    returnHref,
    returnLabel,
    targetLabel,
    nextTaskHref,
  }: {
    assignmentId?: string;
    returnHref?: string;
    returnLabel?: string;
    targetLabel?: string;
    nextTaskHref?: string;
  }) => (
    <div
      data-testid="questionnaire-runner"
      data-assignment-id={assignmentId}
      data-return-href={returnHref}
      data-next-task-href={nextTaskHref}
    >
      <span>{returnLabel}</span>
      <span>{targetLabel}</span>
    </div>
  ),
}));

const definition = {
  key: "boss_360",
  version: 3,
  title: "Feedback iCARE",
  description: "",
  schema: {
    schema_version: "1.0",
    instructions: "",
    sections: [],
  },
} satisfies QuestionnaireDefinition;

describe("ParticipantQuestionnaireRunPage", () => {
  beforeEach(() => {
    vi.mocked(getAssignedQuestionnaireDefinition).mockResolvedValue(definition);
    vi.mocked(getQuestionnaireResponse).mockResolvedValue({
      id: "response-1",
      assignment_id: "assignment-1",
      questionnaire_key: "boss_360",
      questionnaire_version: 3,
      status: "draft",
      answers: { q1: 4 },
    });
    vi.mocked(getParticipantWorkspaceSummary).mockResolvedValue({
      participantFullName: "Participant Pilot",
      participantEmail: "participant@example.com",
      projectName: "Pilot",
      deadlineLabel: "31 iulie",
      tasks: [
        {
          id: "assignment-1",
          assignmentId: "assignment-1",
          title: "Feedback confidențial",
          status: "in_progress",
          detail: "",
          href: "/participant/questionnaires/boss_360?assignmentId=assignment-1",
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
          href: "/participant/questionnaires/boss_360?assignmentId=assignment-2",
          targetLabel: "Darius Neagu",
          estimatedMinutes: 10,
          questionnaireKey: "boss_360",
          projectId: "project-1",
          assignmentRoundId: "round-1",
        },
      ],
      results: [],
      receivedFeedback: null,
      receivedFeedbackGroups: [],
      cards: [],
      contexts: [],
      cycles: [],
      projects: [],
      contextSelectionRequired: false,
      companyName: "",
      emptyState: { title: "", description: "" },
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("opens the runner in focus mode with the target and autosaving Back destination intact", async () => {
    const ui = await ParticipantQuestionnaireRunPage({
      params: Promise.resolve({ key: "boss_360" }),
      searchParams: Promise.resolve({
        assignmentId: "assignment-1",
        returnTo: "/participant/questionnaires",
        target: "Bianca Pavel",
      }),
    });

    render(ui);

    const runner = screen.getByTestId("questionnaire-runner");
    expect(runner.getAttribute("data-assignment-id")).toBe("assignment-1");
    expect(runner.getAttribute("data-return-href")).toBe("/participant/questionnaires");
    expect(runner.getAttribute("data-next-task-href")).toContain(
      "assignmentId=assignment-2",
    );
    expect(screen.getByText("Înapoi la chestionare")).toBeDefined();
    expect(screen.getByText("Bianca Pavel")).toBeDefined();
    expect(screen.queryByLabelText("Navigare principală")).toBeNull();
    expect(getServerApiRequestOptions).toHaveBeenCalledWith("participant");
  });

  it("keeps a secure return path inside the invitation surface", async () => {
    const ui = await ParticipantQuestionnaireRunPage({
      params: Promise.resolve({ key: "boss_360" }),
      searchParams: Promise.resolve({
        assignmentId: "assignment-1",
        access: "secure",
        returnTo: "/invite/demo-token",
        target: "Bianca Pavel",
      }),
    });

    render(ui);

    expect(screen.getByTestId("questionnaire-runner").getAttribute("data-return-href")).toBe("/invite/demo-token");
    expect(screen.getByText("Înapoi la invitație")).toBeDefined();
    expect(screen.queryByText(/Nu ai nevoie de meniul complet/)).toBeNull();
  });

  it("explains an expired session and keeps recovery inside the safe return path", async () => {
    vi.mocked(getAssignedQuestionnaireDefinition).mockRejectedValue(
      new QuestionnaireRequestError("Sesiunea a expirat.", 401, "http_401"),
    );

    const ui = await ParticipantQuestionnaireRunPage({
      params: Promise.resolve({ key: "boss_360" }),
      searchParams: Promise.resolve({
        assignmentId: "assignment-1",
        returnTo: "/participant/questionnaires",
      }),
    });

    render(ui);

    expect(screen.getByText("Sesiunea trebuie reînnoită")).toBeDefined();
    expect(screen.getByRole("link", { name: "Înapoi la invitație" }).getAttribute("href")).toBe(
      "/participant/questionnaires",
    );
  });

  it("offers a retry without reporting a missing questionnaire on network failure", async () => {
    vi.mocked(getAssignedQuestionnaireDefinition).mockRejectedValue(
      new QuestionnaireRequestError("offline", 0, "network_error"),
    );

    const ui = await ParticipantQuestionnaireRunPage({
      params: Promise.resolve({ key: "boss_360" }),
      searchParams: Promise.resolve({
        assignmentId: "assignment-1",
        target: "Bianca Pavel",
      }),
    });

    render(ui);

    expect(screen.getByText("Chestionarul nu s-a încărcat")).toBeDefined();
    const retry = screen.getByRole("link", { name: "Încearcă din nou" });
    expect(retry.getAttribute("href")).toContain("assignmentId=assignment-1");
    expect(retry.getAttribute("href")).toContain("target=Bianca+Pavel");
  });
});
