import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  updateQuestionnaireDefinitionOnServer,
  type QuestionnaireDefinition,
} from "@/api/questionnaires";
import { QuestionnairesWorkspace } from "./QuestionnairesWorkspace";

const fixtures = vi.hoisted(() => ({
  definition: {
    key: "lencioni",
    version: 1,
    title: "Lencioni team assessment",
    description: "Initial description",
    schema: {
      schema_version: "questionnaire.v1",
      audience: "team",
      instructions: "Initial instructions",
      sections: [
        {
          id: "section_1",
          title: "Section one",
          questions: [
            {
              id: "q1",
              code: "Q1",
              type: "likert",
              label: "Initial question",
              required: true,
              scale: [
                { value: 1, label: "Rar" },
                { value: 2, label: "Des" },
              ],
            },
          ],
        },
      ],
    },
  } satisfies QuestionnaireDefinition,
}));

vi.mock("@/api/questionnaires", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/questionnaires")>();
  return {
    ...original,
    listQuestionnaireDefinitionStubs: vi.fn().mockResolvedValue([
      {
        id: "lencioni",
        name: "Lencioni team assessment",
        description: "Initial description",
        status: "active",
        version: 1,
        audience: "team",
        estimatedItems: 1,
      },
    ]),
    getQuestionnaireDefinition: vi.fn().mockResolvedValue(fixtures.definition),
    updateQuestionnaireDefinitionOnServer: vi.fn().mockResolvedValue(fixtures.definition),
  };
});

describe("QuestionnairesWorkspace", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("keeps typing local and debounces server saves", async () => {
    render(<QuestionnairesWorkspace />);

    const titleInput = await screen.findByDisplayValue("Lencioni team assessment");

    fireEvent.change(titleInput, { target: { value: "L" } });
    fireEvent.change(titleInput, { target: { value: "Le" } });
    fireEvent.change(titleInput, { target: { value: "Leadership" } });

    expect(titleInput).toHaveProperty("value", "Leadership");
    expect(screen.getAllByText("Leadership").some((element) => element.tagName === "H3")).toBe(true);
    expect(updateQuestionnaireDefinitionOnServer).not.toHaveBeenCalled();

    await waitFor(() => expect(updateQuestionnaireDefinitionOnServer).toHaveBeenCalledTimes(1));
    expect(updateQuestionnaireDefinitionOnServer).toHaveBeenCalledWith(
      "lencioni",
      expect.objectContaining({ title: "Leadership" }),
      1,
    );
  });

  it("keeps nested question typing local and saves the latest schema", async () => {
    render(<QuestionnairesWorkspace />);

    const questionInput = await screen.findByDisplayValue("Initial question");

    fireEvent.change(questionInput, { target: { value: "P" } });
    fireEvent.change(questionInput, { target: { value: "Pr" } });
    fireEvent.change(questionInput, { target: { value: "Proces clar pentru echipă" } });

    expect(questionInput).toHaveProperty("value", "Proces clar pentru echipă");
    expect(screen.queryByText("Se salvează...")).not.toBeNull();
    expect(updateQuestionnaireDefinitionOnServer).not.toHaveBeenCalled();

    await waitFor(() => expect(updateQuestionnaireDefinitionOnServer).toHaveBeenCalledTimes(1));
    expect(updateQuestionnaireDefinitionOnServer).toHaveBeenCalledWith(
      "lencioni",
      expect.objectContaining({
        schema: expect.objectContaining({
          sections: [
            expect.objectContaining({
              questions: [
                expect.objectContaining({
                  label: "Proces clar pentru echipă",
                }),
              ],
            }),
          ],
        }),
      }),
      1,
    );
    expect(await screen.findByText("Salvat")).not.toBeNull();
  });
});
