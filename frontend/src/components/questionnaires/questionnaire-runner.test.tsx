import { fireEvent, render, screen, cleanup } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi, afterEach } from "vitest";

import type { QuestionnaireDefinition } from "../../api/questionnaires";
import { saveQuestionnaireResponse } from "../../api/questionnaires";
import { QuestionnaireRunner } from "./questionnaire-runner";

// Mock the API client modules to verify auto-saving/submission calls
vi.mock("@/api/questionnaires", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/questionnaires")>();
  return {
    ...original,
    saveQuestionnaireResponse: vi.fn().mockResolvedValue({ status: "draft" }),
    submitQuestionnaireResponse: vi.fn().mockResolvedValue({ status: "submitted" }),
  };
});

const mockDefinition: QuestionnaireDefinition = {
  key: "test_q",
  version: 1,
  title: "Test Questionnaire",
  description: "This is a test description",
  schema: {
    schema_version: "questionnaire.v1",
    instructions: "Please answer all questions.",
    sections: [
      {
        id: "section_1",
        title: "Section One",
        questions: [
          {
            id: "q1",
            code: "Q1",
            type: "likert",
            label: "Question One Label",
            required: true,
            scale: [
              { value: 1, label: "Rar" },
              { value: 2, label: "De obicei" },
            ],
          },
        ],
      },
    ],
  },
};

describe("QuestionnaireRunner", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders questionnaire instructions, questions, and action buttons", () => {
    render(<QuestionnaireRunner definition={mockDefinition} assignmentId="test-assignment" />);

    expect(screen.getByText("This is a test description")).toBeTruthy();
    expect(screen.getByText("Please answer all questions.")).toBeTruthy();
    expect(screen.getByText("Question One Label")).toBeTruthy();
    expect(screen.getByText("Rar")).toBeTruthy();
    expect(screen.getByText("De obicei")).toBeTruthy();
  });

  it("triggers background auto-save and updates progress when answer is clicked", async () => {
    render(<QuestionnaireRunner definition={mockDefinition} assignmentId="test-assignment" />);

    // Initially progress is 0%
    expect(screen.getByText("0% completat")).toBeTruthy();

    // Click on option "De obicei"
    const optionButton = screen.getByText("De obicei");
    fireEvent.click(optionButton);

    // Progress updates to 100%
    expect(screen.getByText("100% completat")).toBeTruthy();

    // Verifies that auto-save API gets triggered in the background
    expect(saveQuestionnaireResponse).toHaveBeenCalledWith("test-assignment", {
      q1: 2,
    });
  });

  it("renders single-choice questions and saves string answers", async () => {
    const singleChoiceDefinition: QuestionnaireDefinition = {
      ...mockDefinition,
      schema: {
        ...mockDefinition.schema,
        sections: [
          {
            id: "pcm",
            title: "Profil PCM",
            questions: [
              {
                id: "pcm_base",
                code: "PCM-BASE",
                type: "single_choice",
                label: "Care este baza ta PCM?",
                required: true,
                scale: [
                  { value: "harmonizer", label: "Armonizator", description: "Orientat către relații." },
                  { value: "thinker", label: "Gânditor", description: "Orientat către structură." },
                ],
              },
            ],
          },
        ],
      },
    };

    render(<QuestionnaireRunner definition={singleChoiceDefinition} assignmentId="pcm-assignment" />);

    fireEvent.click(screen.getByRole("button", { name: /Gânditor/ }));

    expect(screen.getByText("100% completat")).toBeTruthy();
    expect(saveQuestionnaireResponse).toHaveBeenCalledWith("pcm-assignment", {
      pcm_base: "thinker",
    });
  });
});
