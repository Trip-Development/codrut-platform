import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
const routerRefresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: routerPush,
    refresh: routerRefresh,
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
  });

  it("keeps questionnaire details in a popup and renders questions/actions directly", () => {
    render(<QuestionnaireRunner definition={mockDefinition} assignmentId="test-assignment" />);

    expect(screen.queryByText("This is a test description")).toBeNull();
    expect(screen.queryByText("Please answer all questions.")).toBeNull();
    expect(screen.queryByText("Versiunea 1")).toBeNull();
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
            id: "sample_feedback",
            title: "Feedback demonstrativ",
            questions: [
              {
                id: "feedback_signal_a",
                code: "SYN-F1",
                type: "statement_score_set",
                label: "Claritate",
                required: true,
                scale: [
                  { value: 1, label: "1", description: "Niciodată." },
                  { value: 4, label: "4", description: "Aproape întotdeauna." },
                ],
                statements: [
                  {
                    id: "sample_statement_a",
                    code: "S1",
                    label: "Clarifică rezultatul așteptat",
                  },
                ],
              },
            ],
          },
        ],
      },
    };

    render(<QuestionnaireRunner definition={statementDefinition} assignmentId="icare-assignment" />);

    expect(screen.getByText("Clarifică rezultatul așteptat")).toBeTruthy();
    expect(screen.queryByText("S1.")).toBeNull();
  });

  it("shows ICARE participants the behavior prompt and descriptive answers", () => {
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

    expect(screen.getByRole("heading", { name: /Completezi feedback pentru Bianca Pavel/i })).toBeTruthy();
    expect(screen.getByText("Nu oferă feedback sau îl evită complet.")).toBeTruthy();
    expect(screen.getByText("Oferă feedback regulat, cu exemple concrete.")).toBeTruthy();
    expect(screen.getByText("Dezvoltă oamenii")).toBeTruthy();
    expect(screen.getByText("Oferă feedback constructiv")).toBeTruthy();
    expect(screen.queryByText("Inspiră (Inspiring)")).toBeNull();
    expect(screen.queryByText("Metadata for trainer review only.")).toBeNull();
    expect(screen.queryByText("S1.")).toBeNull();
  });

  it("renders distress driver scales as horizontal native radio choices", () => {
    const distressDefinition: QuestionnaireDefinition = {
      ...mockDefinition,
      key: "distress_drivers",
      schema: {
        ...mockDefinition.schema,
        sections: [
          {
            id: "drivers",
            title: "Driveri",
            questions: [
              {
                id: "driver_set",
                code: "D1",
                type: "statement_score_set",
                label: "Ritmul de lucru",
                required: true,
                scale: [
                  { value: 1, label: "Deloc" },
                  { value: 2, label: "Uneori" },
                  { value: 3, label: "Des" },
                ],
                statements: [
                  { id: "driver_a", code: "D1-A", label: "Lucrez sub presiunea timpului" },
                ],
              },
            ],
          },
        ],
      },
    };

    render(<QuestionnaireRunner definition={distressDefinition} assignmentId="drivers-assignment" />);

    expect(screen.getByText("Driveri de distres")).toBeTruthy();
    expect(screen.getByRole("heading", {
      name: "Răspunde sincer și fără să te gândești prea mult.",
    })).toBeTruthy();
    expect(screen.getByText(
      "Nu există răspuns greșit sau corect. Citește, te rog, instrucțiunile de completare de mai jos.",
    )).toBeTruthy();
    const group = screen.getByRole("radiogroup", { name: "Lucrez sub presiunea timpului" });
    expect(within(group).getAllByRole("radio")).toHaveLength(3);
    expect(screen.getByText("Ritmul de lucru")).toBeTruthy();
    expect(within(group).getByText("1")).toBeTruthy();
  });

  it("shows the 360 target prompt as an editorial Romanian heading using only the safe display name", () => {
    render(
      <QuestionnaireRunner
        definition={{ ...mockDefinition, key: "boss_360" }}
        assignmentId="test-assignment"
        targetLabel="Bianca Pavel"
      />,
    );

    expect(screen.getByRole("heading", { name: /Completezi feedback pentru Bianca Pavel/i })).toBeTruthy();
    expect(screen.getByText("Feedback iCARE")).toBeTruthy();
    expect(screen.queryByText("Completezi pentru Bianca Pavel")).toBeNull();
    expect(screen.queryByText("Evaluezi")).toBeNull();
    expect(screen.queryByText(/You are reviewing/i)).toBeNull();
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

  it("uses participant-safe Lencioni team copy without exposing the internal team name", () => {
    render(
      <QuestionnaireRunner
        definition={{ ...mockDefinition, key: "lencioni" }}
        assignmentId="team-assignment"
        targetLabel="Echipa Echipa Vlad doi"
      />,
    );

    expect(screen.getByRole("heading", { name: "Răspunzi despre echipa ta" })).toBeTruthy();
    expect(screen.getByText("Feedback pentru echipă")).toBeTruthy();
    expect(screen.queryByText(/Vlad doi/i)).toBeNull();
  });

  it("triggers background auto-save and updates progress when answer is clicked", async () => {
    vi.useFakeTimers();
    render(<QuestionnaireRunner definition={mockDefinition} assignmentId="test-assignment" />);

    // Initially progress is 0%
    expect(screen.getByText("0% completat")).toBeTruthy();

    // Click on option "De obicei"
    const optionButton = screen.getByRole("radio", { name: "De obicei" });
    fireEvent.click(optionButton);

    // Progress updates to 100%
    expect(screen.getByText("100% completat")).toBeTruthy();
    expect(screen.getByRole("radiogroup", { name: "Question One Label" })).toBeTruthy();
    expect(optionButton.getAttribute("aria-checked")).toBe("true");
    expect(saveQuestionnaireResponse).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(450);
    expect(saveQuestionnaireResponse).toHaveBeenCalledWith("test-assignment", {
      q1: 2,
    });
  });

  it("flushes a pending draft with keepalive when the questionnaire unmounts", async () => {
    vi.useFakeTimers();
    const { unmount } = render(
      <QuestionnaireRunner definition={mockDefinition} assignmentId="test-assignment" />,
    );

    fireEvent.click(screen.getByRole("radio", { name: "De obicei" }));
    expect(saveQuestionnaireResponse).not.toHaveBeenCalled();

    unmount();

    expect(saveQuestionnaireResponse).toHaveBeenCalledWith(
      "test-assignment",
      { q1: 2 },
      { keepalive: true },
    );
  });

  it("warns before leaving only while a changed answer is unsaved", () => {
    render(<QuestionnaireRunner definition={mockDefinition} assignmentId="test-assignment" />);

    const cleanExit = new Event("beforeunload", { cancelable: true });
    expect(window.dispatchEvent(cleanExit)).toBe(true);

    fireEvent.click(screen.getByRole("radio", { name: "De obicei" }));
    const dirtyExit = new Event("beforeunload", { cancelable: true });
    expect(window.dispatchEvent(dirtyExit)).toBe(false);
  });

  it("allows submission when only optional questions are unanswered", () => {
    const definition: QuestionnaireDefinition = {
      ...mockDefinition,
      schema: {
        ...mockDefinition.schema,
        sections: [{
          ...mockDefinition.schema.sections[0],
          questions: [
            mockDefinition.schema.sections[0].questions[0],
            {
              id: "q2",
              code: "Q2",
              type: "likert",
              label: "Optional question",
              required: false,
              scale: [{ value: 1, label: "Da" }],
            },
          ],
        }],
      },
    };

    render(
      <QuestionnaireRunner
        definition={definition}
        assignmentId="test-assignment"
        initialAnswers={{ q1: 1 }}
      />,
    );

    expect(screen.getByText("100% completat")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Trimite răspunsurile" }) as HTMLButtonElement).disabled).toBe(false);
  });

  it("communicates autosave through the submit control without locking answers", async () => {
    vi.useFakeTimers();
    let resolveSave!: () => void;
    const savePromise = new Promise<Awaited<ReturnType<typeof saveQuestionnaireResponse>>>((resolve) => {
      resolveSave = () => resolve({ status: "draft" } as Awaited<ReturnType<typeof saveQuestionnaireResponse>>);
    });
    vi.mocked(saveQuestionnaireResponse).mockReturnValueOnce(savePromise);

    render(<QuestionnaireRunner definition={mockDefinition} assignmentId="test-assignment" />);

    const optionButton = screen.getByRole("radio", { name: "De obicei" }) as HTMLButtonElement;
    fireEvent.click(optionButton);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(450);
    });

    expect(screen.getByText("Se salvează…")).toBeTruthy();
    expect((screen.getByRole("button", { name: "Se salvează" }) as HTMLButtonElement).disabled).toBe(true);
    expect(optionButton.disabled).toBe(false);

    await act(async () => {
      resolveSave();
      await savePromise;
    });

    expect(screen.queryByText("Draft salvat.")).toBeNull();
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

    const slider = screen.getByRole("slider", { name: "Question One Label" });
    expect(slider.getAttribute("aria-valuemin")).toBe("1");
    expect(slider.getAttribute("aria-valuemax")).toBe("10");
    expect(slider.getAttribute("aria-valuenow")).toBe("5");
    expect(slider.getAttribute("aria-valuetext")).toBe("Neselectat. Alege un scor de la 1 la 10.");
    expect(slider.getAttribute("aria-describedby")).toBeTruthy();
    expect(screen.getByText("Alege un scor de la 1 la 10. Cursorul este poziționat neutru până selectezi.")).toBeTruthy();

    slider.focus();
    fireEvent.keyDown(slider, { key: "ArrowRight" });
    fireEvent.keyDown(slider, { key: "ArrowRight" });

    expect(screen.getByText("100% completat")).toBeTruthy();
    expect(screen.getByText("Scor selectat: 7/10")).toBeTruthy();
    expect(slider.getAttribute("aria-valuenow")).toBe("7");
    expect(slider.getAttribute("aria-valuetext")).toBe("7 din 10");

    await vi.advanceTimersByTimeAsync(450);
    expect(saveQuestionnaireResponse).toHaveBeenCalledWith("ten-point-assignment", {
      q1: 7,
    });
  });

  it("renders 1-10 distress statement scales without a horizontally scrolling choice row", () => {
    const distressDefinition: QuestionnaireDefinition = {
      ...mockDefinition,
      key: "distress_drivers",
      schema: {
        ...mockDefinition.schema,
        sections: [
          {
            id: "drivers",
            title: "Driveri",
            questions: [
              {
                id: "driver_set",
                code: "D1",
                type: "statement_score_set",
                label: "Ritmul de lucru",
                required: true,
                scale: Array.from({ length: 10 }, (_, index) => ({
                  value: index + 1,
                  label: String(index + 1),
                })),
                statements: [
                  { id: "driver_a", code: "D1-A", label: "Lucrez sub presiunea timpului" },
                ],
              },
            ],
          },
        ],
      },
    };

    render(<QuestionnaireRunner definition={distressDefinition} assignmentId="drivers-assignment" />);

    const slider = screen.getByRole("slider", { name: "Lucrez sub presiunea timpului" });
    expect(slider.getAttribute("aria-valuemin")).toBe("1");
    expect(slider.getAttribute("aria-valuemax")).toBe("10");
    expect(screen.queryByRole("radiogroup", { name: "Lucrez sub presiunea timpului" })).toBeNull();
  });

  it("renders the original 0-10 TA scale as a centered snapping slider", async () => {
    vi.useFakeTimers();
    const distressDefinition: QuestionnaireDefinition = {
      ...mockDefinition,
      key: "distress_drivers",
      schema: {
        ...mockDefinition.schema,
        sections: [{
          id: "drivers",
          title: "Driveri",
          questions: [{
            id: "driver_set",
            code: "D1",
            type: "statement_score_set",
            label: "Ritmul de lucru",
            required: true,
            scale: Array.from({ length: 11 }, (_, value) => ({
              value,
              label: String(value),
            })),
            statements: [
              { id: "driver_a", code: "D1-A", label: "Lucrez sub presiunea timpului" },
            ],
          }],
        }],
      },
    };

    render(<QuestionnaireRunner definition={distressDefinition} assignmentId="drivers-assignment" />);

    const slider = screen.getByRole("slider", { name: "Lucrez sub presiunea timpului" });
    expect(slider.getAttribute("aria-valuemin")).toBe("0");
    expect(slider.getAttribute("aria-valuemax")).toBe("10");
    expect(slider.getAttribute("aria-valuenow")).toBe("5");
    expect(screen.queryByRole("radiogroup", { name: "Lucrez sub presiunea timpului" })).toBeNull();
    expect(screen.getByText("Cel mai puțin adevărat")).toBeTruthy();
    expect(screen.getByText("Mijloc")).toBeTruthy();
    expect(screen.getByText("Cel mai adevărat")).toBeTruthy();

    const responseGroup = slider.closest("[data-testid='question-response-group']");
    expect(responseGroup?.className).not.toContain("overflow-x-auto");

    slider.focus();
    fireEvent.keyDown(slider, { key: "ArrowRight" });

    expect(slider.getAttribute("aria-valuenow")).toBe("6");
    expect(screen.getByText("Scor selectat: 6/10")).toBeTruthy();

    await vi.advanceTimersByTimeAsync(450);
    expect(saveQuestionnaireResponse).toHaveBeenCalledWith("drivers-assignment", {
      "driver_set:driver_a": 6,
    });
  });

  it("shows 1-10 slider ticks while preserving a stored 0-9 distress scale", async () => {
    vi.useFakeTimers();
    const distressDefinition: QuestionnaireDefinition = {
      ...mockDefinition,
      key: "distress_drivers",
      schema: {
        ...mockDefinition.schema,
        sections: [{
          id: "drivers",
          title: "Driveri",
          questions: [{
            id: "driver_set",
            code: "D1",
            type: "statement_score_set",
            label: "Ritmul de lucru",
            required: true,
            scale: Array.from({ length: 10 }, (_, index) => ({
              value: index,
              label: String(index),
            })),
            statements: [
              { id: "driver_a", code: "D1-A", label: "Lucrez sub presiunea timpului" },
            ],
          }],
        }],
      },
    };

    render(<QuestionnaireRunner definition={distressDefinition} assignmentId="drivers-assignment" />);

    const slider = screen.getByRole("slider", { name: "Lucrez sub presiunea timpului" });
    slider.focus();
    fireEvent.keyDown(slider, { key: "ArrowRight" });
    expect(slider.getAttribute("aria-valuenow")).toBe("6");
    expect(screen.getByText("Scor selectat: 6/10")).toBeTruthy();

    await vi.advanceTimersByTimeAsync(450);
    expect(saveQuestionnaireResponse).toHaveBeenCalledWith("drivers-assignment", {
      "driver_set:driver_a": 5,
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

    expect(
      screen.getByText(/Nu s-a salvat\. Poți reîncerca\. Serverul nu a putut salva draftul\./),
    ).toBeTruthy();
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

  it("saves through the back action and exits to the questionnaire list", async () => {
    render(
      <QuestionnaireRunner
        definition={mockDefinition}
        assignmentId="test-assignment"
        initialAnswers={{ q1: 1 }}
      />,
    );

    expect(screen.queryByRole("button", { name: "Salvează draft" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Înapoi la chestionare" }));

    await waitFor(() => {
      expect(routerPush).toHaveBeenCalledWith("/participant/questionnaires");
    });
    expect(screen.getByRole("button", { name: "Trimite răspunsurile" })).toBeTruthy();
    expect(saveQuestionnaireResponse).toHaveBeenCalledWith("test-assignment", { q1: 1 });
  });

  it("shows save-before-exit feedback while the back action is pending", async () => {
    let resolveSave!: () => void;
    const savePromise = new Promise<Awaited<ReturnType<typeof saveQuestionnaireResponse>>>((resolve) => {
      resolveSave = () => resolve({ status: "draft" } as Awaited<ReturnType<typeof saveQuestionnaireResponse>>);
    });
    vi.mocked(saveQuestionnaireResponse).mockReturnValueOnce(savePromise);

    render(
      <QuestionnaireRunner
        definition={mockDefinition}
        assignmentId="test-assignment"
        initialAnswers={{ q1: 1 }}
      />,
    );

    const optionButton = screen.getByRole("radio", { name: "Rar" }) as HTMLButtonElement;
    const backButton = screen.getByRole("button", { name: "Înapoi la chestionare" });
    fireEvent.click(backButton);
    fireEvent.click(backButton);

    expect(await screen.findByText("Se salvează…")).toBeTruthy();
    expect(screen.getAllByText("Se salvează")).toHaveLength(2);
    expect(screen.queryByText("Salvăm draftul înainte de ieșire")).toBeNull();
    expect(optionButton.disabled).toBe(true);
    expect(saveQuestionnaireResponse).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveSave();
      await savePromise;
    });

    await waitFor(() => {
      expect(routerPush).toHaveBeenCalledWith("/participant/questionnaires");
    });
  });

  it("submits completed answers and shows the completion view", async () => {
    render(
      <QuestionnaireRunner
        definition={mockDefinition}
        assignmentId="test-assignment"
        initialAnswers={{ q1: 2 }}
        returnHref="/participant/questionnaires"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Trimite răspunsurile" }));
    expect(screen.getByRole("dialog", { name: "Trimiți răspunsurile finale?" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Trimite" }));

    await waitFor(() => {
      expect(submitQuestionnaireResponse).toHaveBeenCalledWith("test-assignment", { q1: 2 });
      expect(routerRefresh).toHaveBeenCalled();
      expect(screen.getByText("Răspunsurile au fost trimise")).toBeTruthy();
    });
    expect(routerPush).not.toHaveBeenCalled();
  });

  it("shows final-submit progress on the submit control and locks answers while pending", async () => {
    let resolveSubmit!: () => void;
    const submitPromise = new Promise<Awaited<ReturnType<typeof submitQuestionnaireResponse>>>((resolve) => {
      resolveSubmit = () => resolve({ status: "submitted" } as Awaited<ReturnType<typeof submitQuestionnaireResponse>>);
    });
    vi.mocked(submitQuestionnaireResponse).mockReturnValueOnce(submitPromise);

    render(
      <QuestionnaireRunner
        definition={mockDefinition}
        assignmentId="test-assignment"
        initialAnswers={{ q1: 2 }}
        returnHref="/participant/questionnaires"
      />,
    );

    const optionButton = screen.getByRole("radio", { name: "De obicei" }) as HTMLButtonElement;
    fireEvent.click(screen.getByRole("button", { name: "Trimite răspunsurile" }));
    const confirmButton = screen.getByRole("button", { name: "Trimite" });
    fireEvent.click(confirmButton);
    fireEvent.click(confirmButton);

    expect((await screen.findByRole("button", { name: "Trimitem" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Trimitem răspunsurile…")).toBeTruthy();
    expect(screen.queryByText("Trimitem răspunsurile finale")).toBeNull();
    expect(optionButton.disabled).toBe(true);
    expect(submitQuestionnaireResponse).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveSubmit();
      await submitPromise;
    });

    await waitFor(() => {
      expect(screen.getByText("Răspunsurile au fost trimise")).toBeTruthy();
    });
    expect(routerPush).not.toHaveBeenCalled();
  });

  it("does not save a competing draft or navigate back while final submission is pending", async () => {
    let resolveSubmit!: () => void;
    const submitPromise = new Promise<Awaited<ReturnType<typeof submitQuestionnaireResponse>>>((resolve) => {
      resolveSubmit = () => resolve({ status: "submitted" } as Awaited<ReturnType<typeof submitQuestionnaireResponse>>);
    });
    vi.mocked(submitQuestionnaireResponse).mockReturnValueOnce(submitPromise);

    render(
      <QuestionnaireRunner
        definition={mockDefinition}
        assignmentId="test-assignment"
        initialAnswers={{ q1: 2 }}
        returnHref="/participant/questionnaires"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Trimite răspunsurile" }));
    fireEvent.click(screen.getByRole("button", { name: "Trimite" }));

    const backButton = await screen.findByRole("button", { name: "Înapoi la chestionare" });
    expect((backButton as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(backButton);

    expect(saveQuestionnaireResponse).not.toHaveBeenCalled();
    expect(routerPush).not.toHaveBeenCalled();

    await act(async () => {
      resolveSubmit();
      await submitPromise;
    });

    await waitFor(() => {
      expect(screen.getByText("Răspunsurile au fost trimise")).toBeTruthy();
    });
    expect(saveQuestionnaireResponse).not.toHaveBeenCalled();
    expect(routerPush).not.toHaveBeenCalled();
  });

  it("offers the next 360 review before returning to the task list", () => {
    render(
      <QuestionnaireRunner
        definition={mockDefinition}
        assignmentId="test-assignment"
        initialAnswers={{ q1: 2 }}
        initialStatus="submitted"
        returnHref="/participant/questionnaires"
        nextTaskHref="/participant/questionnaires/boss_360?assignmentId=next-review"
      />,
    );

    expect(
      screen.getByRole("link", { name: /Continuă cu următorul review/ }).getAttribute("href"),
    ).toBe("/participant/questionnaires/boss_360?assignmentId=next-review");
    expect(
      screen.getByRole("link", { name: "Înapoi la chestionare" }).getAttribute("href"),
    ).toBe("/participant/questionnaires");
  });

  it("shows a stale-session message when another tab changes the active account", async () => {
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
    fireEvent.click(screen.getByRole("button", { name: "Trimite" }));

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
    expect(screen.queryByRole("button", { name: "Salvează draft" })).toBeNull();
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

    const thinkerOption = screen.getByRole("radio", { name: /Gânditor/ });
    fireEvent.click(thinkerOption);

    expect(screen.getByText("100% completat")).toBeTruthy();
    expect(screen.getByRole("radiogroup", { name: "Care este baza ta PCM?" })).toBeTruthy();
    expect(thinkerOption.getAttribute("aria-checked")).toBe("true");

    await vi.advanceTimersByTimeAsync(450);
    expect(saveQuestionnaireResponse).toHaveBeenCalledWith("pcm-assignment", {
      pcm_base: "thinker",
    });
  });
});
