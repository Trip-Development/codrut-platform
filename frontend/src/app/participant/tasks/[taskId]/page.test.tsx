import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  getQuestionnaireResponse,
  QuestionnaireRequestError,
} from "@/api/questionnaires";
import TaskRunnerPage from "./page";

const { redirect } = vi.hoisted(() => ({ redirect: vi.fn() }));

vi.mock("next/navigation", () => ({ redirect }));
vi.mock("@/api/server-request", () => ({
  getServerApiRequestOptions: vi.fn().mockResolvedValue({ headers: {} }),
}));
vi.mock("@/api/questionnaires", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/questionnaires")>();
  return { ...original, getQuestionnaireResponse: vi.fn() };
});

describe("TaskRunnerPage", () => {
  it("redirects a resolved legacy task to the canonical questionnaire route", async () => {
    vi.mocked(getQuestionnaireResponse).mockResolvedValue({
      id: "response-1",
      assignment_id: "assignment-1",
      questionnaire_key: "boss_360",
      questionnaire_version: 1,
      status: "draft",
      answers: {},
    });

    await TaskRunnerPage({
      params: Promise.resolve({ taskId: "assignment-1" }),
      searchParams: Promise.resolve({
        returnTo: "/participant/questionnaires?cycle=cycle-1",
        target: "Bianca Pavel",
      }),
    });

    expect(redirect).toHaveBeenCalledWith(
      "/participant/questionnaires/boss_360?assignmentId=assignment-1&returnTo=%2Fparticipant%2Fquestionnaires%3Fcycle%3Dcycle-1&target=Bianca+Pavel",
    );
  });

  it("offers a retry when a legacy task cannot be loaded", async () => {
    vi.mocked(getQuestionnaireResponse).mockRejectedValue(
      new QuestionnaireRequestError("Indisponibil", 503, "server_error"),
    );

    const ui = await TaskRunnerPage({
      params: Promise.resolve({ taskId: "assignment-1" }),
      searchParams: Promise.resolve({ target: "Bianca Pavel" }),
    });
    render(ui);

    expect(screen.getByText("Chestionarul nu s-a încărcat")).toBeDefined();
    expect(screen.getByRole("link", { name: "Încearcă din nou" }).getAttribute("href")).toBe(
      "/participant/tasks/assignment-1?target=Bianca+Pavel",
    );
  });
});
