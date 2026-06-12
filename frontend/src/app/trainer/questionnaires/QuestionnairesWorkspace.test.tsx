import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
    title: "Chestionar de evaluare a echipei",
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
            {
              id: "q2",
              code: "Q2",
              type: "likert",
              label: "Second question",
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
        name: "Chestionar de evaluare a echipei",
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

  it("keeps typing local until the trainer explicitly saves", async () => {
    render(<QuestionnairesWorkspace />);

    const titleInput = await screen.findByDisplayValue("Chestionar de evaluare a echipei");

    fireEvent.change(titleInput, { target: { value: "L" } });
    fireEvent.change(titleInput, { target: { value: "Le" } });
    fireEvent.change(titleInput, { target: { value: "Leadership" } });

    expect(titleInput).toHaveProperty("value", "Leadership");
    expect(screen.getAllByText("Leadership").some((element) => element.tagName === "H3")).toBe(true);
    expect(screen.getByText("Modificări nesalvate")).toBeTruthy();
    expect(updateQuestionnaireDefinitionOnServer).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Salvează modificările" }));

    await waitFor(() => expect(updateQuestionnaireDefinitionOnServer).toHaveBeenCalledTimes(1));
    expect(updateQuestionnaireDefinitionOnServer).toHaveBeenCalledWith(
      "lencioni",
      expect.objectContaining({ title: "Leadership" }),
      1,
    );
    expect(await screen.findByText("Salvat")).toBeTruthy();
  });

  it("keeps nested question typing stable during a slow explicit save", async () => {
    let resolveSave: (definition: QuestionnaireDefinition) => void = () => {};
    vi.mocked(updateQuestionnaireDefinitionOnServer).mockImplementation(
      () =>
        new Promise<QuestionnaireDefinition>((resolve) => {
          resolveSave = resolve;
        }),
    );

    render(<QuestionnairesWorkspace />);

    const questionInput = await screen.findByDisplayValue("Initial question");

    fireEvent.change(questionInput, { target: { value: "P" } });
    fireEvent.change(questionInput, { target: { value: "Pr" } });
    fireEvent.change(questionInput, { target: { value: "Proces clar pentru echipă" } });

    expect(questionInput).toHaveProperty("value", "Proces clar pentru echipă");
    expect(screen.getByText("Modificări nesalvate")).toBeTruthy();
    expect(updateQuestionnaireDefinitionOnServer).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Salvează modificările" }));
    expect(screen.getAllByText("Se salvează...").length).toBeGreaterThanOrEqual(1);
    expect(questionInput).toHaveProperty("value", "Proces clar pentru echipă");

    await waitFor(() => expect(updateQuestionnaireDefinitionOnServer).toHaveBeenCalledTimes(1));
    expect(updateQuestionnaireDefinitionOnServer).toHaveBeenCalledWith(
      "lencioni",
      expect.objectContaining({
        schema: expect.objectContaining({
          sections: [
            expect.objectContaining({
              questions: [
                expect.objectContaining({ label: "Proces clar pentru echipă" }),
                expect.any(Object),
              ],
            }),
          ],
        }),
      }),
      1,
    );
    expect(questionInput).toHaveProperty("value", "Proces clar pentru echipă");
    resolveSave({
      ...fixtures.definition,
      schema: {
        ...fixtures.definition.schema,
        sections: [
          {
            ...fixtures.definition.schema.sections[0],
            questions: [
              {
                ...fixtures.definition.schema.sections[0].questions[0],
                label: "Proces clar pentru echipă",
              },
            ],
          },
        ],
      },
    });

    expect(await screen.findByText("Salvat")).not.toBeNull();
  });

  it("can discard local questionnaire edits without touching the server", async () => {
    render(<QuestionnairesWorkspace />);

    const descriptionInput = await screen.findByDisplayValue("Initial description");
    fireEvent.change(descriptionInput, { target: { value: "Draft description" } });

    expect(descriptionInput).toHaveProperty("value", "Draft description");
    fireEvent.click(screen.getByRole("button", { name: "Revino la ultima versiune salvată" }));

    expect(descriptionInput).toHaveProperty("value", "Initial description");
    expect(updateQuestionnaireDefinitionOnServer).not.toHaveBeenCalled();
  });

  it("edits a shared answer scale globally for matching questions", async () => {
    render(<QuestionnairesWorkspace />);

    const globalPanel = await screen.findByText("Scări globale de răspuns");
    const scaleCard = globalPanel.closest("section");
    expect(scaleCard).not.toBeNull();

    const labelInput = within(scaleCard as HTMLElement).getAllByDisplayValue("Rar")[0];
    fireEvent.change(labelInput, { target: { value: "Foarte rar" } });

    fireEvent.click(screen.getByRole("button", { name: "Salvează modificările" }));

    await waitFor(() => expect(updateQuestionnaireDefinitionOnServer).toHaveBeenCalledTimes(1));
    expect(updateQuestionnaireDefinitionOnServer).toHaveBeenCalledWith(
      "lencioni",
      expect.objectContaining({
        schema: expect.objectContaining({
          sections: [
            expect.objectContaining({
              questions: [
                expect.objectContaining({
                  scale: [
                    expect.objectContaining({ label: "Foarte rar" }),
                    expect.objectContaining({ label: "Des" }),
                  ],
                }),
                expect.objectContaining({
                  scale: [
                    expect.objectContaining({ label: "Foarte rar" }),
                    expect.objectContaining({ label: "Des" }),
                  ],
                }),
              ],
            }),
          ],
        }),
      }),
      1,
    );
  });
});
