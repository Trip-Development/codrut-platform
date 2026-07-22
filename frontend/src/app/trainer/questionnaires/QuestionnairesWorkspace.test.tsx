import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createQuestionnaireDefinitionOnServer,
  getQuestionnaireDefinition,
  listQuestionnaireDefinitionStubs,
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
    createQuestionnaireDefinitionOnServer: vi.fn().mockResolvedValue({
      ...fixtures.definition,
      key: "lencioni",
      version: 2,
      title: "Chestionar nou",
      active: false,
      schema: {
        ...fixtures.definition.schema,
        sections: [{ id: "sectiunea_1", title: "Secțiunea 1", questions: [] }],
      },
    }),
    updateQuestionnaireDefinitionOnServer: vi.fn().mockResolvedValue(fixtures.definition),
  };
});

function resetQuestionnaireApiMocks() {
  vi.mocked(listQuestionnaireDefinitionStubs).mockResolvedValue([
    {
      id: "lencioni",
      name: "Chestionar de evaluare a echipei",
      description: "Initial description",
      status: "active",
      version: 1,
      audience: "team",
      estimatedItems: 1,
    },
  ]);
  vi.mocked(getQuestionnaireDefinition).mockResolvedValue(fixtures.definition);
  vi.mocked(createQuestionnaireDefinitionOnServer).mockResolvedValue({
    ...fixtures.definition,
    key: "lencioni",
    version: 2,
    title: "Chestionar nou",
    active: false,
    schema: {
      ...fixtures.definition.schema,
      sections: [{ id: "sectiunea_1", title: "Secțiunea 1", questions: [] }],
    },
  });
  vi.mocked(updateQuestionnaireDefinitionOnServer).mockResolvedValue(fixtures.definition);
}

describe("QuestionnairesWorkspace", () => {
  beforeEach(() => {
    resetQuestionnaireApiMocks();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("loads draft questionnaire definitions in the trainer editor catalog", async () => {
    render(<QuestionnairesWorkspace />);

    await waitFor(() =>
      expect(listQuestionnaireDefinitionStubs).toHaveBeenCalledWith(false, { latestOnly: false }),
    );
    expect(listQuestionnaireDefinitionStubs).toHaveBeenCalledTimes(1);
    expect(screen.getByPlaceholderText("Caută chestionar").getAttribute("data-slot")).toBe("input");
    const catalogCard = await screen.findByRole("button", { name: "Editează Chestionar de evaluare a echipei" });
    expect(catalogCard.getAttribute("data-slot")).toBe("button");
    expect(catalogCard.getAttribute("data-variant")).toBe("outline");
  });

  it("shows catalog load failures instead of leaving the editor empty", async () => {
    vi.mocked(listQuestionnaireDefinitionStubs).mockRejectedValueOnce(new Error("Catalog indisponibil."));

    render(<QuestionnairesWorkspace />);

    expect(await screen.findByText("Catalog indisponibil.")).toBeTruthy();
  });

  it("shows definition load failures after selecting a questionnaire", async () => {
    vi.mocked(getQuestionnaireDefinition).mockRejectedValueOnce(new Error("Definiția nu poate fi citită."));

    render(<QuestionnairesWorkspace />);

    fireEvent.click(await screen.findByText("Chestionar de evaluare a echipei"));

    expect((await screen.findByRole("alert")).textContent).toContain("Definiția nu poate fi citită.");
  });

  it("shows a missing-definition error instead of an empty editor shell", async () => {
    vi.mocked(getQuestionnaireDefinition).mockResolvedValueOnce(null);

    render(<QuestionnairesWorkspace />);

    fireEvent.click(await screen.findByText("Chestionar de evaluare a echipei"));

    expect((await screen.findByRole("alert")).textContent).toContain("Chestionarul nu a putut fi încărcat.");
  });

  it("keeps single-choice questionnaire questions explicit in the trainer editor", async () => {
    vi.mocked(getQuestionnaireDefinition).mockResolvedValueOnce({
      ...fixtures.definition,
      key: "pcm_base",
      title: "Baza și faza ta PCM",
      schema: {
        ...fixtures.definition.schema,
        sections: [
          {
            id: "pcm_base",
            title: "Profil PCM",
            questions: [
              {
                id: "pcm_base",
                code: "PCM-BASE",
                type: "single_choice",
                label: "Care este baza ta PCM?",
                required: true,
                scale: [
                  { value: "harmonizer", label: "Armonizator" },
                  { value: "thinker", label: "Gânditor" },
                ],
              },
            ],
          },
        ],
      },
    });

    render(<QuestionnairesWorkspace />);

    fireEvent.click(await screen.findByText("Chestionar de evaluare a echipei"));

    const questionCard = await screen.findByTestId("question-editor-pcm_base");
    expect(questionCard).toBeTruthy();
    expect(screen.getByLabelText("Tip întrebare PCM-BASE").getAttribute("data-slot")).toBe("select");
    expect(screen.getByDisplayValue("Alegere unică")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Scări" }));
    expect(screen.getByText("1 întrebare · Alegere unică")).toBeTruthy();
  });

  it("shows one latest catalog card while keeping older versions selectable", async () => {
    vi.mocked(listQuestionnaireDefinitionStubs).mockImplementation(async (_includeRetired, options) => {
      const latest = {
        id: "lencioni",
        name: "Latest Lencioni",
        description: "Latest description",
        status: "active" as const,
        version: 2,
        audience: "team" as const,
        estimatedItems: 2,
      };
      const older = {
        id: "lencioni",
        name: "Older Lencioni",
        description: "Older description",
        status: "active" as const,
        version: 1,
        audience: "team" as const,
        estimatedItems: 1,
      };
      return options?.latestOnly === false ? [latest, older] : [latest];
    });
    vi.mocked(getQuestionnaireDefinition).mockImplementation(async (key) => {
      const version = key.endsWith("@1") ? 1 : 2;
      return {
        ...fixtures.definition,
        version,
        title: version === 2 ? "Latest Lencioni" : "Older Lencioni",
      };
    });

    render(<QuestionnairesWorkspace />);

    const latestCard = await screen.findByText("Latest Lencioni");
    expect(screen.queryByText("Older Lencioni")).toBeNull();

    fireEvent.click(latestCard);

    expect((await screen.findByLabelText("Versiune")).getAttribute("data-slot")).toBe("select");
    expect(await screen.findByRole("option", { name: "v2 (Activă)" })).toBeTruthy();
    expect(screen.getByRole("option", { name: "v1 (Veche)" })).toBeTruthy();
  });

  it("creates a new questionnaire as an active incomplete definition", async () => {
    let resolveCreate: (definition: QuestionnaireDefinition) => void = () => {};
    vi.mocked(createQuestionnaireDefinitionOnServer).mockImplementation(
      () =>
        new Promise<QuestionnaireDefinition>((resolve) => {
          resolveCreate = resolve;
        }),
    );

    render(<QuestionnairesWorkspace />);

    fireEvent.click(await screen.findByRole("button", { name: "Creează chestionar" }));
    const modalTitle = await screen.findByText("Adaugă chestionar nou");
    const form = modalTitle.closest("form");
    expect(form).not.toBeNull();

    const formScope = within(form as HTMLElement);
    const categorySelect = formScope.getByLabelText("Cod unic (slug / categorie)");
    expect(categorySelect.getAttribute("data-slot")).toBe("select");
    expect(formScope.getByLabelText("Audiență țintă").getAttribute("data-slot")).toBe("select");
    expect(formScope.getByPlaceholderText("Chestionar nou").getAttribute("data-slot")).toBe("input");
    expect(formScope.getByPlaceholderText("Scurtă descriere a scopului acestui chestionar").getAttribute("data-slot")).toBe("textarea");
    fireEvent.change(categorySelect, { target: { value: "lencioni" } });
    fireEvent.submit(form!);
    fireEvent.submit(form!);

    expect(await screen.findByText("Creăm chestionarul")).toBeTruthy();
    expect(createQuestionnaireDefinitionOnServer).toHaveBeenCalledTimes(1);
    expect(createQuestionnaireDefinitionOnServer).toHaveBeenCalledWith(
      expect.objectContaining({
        key: "lencioni",
        title: "Chestionar nou",
        active: true,
        schema: expect.objectContaining({
          sections: [expect.objectContaining({ questions: [] })],
        }),
      }),
    );
    expect(formScope.getByRole("button", { name: "Creăm" })).toHaveProperty("disabled", true);

    await act(async () => {
      resolveCreate({
        ...fixtures.definition,
        key: "lencioni",
        version: 2,
        title: "Chestionar nou",
        schema: {
          ...fixtures.definition.schema,
          sections: [{ id: "sectiunea_1", title: "Secțiunea 1", questions: [] }],
        },
      });
    });
  });

  it("keeps typing local until the trainer explicitly saves", async () => {
    render(<QuestionnairesWorkspace />);

    const card = await screen.findByText("Chestionar de evaluare a echipei");
    fireEvent.click(card);
    fireEvent.click(await screen.findByRole("button", { name: "Setări" }));

    const titleInput = await screen.findByDisplayValue("Chestionar de evaluare a echipei");
    expect(titleInput.getAttribute("data-slot")).toBe("input");
    expect(screen.getByLabelText("Categorie / Slug").getAttribute("data-slot")).toBe("select");
    expect(screen.getByLabelText("Audiență").getAttribute("data-slot")).toBe("select");

    fireEvent.change(titleInput, { target: { value: "L" } });
    fireEvent.change(titleInput, { target: { value: "Le" } });
    fireEvent.change(titleInput, { target: { value: "Leadership" } });

    expect(titleInput).toHaveProperty("value", "Leadership");
    expect(screen.getByText("Modificări nesalvate")).toBeTruthy();
    expect(updateQuestionnaireDefinitionOnServer).not.toHaveBeenCalled();

    const saveButton = screen.getByRole("button", { name: "Salvează modificările" });
    fireEvent.click(saveButton);
    fireEvent.click(saveButton);

    await waitFor(() => expect(updateQuestionnaireDefinitionOnServer).toHaveBeenCalledTimes(1));
    expect(updateQuestionnaireDefinitionOnServer).toHaveBeenCalledWith(
      "lencioni",
      expect.objectContaining({ title: "Leadership" }),
      1,
    );
    expect(await screen.findByText("Salvat")).toBeTruthy();
  });

  it("protects a dirty questionnaire from reload and sidebar navigation", async () => {
    render(<QuestionnairesWorkspace />);

    fireEvent.click(await screen.findByText("Chestionar de evaluare a echipei"));
    fireEvent.click(await screen.findByRole("button", { name: "Setări" }));
    fireEvent.change(await screen.findByDisplayValue("Chestionar de evaluare a echipei"), {
      target: { value: "Titlu nesalvat" },
    });

    const beforeUnload = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(beforeUnload);
    expect(beforeUnload.defaultPrevented).toBe(true);

    const sidebarLink = document.createElement("a");
    sidebarLink.href = `${window.location.href}#projects`;
    sidebarLink.textContent = "Proiecte";
    document.body.appendChild(sidebarLink);
    fireEvent.click(sidebarLink);

    expect(screen.getAllByText("Modificări nesalvate")).toHaveLength(2);
    expect(screen.getByText(/pierzi modificările/i)).toBeTruthy();
    expect(window.location.hash).not.toBe("#projects");

    fireEvent.click(screen.getByRole("button", { name: "Renunță la modificări" }));
    expect(window.location.hash).toBe("#projects");
    const confirmedBeforeUnload = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(confirmedBeforeUnload);
    expect(confirmedBeforeUnload.defaultPrevented).toBe(false);
    sidebarLink.remove();
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

    const card = await screen.findByText("Chestionar de evaluare a echipei");
    fireEvent.click(card);

    const questionInput = await screen.findByDisplayValue("Initial question");

    fireEvent.change(questionInput, { target: { value: "P" } });
    fireEvent.change(questionInput, { target: { value: "Pr" } });
    fireEvent.change(questionInput, { target: { value: "Proces clar pentru echipă" } });

    expect(questionInput).toHaveProperty("value", "Proces clar pentru echipă");
    expect(screen.getByText("Modificări nesalvate")).toBeTruthy();
    expect(updateQuestionnaireDefinitionOnServer).not.toHaveBeenCalled();

    const saveButton = screen.getByRole("button", { name: "Salvează modificările" });
    fireEvent.click(saveButton);
    fireEvent.click(saveButton);
    expect(screen.getAllByText("Salvăm modificările").length).toBeGreaterThanOrEqual(1);
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

    fireEvent.change(questionInput, { target: { value: "Proces clar pentru echipă extins" } });
    expect(questionInput).toHaveProperty("value", "Proces clar pentru echipă extins");

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

    await waitFor(() => expect(questionInput).toHaveProperty("value", "Proces clar pentru echipă extins"));
    expect(screen.getByText("Modificări nesalvate")).toBeTruthy();
  });

  it("does not create duplicate questionnaire versions on rapid repeat clicks", async () => {
    let resolveCreate: (definition: QuestionnaireDefinition) => void = () => {};
    vi.mocked(createQuestionnaireDefinitionOnServer).mockImplementation(
      () =>
        new Promise<QuestionnaireDefinition>((resolve) => {
          resolveCreate = resolve;
        }),
    );

    render(<QuestionnairesWorkspace />);

    const card = await screen.findByText("Chestionar de evaluare a echipei");
    fireEvent.click(card);

    const versionButton = await screen.findByRole("button", { name: "Versiune nouă (clonează)" });
    fireEvent.click(versionButton);
    fireEvent.click(versionButton);

    await waitFor(() => expect(createQuestionnaireDefinitionOnServer).toHaveBeenCalledTimes(1));
    expect(createQuestionnaireDefinitionOnServer).toHaveBeenCalledWith(
      expect.objectContaining({
        key: "lencioni",
        title: "Chestionar de evaluare a echipei",
        active: true,
      }),
    );

    await act(async () => {
      resolveCreate({
        ...fixtures.definition,
        version: 2,
      });
    });
  });

  it("can discard local questionnaire edits without touching the server", async () => {
    render(<QuestionnairesWorkspace />);

    const card = await screen.findByText("Chestionar de evaluare a echipei");
    fireEvent.click(card);
    fireEvent.click(await screen.findByRole("button", { name: "Setări" }));

    const descriptionInput = await screen.findByDisplayValue("Initial description");
    expect(descriptionInput.getAttribute("data-slot")).toBe("textarea");
    fireEvent.change(descriptionInput, { target: { value: "Draft description" } });

    expect(descriptionInput).toHaveProperty("value", "Draft description");
    fireEvent.click(screen.getByRole("button", { name: "Revino la ultima versiune salvată" }));

    expect(descriptionInput).toHaveProperty("value", "Initial description");
    expect(updateQuestionnaireDefinitionOnServer).not.toHaveBeenCalled();
  });

  it("edits a shared answer scale globally for matching questions", async () => {
    render(<QuestionnairesWorkspace />);

    const card = await screen.findByText("Chestionar de evaluare a echipei");
    fireEvent.click(card);
    fireEvent.click(await screen.findByRole("button", { name: "Scări" }));

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

  it("keeps global scale inputs focused while editing their labels", async () => {
    render(<QuestionnairesWorkspace />);

    const card = await screen.findByText("Chestionar de evaluare a echipei");
    fireEvent.click(card);
    fireEvent.click(await screen.findByRole("button", { name: "Scări" }));

    const globalPanel = await screen.findByText("Scări globale de răspuns");
    const scaleCard = globalPanel.closest("section");
    expect(scaleCard).not.toBeNull();

    const labelInput = within(scaleCard as HTMLElement).getAllByDisplayValue("Rar")[0] as HTMLInputElement;
    expect(labelInput.getAttribute("data-slot")).toBe("input");
    labelInput.focus();

    fireEvent.change(labelInput, { target: { value: "Foarte r" } });
    expect(document.activeElement).toBe(labelInput);
    expect(labelInput).toHaveProperty("value", "Foarte r");

    fireEvent.change(labelInput, { target: { value: "Foarte rar" } });
    expect(document.activeElement).toBe(labelInput);
    expect(labelInput).toHaveProperty("value", "Foarte rar");
  });

  it("uses compact icon controls in the questionnaire workspace", async () => {
    render(<QuestionnairesWorkspace />);

    const card = await screen.findByText("Chestionar de evaluare a echipei");
    fireEvent.click(card);
    fireEvent.click(await screen.findByRole("button", { name: "Scări" }));

    const globalPanel = await screen.findByText("Scări globale de răspuns");
    const scaleCard = globalPanel.closest("section");
    expect(scaleCard).not.toBeNull();

    const addOptionButton = within(scaleCard as HTMLElement).getByRole("button", {
      name: "Adaugă opțiune în scara Rar / Des",
    });
    expect(addOptionButton.textContent).not.toContain("Adaugă");
    expect(addOptionButton.getAttribute("data-slot")).toBe("button");
    expect(addOptionButton.getAttribute("data-size")).toBe("icon-sm");
    expect(addOptionButton.getAttribute("data-variant")).toBe("ghost");

    const addQuestionButtons = await screen.findAllByRole("button", {
      name: "Adaugă întrebare în secțiunea Section one",
    });
    const addQuestionButton = addQuestionButtons.find((button) => button.getAttribute("data-size") === "icon-sm")!;
    expect(addQuestionButton).toBeTruthy();
    expect(addQuestionButton.textContent).not.toContain("Adaugă");
    expect(addQuestionButton.getAttribute("data-slot")).toBe("button");
    expect(addQuestionButton.getAttribute("data-size")).toBe("icon-sm");

    const deleteSectionButton = screen.getByRole("button", {
      name: "Șterge secțiunea Section one",
    });
    expect(deleteSectionButton.textContent).not.toContain("Șterge");
    expect(deleteSectionButton.getAttribute("data-slot")).toBe("button");
    expect(deleteSectionButton.getAttribute("data-size")).toBe("icon-sm");
    expect(deleteSectionButton.getAttribute("data-variant")).toBe("ghost");

    fireEvent.click(screen.getByRole("button", { name: "Întrebare" }));
    fireEvent.change(screen.getByDisplayValue("Scară Likert"), {
      target: { value: "statement_score_set" },
    });

    const questionCard = await screen.findByTestId("question-editor-q1");
    const questionScope = within(questionCard);
    const addStatementButton = questionScope.getByRole("button", {
      name: "Adaugă afirmație în întrebarea Q1",
    });
    expect(addStatementButton.textContent).not.toContain("Adaugă");
    expect(addStatementButton.getAttribute("data-slot")).toBe("button");
    expect(addStatementButton.getAttribute("data-size")).toBe("icon-sm");
  });

  it("shows statement-specific participant answers instead of an empty fallback scale", async () => {
    const icareDefinition: QuestionnaireDefinition = {
      ...fixtures.definition,
      key: "boss_360",
      title: "Feedback 360 iCARE pentru manager",
      schema: {
        ...fixtures.definition.schema,
        audience: "participant",
        sections: [
          {
            id: "inspiring",
            title: "Inspiră",
            questions: [
              {
                id: "icare_feedback",
                code: "ICARE-1",
                type: "statement_score_set",
                label: "Dezvoltă oamenii",
                required: true,
                scale: [
                  { value: 1, label: "1" },
                  { value: 2, label: "2" },
                  { value: 3, label: "3" },
                  { value: 4, label: "4" },
                ],
                statements: [
                  {
                    id: "icare_s1",
                    code: "S1",
                    label: "Oferă feedback constructiv",
                    scale: [
                      { value: 1, label: "1", description: "Nu oferă feedback sau îl evită complet." },
                      { value: 2, label: "2", description: "Oferă feedback rar, doar când i se cere." },
                      { value: 3, label: "3", description: "Oferă feedback destul de des." },
                      { value: 4, label: "4", description: "Oferă feedback regulat și constructiv." },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
    };
    vi.mocked(listQuestionnaireDefinitionStubs).mockResolvedValue([
      {
        id: "boss_360",
        name: icareDefinition.title,
        description: "Feedback comportamental iCARE",
        status: "active",
        version: 1,
        audience: "participant",
        estimatedItems: 1,
      },
    ]);
    vi.mocked(getQuestionnaireDefinition).mockResolvedValue(icareDefinition);

    render(<QuestionnairesWorkspace />);

    fireEvent.click(await screen.findByText("Feedback 360 iCARE pentru manager"));

    const questionCard = await screen.findByTestId("question-editor-icare_feedback");
    const questionScope = within(questionCard);
    expect(screen.queryByText("Scări globale de răspuns")).toBeNull();
    expect(questionScope.queryByRole("button", { name: "Editează scara locală" })).toBeNull();
    expect(questionScope.getByText("Răspunsuri văzute de participant")).toBeTruthy();
    expect(questionScope.getByLabelText("Descriere participant S1 1")).toHaveProperty(
      "value",
      "Nu oferă feedback sau îl evită complet.",
    );

    fireEvent.change(questionScope.getByLabelText("Descriere participant S1 2"), {
      target: { value: "Oferă feedback rar." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvează modificările" }));

    await waitFor(() => expect(updateQuestionnaireDefinitionOnServer).toHaveBeenCalledTimes(1));
    expect(updateQuestionnaireDefinitionOnServer).toHaveBeenCalledWith(
      "boss_360",
      expect.objectContaining({
        schema: expect.objectContaining({
          sections: [
            expect.objectContaining({
              questions: [
                expect.objectContaining({
                  statements: [
                    expect.objectContaining({
                      scale: expect.arrayContaining([
                        expect.objectContaining({ value: 2, description: "Oferă feedback rar." }),
                      ]),
                    }),
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

  it("keeps local scale editing collapsed by default and stable while typing", async () => {
    render(<QuestionnairesWorkspace />);

    const card = await screen.findByText("Chestionar de evaluare a echipei");
    fireEvent.click(card);

    const questionCard = await screen.findByTestId("question-editor-q1");
    const questionScope = within(questionCard);

    expect(questionScope.queryByPlaceholderText("Descriere opțională pentru această opțiune")).toBeNull();
    fireEvent.click(questionScope.getByRole("button", { name: "Editează scara locală" }));

    const localLabelInput = questionScope.getByDisplayValue("Rar") as HTMLInputElement;
    localLabelInput.focus();

    fireEvent.change(localLabelInput, { target: { value: "Aproape niciodată" } });

    expect(document.activeElement).toBe(localLabelInput);
    expect(localLabelInput).toHaveProperty("value", "Aproape niciodată");
    expect(questionScope.getByRole("button", { name: "Ascunde scara" })).toBeTruthy();
  });

  it("keeps one question active and uses compact rows for the rest", async () => {
    render(<QuestionnairesWorkspace />);

    fireEvent.click(await screen.findByText("Chestionar de evaluare a echipei"));

    expect(await screen.findByTestId("question-editor-q1")).toBeTruthy();
    expect(screen.queryByTestId("question-editor-q2")).toBeNull();
    expect(screen.getByTestId("question-row-q2")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Editează Q2 Second question" }));

    expect(await screen.findByTestId("question-editor-q2")).toBeTruthy();
    expect(screen.queryByTestId("question-editor-q1")).toBeNull();
    expect(screen.getByRole("heading", { name: "Second question" })).toBeTruthy();
  });

  it("persists question order changed with accessible controls", async () => {
    vi.mocked(updateQuestionnaireDefinitionOnServer).mockImplementation(async (_key, payload, version) => ({
      ...fixtures.definition,
      version: version ?? fixtures.definition.version,
      title: payload.title ?? fixtures.definition.title,
      description: payload.description ?? fixtures.definition.description,
      schema: payload.schema ?? fixtures.definition.schema,
    }));
    render(<QuestionnairesWorkspace />);

    fireEvent.click(await screen.findByText("Chestionar de evaluare a echipei"));
    await screen.findByTestId("question-editor-q1");
    fireEvent.click(screen.getByRole("button", { name: "Editează Q2 Second question" }));
    fireEvent.click(screen.getByRole("button", { name: "Mută întrebarea mai sus" }));
    fireEvent.click(screen.getByRole("button", { name: "Salvează modificările" }));

    await waitFor(() => expect(updateQuestionnaireDefinitionOnServer).toHaveBeenCalledTimes(1));
    expect(updateQuestionnaireDefinitionOnServer).toHaveBeenCalledWith(
      "lencioni",
      expect.objectContaining({
        schema: expect.objectContaining({
          sections: [
            expect.objectContaining({
              questions: [
                expect.objectContaining({ id: "q2" }),
                expect.objectContaining({ id: "q1" }),
              ],
            }),
          ],
        }),
      }),
      1,
    );
  });
});
