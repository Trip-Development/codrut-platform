"use client";

import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import {
  listQuestionnaireDefinitionStubs,
  getQuestionnaireDefinition,
  createQuestionnaireDefinitionOnServer,
  updateQuestionnaireDefinitionOnServer,
  deleteQuestionnaireDefinitionOnServer,
  type QuestionnaireDefinitionStub,
  type QuestionnaireDefinition,
  type QuestionnaireSection,
  type QuestionnaireQuestion,
  type QuestionnaireScaleOption,
  type QuestionnaireStatement
} from "@/api/questionnaires";

const destructiveButtonClass =
  "tap-soft rounded-lg border border-[#890505]/35 bg-transparent px-3 py-1.5 text-xs font-bold text-[#890505] shadow-none transition hover:bg-[#890505]/10 disabled:cursor-not-allowed disabled:border-[var(--border)] disabled:bg-transparent disabled:text-foreground/35 dark:border-[#e35f5f]/45 dark:text-[#e35f5f] dark:hover:bg-[#890505]/22";

export function QuestionnairesWorkspace() {
  const [stubs, setStubs] = useState<QuestionnaireDefinitionStub[]>([]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<number>(1);
  const [availableVersions, setAvailableVersions] = useState<number[]>([]);
  const [currentDefinition, setCurrentDefinition] = useState<QuestionnaireDefinition | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [draftKey, setDraftKey] = useState("");

  // New Questionnaire Modal State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newAudience, setNewAudience] = useState<"leadership" | "team" | "participant">("team");

  // Load stubs list
  const loadStubs = async () => {
    setIsLoading(true);
    try {
      const list = await listQuestionnaireDefinitionStubs();
      setStubs(list);
      if (list.length > 0 && !selectedKey) {
        setSelectedKey(list[0].id);
        setSelectedVersion(list[0].version ?? 1);
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadStubs();
  }, []);

  // Sync available versions and load definition details when selected key or version changes
  useEffect(() => {
    if (!selectedKey) return;

    const allVersions: number[] = stubs
      .filter((s) => s.id === selectedKey)
      .map((s) => s.version)
      .filter((v): v is number => typeof v === "number");

    if (allVersions.length === 0) {
      allVersions.push(1);
    }

    allVersions.sort((a, b) => b - a); // Descending
    setAvailableVersions(allVersions);

    // If selectedVersion is not in the list, set to the highest version
    if (!allVersions.includes(selectedVersion)) {
      setSelectedVersion(allVersions[0]);
    }
  }, [selectedKey, stubs]);

  useEffect(() => {
    if (!selectedKey) return;
    const fetchDefinition = async () => {
      setIsLoading(true);
      try {
        const def = await getQuestionnaireDefinition(`${selectedKey}@${selectedVersion}`);
        setCurrentDefinition(def);
        setDraftKey(def?.key ?? "");
      } finally {
        setIsLoading(false);
      }
    };
    fetchDefinition();
  }, [selectedKey, selectedVersion]);

  const handleSave = async (updatedDef: QuestionnaireDefinition) => {
    setIsLoading(true);
    try {
      const saved = await updateQuestionnaireDefinitionOnServer(
        updatedDef.key,
        {
          title: updatedDef.title,
          description: updatedDef.description,
          schema: updatedDef.schema,
        },
        updatedDef.version
      );
      setCurrentDefinition(saved);
      if (saved.version !== updatedDef.version) {
        setSelectedVersion(saved.version);
      }
      await loadStubs();
    } catch (e) {
      alert((e as Error).message ?? "Eroare la salvarea chestionarului.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveMetadata = (
    fields: Partial<Pick<QuestionnaireDefinition, "title" | "description">> & {
      audience?: "leadership" | "team" | "participant";
    },
  ) => {
    if (!currentDefinition) return;
    handleSave({
      ...currentDefinition,
      ...fields,
      schema: {
        ...currentDefinition.schema,
        audience: fields.audience ?? currentDefinition.schema.audience,
      },
    });
  };

  const handleRenameDefinitionKey = () => {
    alert("Redenumirea cheii nu este permisă pe server. Creează un chestionar nou cu o altă cheie dacă este necesar.");
  };

  const handleCreateNewVersion = async () => {
    if (!currentDefinition) return;
    setIsLoading(true);
    try {
      const saved = await createQuestionnaireDefinitionOnServer({
        key: currentDefinition.key,
        title: currentDefinition.title,
        description: currentDefinition.description,
        schema: currentDefinition.schema,
        active: true,
      });
      setSelectedVersion(saved.version);
      await loadStubs();
    } catch (e) {
      alert((e as Error).message ?? "Eroare la crearea unei noi versiuni.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteQuestionnaire = async () => {
    if (!selectedKey) return;
    const selectedName = currentDefinition?.title ?? selectedKey;
    const confirmed = window.confirm(
      `Pensionați chestionarul "${selectedName}"? Această acțiune îl va marca ca inactiv pe server.`,
    );
    if (!confirmed) return;

    setIsLoading(true);
    try {
      await deleteQuestionnaireDefinitionOnServer(selectedKey, selectedVersion);
      const remaining = await listQuestionnaireDefinitionStubs();
      setStubs(remaining);
      const nextSelection = remaining.find((stub) => stub.id !== selectedKey) ?? remaining[0];
      if (nextSelection) {
        setSelectedKey(nextSelection.id);
        setSelectedVersion(nextSelection.version ?? 1);
      } else {
        setSelectedKey(null);
        setCurrentDefinition(null);
        setAvailableVersions([]);
      }
    } catch (e) {
      alert((e as Error).message ?? "Eroare la ștergerea/pensionarea chestionarului.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddQuestionnaire = async (e: FormEvent) => {
    e.preventDefault();
    if (!newKey || !newTitle) return;

    const key = newKey.toLowerCase().replace(/[^a-z0-9_]/g, "_");
    setIsLoading(true);
    try {
      const saved = await createQuestionnaireDefinitionOnServer({
        key,
        title: newTitle,
        description: newDescription,
        schema: {
          schema_version: "questionnaire.v1",
          audience: newAudience,
          instructions: "Te rugăm să completezi formularul de mai jos.",
          sections: [
            {
              id: "sectiunea_1",
              title: "Secțiunea 1",
              questions: [
                {
                  id: `${key}_q1`,
                  code: "Q1",
                  type: "likert",
                  label: "Prima întrebare din acest chestionar.",
                  required: true,
                  scale: [
                     { value: 1, label: "Dezacord total" },
                     { value: 2, label: "Neutru" },
                     { value: 3, label: "Acord total" },
                  ],
                },
              ],
            },
          ],
        },
        active: true,
      });

      setShowCreateModal(false);
      setNewKey("");
      setNewTitle("");
      setNewDescription("");
      setSelectedKey(saved.key);
      setSelectedVersion(saved.version);
      await loadStubs();
    } catch (e) {
      alert((e as Error).message ?? "Eroare la crearea chestionarului.");
    } finally {
      setIsLoading(false);
    }
  };

  // Section modifiers
  const handleAddSection = () => {
    if (!currentDefinition) return;
    const sections = [...currentDefinition.schema.sections];
    const newSectionId = `sectiunea_${sections.length + 1}`;
    sections.push({
      id: newSectionId,
      title: `Secțiunea ${sections.length + 1}`,
      questions: [],
    });

    handleSave({
      ...currentDefinition,
      schema: {
        ...currentDefinition.schema,
        sections,
      },
    });
  };

  const handleUpdateSectionTitle = (sectionIndex: number, title: string) => {
    if (!currentDefinition) return;
    const sections = [...currentDefinition.schema.sections];
    sections[sectionIndex] = {
      ...sections[sectionIndex],
      title,
    };

    handleSave({
      ...currentDefinition,
      schema: {
        ...currentDefinition.schema,
        sections,
      },
    });
  };

  const handleDeleteSection = (sectionIndex: number) => {
    if (!currentDefinition) return;
    if (currentDefinition.schema.sections.length <= 1) {
      alert("Chestionarul trebuie să aibă cel puțin o secțiune.");
      return;
    }
    const sections = currentDefinition.schema.sections.filter((_, i) => i !== sectionIndex);
    handleSave({
      ...currentDefinition,
      schema: {
        ...currentDefinition.schema,
        sections,
      },
    });
  };

  // Question modifiers
  const handleAddQuestion = (sectionIndex: number) => {
    if (!currentDefinition) return;
    const sections = [...currentDefinition.schema.sections];
    const section = sections[sectionIndex];
    const nextIndex = section.questions.length + 1;
    const questionId = `${currentDefinition.key}_s${sectionIndex + 1}_q${nextIndex}_${Date.now().toString().slice(-4)}`;

    const newQuestion: QuestionnaireQuestion = {
      id: questionId,
      code: `Q${nextIndex}`,
      type: "likert",
      label: "Întrebare nouă. Faceți clic pentru a edita textul.",
      required: true,
      scale: [
        { value: 1, label: "Rar" },
        { value: 2, label: "Uneori" },
        { value: 3, label: "De obicei" },
      ],
    };

    const questions = [...section.questions, newQuestion];
    sections[sectionIndex] = {
      ...section,
      questions,
    };

    handleSave({
      ...currentDefinition,
      schema: {
        ...currentDefinition.schema,
        sections,
      },
    });
  };

  const handleUpdateQuestion = (
    sectionIndex: number,
    questionIndex: number,
    fields: Partial<QuestionnaireQuestion>
  ) => {
    if (!currentDefinition) return;
    const sections = [...currentDefinition.schema.sections];
    const section = sections[sectionIndex];
    const questions = [...section.questions];

    questions[questionIndex] = {
      ...questions[questionIndex],
      ...fields,
    };

    sections[sectionIndex] = {
      ...section,
      questions,
    };

    handleSave({
      ...currentDefinition,
      schema: {
        ...currentDefinition.schema,
        sections,
      },
    });
  };

  const handleDeleteQuestion = (sectionIndex: number, questionIndex: number) => {
    if (!currentDefinition) return;
    const sections = [...currentDefinition.schema.sections];
    const section = sections[sectionIndex];
    const questions = section.questions.filter((_, i) => i !== questionIndex);

    sections[sectionIndex] = {
      ...section,
      questions,
    };

    handleSave({
      ...currentDefinition,
      schema: {
        ...currentDefinition.schema,
        sections,
      },
    });
  };

  // Statement list modifiers for Distress Drivers style statement set questions
  const handleAddStatement = (sectionIndex: number, questionIndex: number) => {
    if (!currentDefinition) return;
    const sections = [...currentDefinition.schema.sections];
    const question = sections[sectionIndex].questions[questionIndex];
    const statements = [...(question.statements || [])];
    const nextCode = `S${statements.length + 1}`;

    statements.push({
      id: `${question.id}_s${statements.length + 1}`,
      code: nextCode,
      label: "Afirmație suplimentară.",
    });

    handleUpdateQuestion(sectionIndex, questionIndex, { statements });
  };

  const handleUpdateStatementLabel = (
    sectionIndex: number,
    questionIndex: number,
    statementIndex: number,
    label: string
  ) => {
    if (!currentDefinition) return;
    const sections = [...currentDefinition.schema.sections];
    const question = sections[sectionIndex].questions[questionIndex];
    const statements = [...(question.statements || [])];

    statements[statementIndex] = {
      ...statements[statementIndex],
      label,
    };

    handleUpdateQuestion(sectionIndex, questionIndex, { statements });
  };

  const handleDeleteStatement = (sectionIndex: number, questionIndex: number, statementIndex: number) => {
    if (!currentDefinition) return;
    const sections = [...currentDefinition.schema.sections];
    const question = sections[sectionIndex].questions[questionIndex];
    const statements = (question.statements || []).filter((_, i) => i !== statementIndex);

    handleUpdateQuestion(sectionIndex, questionIndex, { statements });
  };

  const selectedStub = stubs.find((s) => s.id === selectedKey);
  const canDeleteSelected = !!selectedKey;

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="text-base font-bold text-foreground">Catalog chestionare</h2>
              <p className="mt-1 text-xs leading-5 text-foreground/52">Definiții active și drafturi.</p>
            </div>
            <button
              onClick={() => setShowCreateModal(true)}
              className="tap-soft rounded-lg bg-burgundy px-3 py-1.5 text-xs font-bold text-white hover:bg-burgundy/90"
            >
              + Nou
            </button>
          </div>

          <div className="mt-4 flex gap-3 overflow-x-auto pb-1">
            {stubs.map((stub) => {
              const isLocal = false;

              return (
              <button
                key={stub.id}
                onClick={() => {
                  setSelectedKey(stub.id);
                  setSelectedVersion(stub.version ?? 1);
                }}
                className={`min-w-[16rem] max-w-[18rem] text-left p-3 rounded-xl border transition-all ${
                  selectedKey === stub.id
                    ? "bg-burgundy/10 border-burgundy/40 text-foreground"
                    : "bg-background border-[var(--border)] text-foreground/70 hover:border-burgundy/30"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-bold uppercase tracking-wider text-burgundy">
                    {stub.audience}
                  </span>
                  <div className="flex items-center gap-1.5">
                    {isLocal ? (
                      <span className="rounded-full border border-success/25 bg-success/12 px-1.5 py-0.5 text-[10px] font-bold text-success-ink">
                        local
                      </span>
                    ) : null}
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-surface-muted text-foreground/60 border border-[var(--border)]">
                      v{stub.version ?? 1}
                    </span>
                  </div>
                </div>
                <h3 className="mt-1 font-bold text-sm text-foreground">{stub.name}</h3>
                <p className="mt-1 text-xs text-foreground/50 line-clamp-2 leading-relaxed">
                  {stub.description}
                </p>
                <div className="mt-2 flex items-center justify-between text-[11px] font-semibold text-foreground/45 border-t border-[var(--border)] pt-2">
                  <span>{stub.estimatedItems ?? "TBD"} întrebări</span>
                  <span className="capitalize">{stub.status}</span>
                </div>
              </button>
              );
            })}
          </div>
      </section>

      {/* Main Content Area */}
      <main className="space-y-5">
        {isLoading ? (
          <div className="flex items-center justify-center h-64 rounded-2xl border border-[var(--border)] bg-surface">
            <p className="text-sm font-semibold text-foreground/50">Se încarcă detaliile chestionarului...</p>
          </div>
        ) : currentDefinition ? (
          <section className="rounded-2xl border border-[var(--border)] bg-surface p-6 shadow-sm space-y-6">
            {/* Header info card */}
            <div className="grid gap-5 border-b border-[var(--border)] pb-5 xl:grid-cols-[minmax(0,1fr)_auto]">
              <div className="min-w-0 space-y-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full border border-[#890505]/35 bg-[#890505]/10 px-2.5 py-1 text-xs font-bold text-[#890505] shadow-none dark:border-[#e35f5f]/45 dark:bg-[#890505]/22 dark:text-[#e35f5f]">
                    Audiență: {currentDefinition.schema.audience ?? (currentDefinition.key === "distress_drivers" ? "leadership" : "team")}
                  </span>
                  <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-bold text-foreground/60 border border-[var(--border)]">
                    {canDeleteSelected ? "Local editabil" : "Definiție de bază"}
                  </span>
                </div>

                <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_15rem]">
                  <label className="space-y-1.5">
                    <span className="text-xs font-bold uppercase tracking-wider text-foreground/50">Nume chestionar</span>
                    <input
                      value={currentDefinition.title}
                      onChange={(e) => handleSaveMetadata({ title: e.target.value })}
                      className="w-full rounded-2xl border border-[var(--border)] bg-background px-4 py-3 text-lg font-bold text-foreground outline-none focus:border-burgundy/45"
                    />
                  </label>
                  <label className="space-y-1.5">
                    <span className="text-xs font-bold uppercase tracking-wider text-foreground/50">Slug</span>
                    <input
                      value={draftKey}
                      onChange={(e) => setDraftKey(e.target.value)}
                      onBlur={handleRenameDefinitionKey}
                      className="w-full rounded-2xl border border-[var(--border)] bg-background px-4 py-3 text-sm font-bold text-foreground outline-none focus:border-burgundy/45"
                    />
                  </label>
                </div>

                <label className="block space-y-1.5">
                  <span className="text-xs font-bold uppercase tracking-wider text-foreground/50">Descriere</span>
                  <textarea
                    value={currentDefinition.description}
                    onChange={(e) => handleSaveMetadata({ description: e.target.value })}
                    rows={2}
                    className="w-full rounded-2xl border border-[var(--border)] bg-background px-4 py-3 text-sm font-semibold leading-6 text-foreground outline-none focus:border-burgundy/45"
                  />
                </label>
              </div>

              {/* Version Controls */}
              <div className="flex flex-col gap-3 xl:items-end">
                <label className="space-y-1.5">
                  <span className="block text-xs font-bold uppercase tracking-wider text-foreground/50">Audiență</span>
                  <select
                    value={currentDefinition.schema.audience ?? (currentDefinition.key === "distress_drivers" ? "leadership" : "team")}
                    onChange={(e) =>
                      handleSaveMetadata({
                        audience: e.target.value as "leadership" | "team" | "participant",
                      })
                    }
                    className="w-full rounded-xl border border-[var(--border)] bg-background px-3 py-2 text-xs font-bold text-foreground xl:w-48"
                  >
                    <option value="team">Echipă</option>
                    <option value="leadership">Leadership</option>
                    <option value="participant">Individual</option>
                  </select>
                </label>
                <label className="space-y-1.5">
                  <span className="block text-xs font-bold uppercase tracking-wider text-foreground/50">Versiune</span>
                  <select
                    value={selectedVersion}
                    onChange={(e) => setSelectedVersion(Number(e.target.value))}
                    className="w-full rounded-xl border border-[var(--border)] bg-background px-3 py-2 text-xs font-bold text-foreground xl:w-48"
                  >
                    {availableVersions.map((v) => (
                      <option key={v} value={v}>
                        v{v} {v === selectedStub?.version ? "(Activă)" : "(Veche)"}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="flex flex-wrap gap-2 xl:justify-end">
                  <button
                    onClick={handleCreateNewVersion}
                    className="tap-soft rounded-lg border border-[var(--border)] bg-background px-3 py-1.5 text-xs font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy"
                  >
                    Versiune Nouă (Clone)
                  </button>
                  <button
                    onClick={handleDeleteQuestionnaire}
                    disabled={!canDeleteSelected}
                    className={destructiveButtonClass}
                    title={
                      canDeleteSelected
                        ? "Șterge chestionarul local"
                        : "Definițiile de bază sunt protejate; clonează sau creează un chestionar local pentru ștergere."
                    }
                  >
                    Șterge chestionarul
                  </button>
                </div>
              </div>
            </div>

            {/* Instruction editor */}
            <div className="space-y-2">
              <label className="block text-xs font-bold uppercase tracking-wider text-foreground/50">
                Instrucțiuni Chestionar
              </label>
              <textarea
                value={currentDefinition.schema.instructions ?? ""}
                onChange={(e) =>
                  handleSave({
                    ...currentDefinition,
                    schema: { ...currentDefinition.schema, instructions: e.target.value },
                  })
                }
                rows={2}
                className="w-full rounded-xl border border-[var(--border)] bg-background px-4 py-3 text-sm font-semibold text-foreground focus:border-burgundy/45"
                placeholder="Instrucțiuni prezentate utilizatorului..."
              />
            </div>

            {/* Sections & Questions Editor */}
            <div className="space-y-5">
              <div className="flex items-center justify-between border-b border-[var(--border)] pb-2">
                <h3 className="text-base font-bold text-foreground">Secțiuni ({currentDefinition.schema.sections.length})</h3>
                <button
                  onClick={handleAddSection}
                  className="tap-soft rounded-lg bg-burgundy px-3 py-1.5 text-xs font-bold text-white hover:bg-burgundy/90"
                >
                  + Adaugă Secțiune
                </button>
              </div>

              {currentDefinition.schema.sections.map((section, sIndex) => (
                <div key={section.id} className="rounded-xl border border-[var(--border)] bg-background p-5 space-y-4">
                  <div className="flex flex-wrap items-center justify-between gap-3 border-b border-[var(--border)] pb-3">
                    <input
                      type="text"
                      value={section.title}
                      onChange={(e) => handleUpdateSectionTitle(sIndex, e.target.value)}
                      className="bg-transparent text-base font-bold text-foreground border-b border-transparent hover:border-foreground/20 focus:border-burgundy px-1 py-0.5 focus:outline-none"
                    />
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleAddQuestion(sIndex)}
                        className="tap-soft rounded-lg bg-burgundy/10 border border-burgundy/20 px-3 py-1.5 text-xs font-bold text-burgundy hover:bg-burgundy/20"
                      >
                        + Adaugă Întrebare
                      </button>
                      <button
                        onClick={() => handleDeleteSection(sIndex)}
                        className={destructiveButtonClass}
                      >
                        Șterge secțiunea
                      </button>
                    </div>
                  </div>

                  {/* Questions inside Section */}
                  <div className="space-y-4">
                    {section.questions.length === 0 ? (
                      <p className="text-xs font-semibold text-foreground/45 text-center py-4">
                        Nicio întrebare în această secțiune. Faceți clic pe butonul de mai sus pentru a adăuga una.
                      </p>
                    ) : (
                      section.questions.map((question, qIndex) => (
                        <div
                          key={question.id}
                          className="rounded-lg border border-[var(--border)] bg-surface p-4 space-y-3 shadow-sm"
                        >
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div className="flex gap-2 items-center flex-1">
                              <input
                                type="text"
                                value={question.code}
                                onChange={(e) =>
                                  handleUpdateQuestion(sIndex, qIndex, { code: e.target.value })
                                }
                                placeholder="Cod"
                                className="w-16 rounded-md border border-[var(--border)] bg-background px-2 py-1 text-xs font-bold text-foreground text-center"
                              />
                              <input
                                type="text"
                                value={question.label}
                                onChange={(e) =>
                                  handleUpdateQuestion(sIndex, qIndex, { label: e.target.value })
                                }
                                placeholder="Textul întrebării"
                                className="flex-1 rounded-md border border-[var(--border)] bg-background px-3 py-1 text-xs font-semibold text-foreground"
                              />
                            </div>
                            <div className="flex items-center gap-2">
                              <select
                                value={question.type}
                                onChange={(e) =>
                                  handleUpdateQuestion(sIndex, qIndex, {
                                    type: e.target.value as "likert" | "statement_score_set",
                                    statements: e.target.value === "statement_score_set" ? [] : undefined,
                                  })
                                }
                                className="rounded-md border border-[var(--border)] bg-background px-2.5 py-1 text-xs font-semibold text-foreground"
                              >
                                <option value="likert">Scarile Likert</option>
                                <option value="statement_score_set">Set de afirmații</option>
                              </select>
                              <label className="flex items-center gap-1.5 text-xs font-semibold text-foreground/75 select-none cursor-pointer">
                                <input
                                  type="checkbox"
                                  checked={question.required}
                                  onChange={(e) =>
                                    handleUpdateQuestion(sIndex, qIndex, { required: e.target.checked })
                                  }
                                  className="rounded border-[var(--border)] accent-[#890505] focus:ring-burgundy"
                                />
                                Obligatoriu
                              </label>
                              <button
                                onClick={() => handleDeleteQuestion(sIndex, qIndex)}
                                className={destructiveButtonClass}
                                title="Șterge întrebarea"
                              >
                                Șterge întrebarea
                              </button>
                            </div>
                          </div>

                          {/* Instructions (optional) */}
                          <div>
                            <input
                              type="text"
                              value={question.instructions ?? ""}
                              onChange={(e) =>
                                handleUpdateQuestion(sIndex, qIndex, { instructions: e.target.value || undefined })
                              }
                              placeholder="Indicații opționale de răspuns..."
                              className="w-full rounded-md border border-[var(--border)] bg-background px-3 py-1.5 text-xs font-semibold text-foreground/75 focus:border-burgundy/45"
                            />
                          </div>

                          {/* Likert Scale configuration */}
                          <div className="border-t border-[var(--border)] pt-3">
                            <p className="text-[10px] font-bold uppercase tracking-wider text-foreground/50 mb-2">
                              Opțiuni de răspuns (Scară de notare)
                            </p>
                            <div className="flex flex-wrap gap-2 items-center">
                              {question.scale.map((opt, optIndex) => (
                                <div key={optIndex} className="flex items-center gap-1 bg-surface-muted rounded-lg border border-[var(--border)] px-2.5 py-1 text-xs">
                                  <span className="font-bold text-burgundy">{opt.value}</span>
                                  <input
                                    type="text"
                                    value={opt.label}
                                    onChange={(e) => {
                                      const newScale = [...question.scale];
                                      newScale[optIndex] = { ...newScale[optIndex], label: e.target.value };
                                      handleUpdateQuestion(sIndex, qIndex, { scale: newScale });
                                    }}
                                    className="bg-transparent border-0 font-semibold p-0 w-24 text-foreground/75 focus:outline-none focus:ring-0 text-xs"
                                  />
                                  <button
                                    onClick={() => {
                                      const newScale = question.scale.filter((_, i) => i !== optIndex);
                                      handleUpdateQuestion(sIndex, qIndex, { scale: newScale });
                                    }}
                                    className="text-foreground/40 hover:text-red-700 ml-1 font-bold"
                                  >
                                    ×
                                  </button>
                                </div>
                              ))}
                              <button
                                onClick={() => {
                                  const nextVal = question.scale.length > 0 ? Math.max(...question.scale.map(o => o.value)) + 1 : 1;
                                  const newScale = [...question.scale, { value: nextVal, label: `Opțiune ${nextVal}` }];
                                  handleUpdateQuestion(sIndex, qIndex, { scale: newScale });
                                }}
                                className="tap-soft rounded-lg border border-dashed border-[var(--border)] px-2.5 py-1 text-[11px] font-bold text-foreground/60 hover:border-burgundy/45 hover:text-burgundy"
                              >
                                + Adaugă scor
                              </button>
                            </div>
                          </div>

                          {/* Statement list for statement_score_set */}
                          {question.type === "statement_score_set" && (
                            <div className="border-t border-[var(--border)] pt-3 space-y-2.5">
                              <div className="flex justify-between items-center">
                                <p className="text-[10px] font-bold uppercase tracking-wider text-foreground/50">
                                  Afirmații în set
                                </p>
                                <button
                                  onClick={() => handleAddStatement(sIndex, qIndex)}
                                  className="text-[11px] font-bold text-burgundy hover:underline"
                                >
                                  + Adaugă Afirmație
                                </button>
                              </div>

                              <div className="space-y-2">
                                {(question.statements || []).map((statement, stmtIndex) => (
                                  <div key={statement.id} className="flex gap-2 items-center">
                                    <span className="text-xs font-bold text-foreground/50 w-8 text-right">
                                      {statement.code}
                                    </span>
                                    <input
                                      type="text"
                                      value={statement.label}
                                      onChange={(e) =>
                                        handleUpdateStatementLabel(sIndex, qIndex, stmtIndex, e.target.value)
                                      }
                                      placeholder="Ex. Îmi place să organizez planuri clare..."
                                      className="flex-1 rounded-md border border-[var(--border)] bg-background px-3 py-1 text-xs font-semibold text-foreground"
                                    />
                                    <button
                                      onClick={() => handleDeleteStatement(sIndex, qIndex, stmtIndex)}
                                      className={`${destructiveButtonClass} px-2`}
                                      title="Șterge afirmația"
                                    >
                                      Șterge
                                    </button>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              ))}
            </div>
          </section>
        ) : (
          <div className="rounded-2xl border border-[var(--border)] bg-surface p-10 text-center shadow-sm">
            <p className="text-lg font-bold text-foreground">Catalog gol</p>
            <p className="mt-2 text-sm leading-6 text-foreground/60">
              Faceți click pe Nou.
            </p>
          </div>
        )}
      </main>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-4">
          <form
            onSubmit={handleAddQuestionnaire}
            className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-surface p-6 shadow-xl space-y-4"
          >
            <h3 className="text-lg font-bold text-foreground">Adaugă Chestionar Nou</h3>
            
            <div className="space-y-1">
              <label className="text-xs font-bold text-foreground/60">Cod Unic (Slug, litere mici/cifre)</label>
              <input
                type="text"
                required
                value={newKey}
                onChange={(e) => setNewKey(e.target.value)}
                placeholder="Ex. pcm_profil"
                className="w-full rounded-xl border border-[var(--border)] bg-background px-3 py-2 text-sm font-semibold text-foreground focus:border-burgundy"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-bold text-foreground/60">Titlu</label>
              <input
                type="text"
                required
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="Ex. Chestionar Evaluare PCM"
                className="w-full rounded-xl border border-[var(--border)] bg-background px-3 py-2 text-sm font-semibold text-foreground focus:border-burgundy"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-bold text-foreground/60">Descriere</label>
              <textarea
                value={newDescription}
                onChange={(e) => setNewDescription(e.target.value)}
                placeholder="Scurtă descriere a scopului acestui chestionar..."
                rows={2}
                className="w-full rounded-xl border border-[var(--border)] bg-background px-3 py-2 text-sm font-semibold text-foreground focus:border-burgundy"
              />
            </div>

            <div className="space-y-1">
              <label className="text-xs font-bold text-foreground/60">Audiență Target</label>
              <select
                value={newAudience}
                onChange={(e) => setNewAudience(e.target.value as "leadership" | "team" | "participant")}
                className="w-full rounded-xl border border-[var(--border)] bg-background px-3 py-2 text-sm font-semibold text-foreground focus:border-burgundy"
              >
                <option value="team">Echipă (ex. Lencioni)</option>
                <option value="leadership">Lideri (ex. Distress Drivers, PCM)</option>
                <option value="participant">Individual (ex. 360 Feedback)</option>
              </select>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-[var(--border)]">
              <button
                type="button"
                onClick={() => setShowCreateModal(false)}
                className="tap-soft rounded-lg border border-[var(--border)] bg-background px-4 py-2 text-xs font-bold text-foreground hover:bg-surface-muted"
              >
                Anulează
              </button>
              <button
                type="submit"
                className="tap-soft rounded-lg bg-burgundy px-4 py-2 text-xs font-bold text-white hover:bg-burgundy/90"
              >
                Creează
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
