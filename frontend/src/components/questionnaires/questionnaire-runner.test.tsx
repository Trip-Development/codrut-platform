import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { describe, expect, it, vi, afterEach } from "vitest";

import type { QuestionnaireDefinition } from "../../api/questionnaires";
import {
  QuestionnaireRequestError,
  saveQuestionnaireResponse,
  submitQuestionnaireResponse,
} from "../../api/questionnaires";
import { QuestionnaireRunner } from "./questionnaire-runner";

const routerPush = vi.fn();
const originalConfirm = window.confirm;

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: routerPush,
  }),
}));

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
    vi.useRealTimers();
    window.confirm = originalConfirm;
  });

  it("keeps questionnaire details in a popup and renders questions/actions directly", () => {
    render(<QuestionnaireRunner definition={mockDefinition} assignmentId="test-assignment" />);

    expect(screen.queryByText("This is a test description")).toBeNull();
    expect(screen.queryByText("Please answer all questions.")).toBeNull();
    expect(screen.getByText("Question One Label")).toBeTruthy();
    expect(screen.getByText("Rar")).toBeTruthy();
    expect(screen.getByText("De obicei")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Detalii chestionar" }));

    expect(screen.getByRole("dialog", { name: "Detalii chestionar" })).toBeTruthy();
    expect(screen.getByText("This is a test description")).toBeTruthy();
    expect(screen.getByText("Please answer all questions.")).toBeTruthy();
  });

  it("hides internal statement codes from participant-facing statement sets", () => {
    const statementDefinition: QuestionnaireDefinition = {
      ...mockDefinition,
      schema: {
        ...mockDefinition.schema,
        sections: [
          {
            id: "icare",
            title: "iCARE",
            questions: [
              {
                id: "icare_01_dezvolta_oamenii",
                code: "ICARE-1",
                type: "statement_score_set",
                label: "Dezvoltă oamenii",
                required: true,
                scale: [
                  { value: 1, label: "1", description: "Niciodată." },
                  { value: 4, label: "4", description: "Aproape întotdeauna." },
                ],
                statements: [
                  {
                    id: "icare_01",
                    code: "S1",
                    label: "Oferă feedback constructiv",
                  },
                ],
              },
            ],
          },
        ],
      },
    };

    render(<QuestionnaireRunner definition={statementDefinition} assignmentId="icare-assignment" />);

    expect(screen.getByText("Oferă feedback constructiv")).toBeTruthy();
    expect(screen.queryByText("S1.")).toBeNull();
  });

  it("shows ICARE participants only the evaluated person and descriptive answers", () => {
    const icareDefinition: QuestionnaireDefinition = {
      ...mockDefinition,
      key: "boss_360",
      schema: {
        ...mockDefinition.schema,
        sections: [
          {
            id: "inspiring",
            title: "Inspiră (Inspiring)",
            questions: [
              {
                id: "icare_01_dezvolta_oamenii",
                code: "ICARE-1",
                type: "statement_score_set",
                label: "Dezvoltă oamenii",
                required: true,
                instructions: "Metadata for trainer review only.",
                scale: [
                  { value: 1, label: "1" },
                  { value: 2, label: "2" },
                  { value: 3, label: "3" },
                  { value: 4, label: "4" },
                ],
                statements: [
                  {
                    id: "icare_01",
                    code: "S1",
                    label: "Oferă feedback constructiv",
                    scale: [
                      { value: 1, label: "1", description: "Nu oferă feedback sau îl evită complet." },
                      { value: 2, label: "2", description: "Oferă feedback rar, doar când i se cere." },
                      { value: 3, label: "3", description: "Oferă feedback destul de des, dar vag." },
                      { value: 4, label: "4", description: "Oferă feedback regulat, cu exemple concrete." },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
    };

    render(
      <QuestionnaireRunner
        definition={icareDefinition}
        assignmentId="icare-assignment"
        targetLabel="Bianca Pavel"
      />,
    );

    expect(screen.getByText("Completezi pentru Bianca Pavel")).toBeTruthy();
    expect(screen.getByText("Nu oferă feedback sau îl evită complet.")).toBeTruthy();
    expect(screen.getByText("Oferă feedback regulat, cu exemple concrete.")).toBeTruthy();
    expect(screen.queryByText("Inspiră (Inspiring)")).toBeNull();
    expect(screen.queryByText("Dezvoltă oamenii")).toBeNull();
    expect(screen.queryByText("Oferă feedback constructiv")).toBeNull();
    expect(screen.queryByText("S1.")).toBeNull();
  });

  it("shows the 360 target prompt as a single Romanian line using only the safe display name", () => {
    render(
      <QuestionnaireRunner
        definition={{ ...mockDefinition, key: "boss_360" }}
        assignmentId="test-assignment"
        targetLabel="Bianca Pavel"
      />,
    );

    expect(screen.getByText("Completezi pentru Bianca Pavel")).toBeTruthy();
    expect(screen.queryByText("Evaluezi")).toBeNull();
    expect(screen.queryByText(/You are reviewing/i)).toBeNull();
    expect(screen.queryByText(/Completezi feedback/i)).toBeNull();
  });

  it("does not expose account-like 360 target labels", () => {
    render(
      <QuestionnaireRunner
        definition={{ ...mockDefinition, key: "boss_360" }}
        assignmentId="test-assignment"
        targetLabel="bianca.pavel@example.com"
      />,
    );

    expect(screen.queryByText(/bianca\.pavel@example\.com/i)).toBeNull();
    expect(screen.queryByText(/You are reviewing/i)).toBeNull();
  });

  it("triggers background auto-save and updates progress when answer is clicked", async () => {
    vi.useFakeTimers();
    render(<QuestionnaireRunner definition={mockDefinition} assignmentId="test-assignment" />);

    // Initially progress is 0%
    expect(screen.getByText("0% completat")).toBeTruthy();

    // Click on option "De obicei"
    const optionButton = screen.getByText("De obicei");
    fireEvent.click(optionButton);

    // Progress updates to 100%
    expect(screen.getByText("100% completat")).toBeTruthy();
    expect(saveQuestionnaireResponse).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(450);
    expect(saveQuestionnaireResponse).toHaveBeenCalledWith("test-assignment", {
      q1: 2,
    });
  });

  it("renders 1-10 scales as a discrete slider and saves the selected score", async () => {
    vi.useFakeTimers();
    const tenPointDefinition: QuestionnaireDefinition = {
      ...mockDefinition,
      schema: {
        ...mockDefinition.schema,
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
                scale: Array.from({ length: 10 }, (_, index) => ({
                  value: index + 1,
                  label: String(index + 1),
                })),
              },
            ],
          },
        ],
      },
    };

    render(<QuestionnaireRunner definition={tenPointDefinition} assignmentId="ten-point-assignment" />);

    const slider = screen.getByRole("slider", { name: "Question One Label" }) as HTMLInputElement;
    expect(slider.min).toBe("1");
    expect(slider.max).toBe("10");
    expect(slider.step).toBe("1");
    expect(slider.getAttribute("aria-valuetext")).toBe("1: Alege un scor de la 1 la 10.");
    expect(slider.getAttribute("aria-describedby")).toBeTruthy();
    expect(screen.getByText("Alege un scor de la 1 la 10.")).toBeTruthy();

    fireEvent.change(slider, { target: { value: "7" } });

    expect(screen.getByText("100% completat")).toBeTruthy();
    expect(screen.getByText("Scor selectat: 7")).toBeTruthy();
    expect(slider.getAttribute("aria-valuetext")).toBe("7: 7");

    await vi.advanceTimersByTimeAsync(450);
    expect(saveQuestionnaireResponse).toHaveBeenCalledWith("ten-point-assignment", {
      q1: 7,
    });
  });

  it("debounces auto-save and only sends the latest changed answer", async () => {
    vi.useFakeTimers();
    render(<QuestionnaireRunner definition={mockDefinition} assignmentId="test-assignment" />);

    fireEvent.click(screen.getByText("Rar"));
    fireEvent.click(screen.getByText("De obicei"));

    await vi.advanceTimersByTimeAsync(449);
    expect(saveQuestionnaireResponse).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(1);
    expect(saveQuestionnaireResponse).toHaveBeenCalledTimes(1);
    expect(saveQuestionnaireResponse).toHaveBeenCalledWith("test-assignment", {
      q1: 2,
    });
  });

  it("shows the concrete save error when auto-save fails", async () => {
    vi.useFakeTimers();
    vi.mocked(saveQuestionnaireResponse).mockRejectedValueOnce(new Error("Serverul nu a putut salva draftul."));
    render(<QuestionnaireRunner definition={mockDefinition} assignmentId="test-assignment" />);

    fireEvent.click(screen.getByText("Rar"));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(450);
    });

    expect(screen.getByText("Serverul nu a putut salva draftul.")).toBeTruthy();
  });

  it("merges rapid answers from different questions before the debounced save", async () => {
    vi.useFakeTimers();
    const twoQuestionDefinition: QuestionnaireDefinition = {
      ...mockDefinition,
      schema: {
        ...mockDefinition.schema,
        sections: [
          {
            id: "section_1",
            title: "Section One",
            questions: [
              ...mockDefinition.schema.sections[0].questions,
              {
                id: "q2",
                code: "Q2",
                type: "likert",
                label: "Question Two Label",
                required: true,
                scale: [
                  { value: 1, label: "Niciodată" },
                  { value: 2, label: "Des" },
                ],
              },
            ],
          },
        ],
      },
    };
    render(<QuestionnaireRunner definition={twoQuestionDefinition} assignmentId="test-assignment" />);

    fireEvent.click(screen.getByText("De obicei"));
    fireEvent.click(screen.getByText("Des"));

    await vi.advanceTimersByTimeAsync(450);

    expect(saveQuestionnaireResponse).toHaveBeenCalledTimes(1);
    expect(saveQuestionnaireResponse).toHaveBeenCalledWith("test-assignment", {
      q1: 2,
      q2: 2,
    });
  });

  it("saves a draft and exits to the questionnaire list", async () => {
    render(
      <QuestionnaireRunner
        definition={mockDefinition}
        assignmentId="test-assignment"
        initialAnswers={{ q1: 1 }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Salvează draft" }));

    await waitFor(() => {
      expect(screen.getByText("Draft salvat.")).toBeTruthy();
      expect(routerPush).toHaveBeenCalledWith("/participant/questionnaires");
    });
    expect(screen.getByRole("button", { name: "Trimite răspunsurile" })).toBeTruthy();
    expect(saveQuestionnaireResponse).toHaveBeenCalledWith("test-assignment", { q1: 1 });
  });

  it("submits completed answers and exits to the return destination", async () => {
    window.confirm = vi.fn(() => true);
    render(
      <QuestionnaireRunner
        definition={mockDefinition}
        assignmentId="test-assignment"
        initialAnswers={{ q1: 2 }}
        returnHref="/participant/questionnaires"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Trimite răspunsurile" }));

    await waitFor(() => {
      expect(submitQuestionnaireResponse).toHaveBeenCalledWith("test-assignment", { q1: 2 });
      expect(routerPush).toHaveBeenCalledWith("/participant/questionnaires");
    });
  });

  it("shows a stale-session message when another tab changes the active account", async () => {
    window.confirm = vi.fn(() => true);
    vi.mocked(submitQuestionnaireResponse).mockRejectedValueOnce(
      new QuestionnaireRequestError("Sesiunea activă nu este un cont de participant.", 403),
    );
    render(
      <QuestionnaireRunner
        definition={mockDefinition}
        assignmentId="test-assignment"
        initialAnswers={{ q1: 2 }}
        returnHref="/participant/questionnaires"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Trimite răspunsurile" }));

    await waitFor(() => {
      expect(screen.getByText(/Sesiunea activă s-a schimbat în altă filă/)).toBeTruthy();
    });
    expect(routerPush).not.toHaveBeenCalled();
  });

  it("locks a submitted assignment on direct revisit", () => {
    render(
      <QuestionnaireRunner
        definition={mockDefinition}
        assignmentId="test-assignment"
        initialAnswers={{ q1: 2 }}
        initialStatus="submitted"
        returnHref="/participant/questionnaires"
      />,
    );

    expect(screen.getByText("Răspunsurile au fost trimise")).toBeTruthy();
    expect(screen.queryByText("Question One Label")).toBeNull();
    expect(screen.getByRole("link", { name: "Înapoi la chestionare" }).getAttribute("href")).toBe(
      "/participant/questionnaires",
    );
    expect((screen.getByRole("button", { name: "Salvează draft" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Trimite răspunsurile" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("renders single-choice questions and saves string answers", async () => {
    vi.useFakeTimers();
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

    await vi.advanceTimersByTimeAsync(450);
    expect(saveQuestionnaireResponse).toHaveBeenCalledWith("pcm-assignment", {
      pcm_base: "thinker",
    });
  });
});
