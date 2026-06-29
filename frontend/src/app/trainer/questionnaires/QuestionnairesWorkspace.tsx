"use client";

import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  listQuestionnaireDefinitionStubs,
  latestDefinitionStubs,
  groupQuestionnaireStubsByKey,
  getQuestionnaireDefinition,
  createQuestionnaireDefinitionOnServer,
  updateQuestionnaireDefinitionOnServer,
  deleteQuestionnaireDefinitionOnServer,
  type QuestionnaireDefinitionStub,
  type QuestionnaireDefinition,
  type QuestionnaireQuestion,
  type QuestionnaireScaleOption,
} from "@/api/questionnaires";

const destructiveButtonClass =
  "tap-soft rounded-full border border-[#890505]/35 bg-transparent px-3 py-1.5 text-xs font-bold text-[#890505] shadow-none transition hover:bg-[#890505]/10 disabled:cursor-not-allowed disabled:border-[var(--border)] disabled:bg-transparent disabled:text-foreground/35 dark:border-[#e35f5f]/45 dark:text-[#e35f5f] dark:hover:bg-[#890505]/22";

type SaveState = "idle" | "saving" | "saved" | "error";

function estimateQuestionnaireItems(definition: QuestionnaireDefinition): number {
  return definition.schema.sections.reduce((count, section) => {
    return (
      count +
      section.questions.reduce((sectionCount, question) => {
        return sectionCount + (question.statements?.length ?? 1);
      }, 0)
    );
  }, 0);
}

function cloneScale(scale: QuestionnaireScaleOption[]): QuestionnaireScaleOption[] {
  return scale.map((option) => ({ ...option }));
}

function scaleSignature(scale: QuestionnaireScaleOption[]): string {
  return JSON.stringify(
    scale.map((option) => ({
      value: option.value,
      label: option.label,
      description: option.description ?? "",
    })),
  );
}

type ScaleGroup = {
  key: string;
  renderKey: string;
  type: QuestionnaireQuestion["type"];
  title: string;
  questionCount: number;
  scale: QuestionnaireScaleOption[];
};

export function QuestionnairesWorkspace() {
  const [stubs, setStubs] = useState<QuestionnaireDefinitionStub[]>([]);
  const [versionStubs, setVersionStubs] = useState<QuestionnaireDefinitionStub[]>([]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<number>(1);
  const [availableVersions, setAvailableVersions] = useState<number[]>([]);
  const [currentDefinition, setCurrentDefinition] = useState<QuestionnaireDefinition | null>(null);
  const [isCatalogLoading, setIsCatalogLoading] = useState<boolean>(false);
  const [isDefinitionLoading, setIsDefinitionLoading] = useState<boolean>(false);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [isDirty, setIsDirty] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [customCategories, setCustomCategories] = useState<string[]>([]);
  const selectedKeyRef = useRef<string | null>(null);
  const currentDefinitionRef = useRef<QuestionnaireDefinition | null>(null);
  const persistedDefinitionRef = useRef<QuestionnaireDefinition | null>(null);
  const definitionRequestRef = useRef(0);
  const saveRequestRef = useRef(0);

  useEffect(() => {
    selectedKeyRef.current = selectedKey;
  }, [selectedKey]);

  const versionStubsByKey = useMemo(() => groupQuestionnaireStubsByKey(versionStubs), [versionStubs]);
  const latestStubByKey = useMemo(() => {
    const latestByKey = new Map<string, QuestionnaireDefinitionStub>();
    for (const stub of stubs) {
      latestByKey.set(stub.id, stub);
    }
    return latestByKey;
  }, [stubs]);
  const categories = useMemo(
    () => Array.from(new Set([...versionStubsByKey.keys(), ...customCategories])).sort(),
    [customCategories, versionStubsByKey],
  );

  // New Questionnaire Modal State
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newKey, setNewKey] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newAudience, setNewAudience] = useState<"leadership" | "team" | "participant">("team");

  // Search State
  const [searchQuery, setSearchQuery] = useState("");
  const [expandedLocalScaleIds, setExpandedLocalScaleIds] = useState<Set<string>>(new Set());

  const filteredStubs = useMemo(() => {
    if (!searchQuery.trim()) return stubs;
    const q = searchQuery.toLowerCase();
    return stubs.filter(s => 
      (s.name && s.name.toLowerCase().includes(q)) || 
      (s.id && s.id.toLowerCase().includes(q))
    );
  }, [stubs, searchQuery]);

  // Load stubs list
  const loadStubs = useCallback(async () => {
    setIsCatalogLoading(true);
    try {
      const allVersions = await listQuestionnaireDefinitionStubs(true, { latestOnly: false });
      setVersionStubs(allVersions);
      setStubs(latestDefinitionStubs(allVersions));
    } finally {
      setIsCatalogLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadStubs();
  }, [loadStubs]);

  // Sync available versions and load definition details when selected key or version changes
  useEffect(() => {
    if (!selectedKey) return;

    const allVersions: number[] =
      versionStubsByKey
        .get(selectedKey)
        ?.map((s) => s.version)
        .filter((v): v is number => typeof v === "number") ?? [];

    if (allVersions.length === 0) {
      allVersions.push(1);
    }

    setAvailableVersions(allVersions);

    // If selectedVersion is not in the list, set to the highest version
    if (!allVersions.includes(selectedVersion)) {
      setSelectedVersion(allVersions[0]);
    }
  }, [selectedKey, selectedVersion, versionStubsByKey]);

  useEffect(() => {
    if (!selectedKey) {
      currentDefinitionRef.current = null;
      setCurrentDefinition(null);
      return;
    }
    const requestId = definitionRequestRef.current + 1;
    definitionRequestRef.current = requestId;

    const fetchDefinition = async () => {
      setIsDefinitionLoading(true);
      try {
        const def = await getQuestionnaireDefinition(`${selectedKey}@${selectedVersion}`);
        if (definitionRequestRef.current !== requestId) return;
        currentDefinitionRef.current = def;
        persistedDefinitionRef.current = def;
        setCurrentDefinition(def);
        setSaveState("idle");
        setIsDirty(false);
        setSaveError(null);
      } finally {
        if (definitionRequestRef.current === requestId) {
          setIsDefinitionLoading(false);
        }
      }
    };
    void fetchDefinition();
  }, [selectedKey, selectedVersion]);

  const applyDefinitionDraft = (updatedDef: QuestionnaireDefinition) => {
    setCurrentDefinition(updatedDef);
    currentDefinitionRef.current = updatedDef;
    setIsDirty(true);
    setSaveState("idle");
    setSaveError(null);
    setStubs((previousStubs) =>
      previousStubs.map((stub) =>
        stub.id === updatedDef.key && (stub.version ?? 1) === updatedDef.version
          ? {
              ...stub,
              name: updatedDef.title,
              description: updatedDef.description,
              audience: updatedDef.schema.audience ?? stub.audience,
              estimatedItems: estimateQuestionnaireItems(updatedDef),
            }
          : stub,
      ),
    );
    setVersionStubs((previousStubs) =>
      previousStubs.map((stub) =>
        stub.id === updatedDef.key && (stub.version ?? 1) === updatedDef.version
          ? {
              ...stub,
              name: updatedDef.title,
              description: updatedDef.description,
              audience: updatedDef.schema.audience ?? stub.audience,
              estimatedItems: estimateQuestionnaireItems(updatedDef),
            }
          : stub,
      ),
    );
  };

  const handleSaveDraft = async () => {
    const draft = currentDefinitionRef.current;
    if (!draft || saveState === "saving" || !isDirty) return;
    const requestId = saveRequestRef.current + 1;
    saveRequestRef.current = requestId;
    setSaveState("saving");
    setSaveError(null);
    try {
      const saved = await updateQuestionnaireDefinitionOnServer(
        draft.key,
        {
          title: draft.title,
          description: draft.description,
          schema: draft.schema,
        },
        draft.version,
      );
      if (saveRequestRef.current !== requestId) return;
      currentDefinitionRef.current = saved;
      persistedDefinitionRef.current = saved;
      setCurrentDefinition(saved);
      setIsDirty(false);
      setSaveState("saved");
      setStubs((previousStubs) =>
        previousStubs.map((stub) =>
          stub.id === saved.key && (stub.version ?? 1) === saved.version
            ? {
                ...stub,
                name: saved.title,
                description: saved.description,
                audience: saved.schema.audience ?? stub.audience,
                estimatedItems: estimateQuestionnaireItems(saved),
              }
            : stub,
        ),
      );
      setVersionStubs((previousStubs) =>
        previousStubs.map((stub) =>
          stub.id === saved.key && (stub.version ?? 1) === saved.version
            ? {
                ...stub,
                name: saved.title,
                description: saved.description,
                audience: saved.schema.audience ?? stub.audience,
                estimatedItems: estimateQuestionnaireItems(saved),
              }
            : stub,
        ),
      );
    } catch (error) {
      if (saveRequestRef.current === requestId) {
        setSaveState("error");
        setSaveError(error instanceof Error ? error.message : "Chestionarul nu a putut fi salvat.");
      }
    }
  };

  const handleDiscardDraft = () => {
    const persisted = persistedDefinitionRef.current;
    if (!persisted) return;
    currentDefinitionRef.current = persisted;
    setCurrentDefinition(persisted);
    setIsDirty(false);
    setSaveState("idle");
    setSaveError(null);
    setStubs((previousStubs) =>
      previousStubs.map((stub) =>
        stub.id === persisted.key && (stub.version ?? 1) === persisted.version
          ? {
              ...stub,
              name: persisted.title,
              description: persisted.description,
              audience: persisted.schema.audience ?? stub.audience,
              estimatedItems: estimateQuestionnaireItems(persisted),
            }
          : stub,
      ),
    );
    setVersionStubs((previousStubs) =>
      previousStubs.map((stub) =>
        stub.id === persisted.key && (stub.version ?? 1) === persisted.version
          ? {
              ...stub,
              name: persisted.title,
              description: persisted.description,
              audience: persisted.schema.audience ?? stub.audience,
              estimatedItems: estimateQuestionnaireItems(persisted),
            }
          : stub,
      ),
    );
  };

  const canDiscardDraftForNavigation = () => {
    if (!isDirty || saveState === "saving") return true;
    return window.confirm("Ai modificări nesalvate. Vrei să le pierzi și să schimbi chestionarul?");
  };

  const handleSelectDefinition = (key: string, version: number) => {
    if (key === selectedKey && version === selectedVersion) return;
    if (!canDiscardDraftForNavigation()) return;
    setSelectedKey(key);
    setSelectedVersion(version);
  };

  const handleSelectVersion = (version: number) => {
    if (version === selectedVersion) return;
    if (!canDiscardDraftForNavigation()) return;
    setSelectedVersion(version);
  };

  const updateDefinitionDraft = (updater: (current: QuestionnaireDefinition) => QuestionnaireDefinition) => {
    const current = currentDefinitionRef.current;
    if (!current) return;
    applyDefinitionDraft(updater(current));
  };

  const handleSaveMetadata = (
    fields: Partial<Pick<QuestionnaireDefinition, "title" | "description">> & {
      audience?: "leadership" | "team" | "participant";
    },
  ) => {
    updateDefinitionDraft((definition) => ({
      ...definition,
      ...fields,
      schema: {
        ...definition.schema,
        audience: fields.audience ?? definition.schema.audience,
      },
    }));
  };

  const handleRenameDefinitionKey = () => {
    alert("Redenumirea cheii nu este permisă pe server. Creează un chestionar nou cu o altă cheie dacă este necesar.");
  };

  const handleCreateNewVersion = async () => {
    const draftDefinition = currentDefinitionRef.current;
    if (!draftDefinition) return;
    setIsDefinitionLoading(true);
    try {
      const saved = await createQuestionnaireDefinitionOnServer({
        key: draftDefinition.key,
        title: draftDefinition.title,
        description: draftDefinition.description,
        schema: draftDefinition.schema,
        active: true,
      });
      setSelectedVersion(saved.version);
      await loadStubs();
    } catch (e) {
      alert((e as Error).message ?? "Eroare la crearea unei noi versiuni.");
    } finally {
      setIsDefinitionLoading(false);
    }
  };

  const handleDeleteQuestionnaire = async () => {
    if (!selectedKey) return;
    const selectedName = currentDefinition?.title ?? selectedKey;
    const confirmed = window.confirm(
      `Pensionați chestionarul "${selectedName}"? Această acțiune îl va marca ca inactiv pe server.`,
    );
    if (!confirmed) return;

    setIsDefinitionLoading(true);
    try {
      await deleteQuestionnaireDefinitionOnServer(selectedKey, selectedVersion);
      const remainingVersions = await listQuestionnaireDefinitionStubs(true, { latestOnly: false });
      const remainingLatest = latestDefinitionStubs(remainingVersions);
      setVersionStubs(remainingVersions);
      setStubs(remainingLatest);
      const nextSelection = remainingLatest.find((stub) => stub.id !== selectedKey) ?? remainingLatest[0];
      if (nextSelection) {
        setSelectedKey(nextSelection.id);
        setSelectedVersion(nextSelection.version ?? 1);
      } else {
        setSelectedKey(null);
        currentDefinitionRef.current = null;
        persistedDefinitionRef.current = null;
        setCurrentDefinition(null);
        setAvailableVersions([]);
      }
    } catch (e) {
      alert((e as Error).message ?? "Eroare la ștergerea/pensionarea chestionarului.");
    } finally {
      setIsDefinitionLoading(false);
    }
  };

  const handleAddQuestionnaire = async (e: FormEvent) => {
    e.preventDefault();
    if (!newKey) return;

    const key = newKey.toLowerCase().replace(/[^a-z0-9_]/g, "_");
    const title = newTitle.trim() || "Chestionar nou";
    setIsCatalogLoading(true);
    try {
      const saved = await createQuestionnaireDefinitionOnServer({
        key,
        title,
        description: newDescription,
        schema: {
          schema_version: "questionnaire.v1",
          audience: newAudience,
          instructions: "Te rugăm să completezi formularul de mai jos.",
          sections: [
            {
              id: "sectiunea_1",
              title: "Secțiunea 1",
              questions: [],
            },
          ],
        },
        active: false,
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
      setIsCatalogLoading(false);
    }
  };

  // Section modifiers
  const handleAddSection = () => {
    updateDefinitionDraft((definition) => {
      const sections = [...definition.schema.sections];
      const newSectionId = `sectiunea_${sections.length + 1}`;
      sections.push({
        id: newSectionId,
        title: `Secțiunea ${sections.length + 1}`,
        questions: [],
      });

      return {
        ...definition,
        schema: {
          ...definition.schema,
          sections,
        },
      };
    });
  };

  const handleUpdateSectionTitle = (sectionIndex: number, title: string) => {
    updateDefinitionDraft((definition) => {
      const sections = [...definition.schema.sections];
      sections[sectionIndex] = {
        ...sections[sectionIndex],
        title,
      };

      return {
        ...definition,
        schema: {
          ...definition.schema,
          sections,
        },
      };
    });
  };

  const handleDeleteSection = (sectionIndex: number) => {
    const definition = currentDefinitionRef.current;
    if (!definition) return;
    if (definition.schema.sections.length <= 1) {
      alert("Chestionarul trebuie să aibă cel puțin o secțiune.");
      return;
    }
    updateDefinitionDraft((current) => {
      const sections = current.schema.sections.filter((_, i) => i !== sectionIndex);
      return {
        ...current,
        schema: {
          ...current.schema,
          sections,
        },
      };
    });
  };

  // Question modifiers
  const handleAddQuestion = (sectionIndex: number) => {
    updateDefinitionDraft((definition) => {
      const sections = [...definition.schema.sections];
      const section = sections[sectionIndex];
      const nextIndex = section.questions.length + 1;
      const questionId = `${definition.key}_s${sectionIndex + 1}_q${nextIndex}_${Date.now().toString().slice(-4)}`;

      const newQuestion: QuestionnaireQuestion = {
        id: questionId,
        code: `Q${nextIndex}`,
        type: "likert",
        label: "Întrebare nouă. Apasă pentru a edita textul.",
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

      return {
        ...definition,
        schema: {
          ...definition.schema,
          sections,
        },
      };
    });
  };

  const handleUpdateQuestion = (
    sectionIndex: number,
    questionIndex: number,
    fields: Partial<QuestionnaireQuestion>
  ) => {
    updateDefinitionDraft((definition) => {
      const sections = [...definition.schema.sections];
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

      return {
        ...definition,
        schema: {
          ...definition.schema,
          sections,
        },
      };
    });
  };

  const handleDeleteQuestion = (sectionIndex: number, questionIndex: number) => {
    updateDefinitionDraft((definition) => {
      const sections = [...definition.schema.sections];
      const section = sections[sectionIndex];
      const questions = section.questions.filter((_, i) => i !== questionIndex);

      sections[sectionIndex] = {
        ...section,
        questions,
      };

      return {
        ...definition,
        schema: {
          ...definition.schema,
          sections,
        },
      };
    });
  };

  // Statement list modifiers for Distress Drivers style statement set questions
  const handleAddStatement = (sectionIndex: number, questionIndex: number) => {
    const definition = currentDefinitionRef.current;
    if (!definition) return;
    const question = definition.schema.sections[sectionIndex].questions[questionIndex];
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
    updateDefinitionDraft((definition) => {
      const sections = [...definition.schema.sections];
      const section = sections[sectionIndex];
      const questions = [...section.questions];
      const question = questions[questionIndex];
      const statements = [...(question.statements || [])];

      statements[statementIndex] = {
        ...statements[statementIndex],
        label,
      };

      questions[questionIndex] = {
        ...question,
        statements,
      };

      sections[sectionIndex] = {
        ...section,
        questions,
      };

      return {
        ...definition,
        schema: {
          ...definition.schema,
          sections,
        },
      };
    });
  };

  const handleDeleteStatement = (sectionIndex: number, questionIndex: number, statementIndex: number) => {
    const definition = currentDefinitionRef.current;
    if (!definition) return;
    const question = definition.schema.sections[sectionIndex].questions[questionIndex];
    const statements = (question.statements || []).filter((_, i) => i !== statementIndex);

    handleUpdateQuestion(sectionIndex, questionIndex, { statements });
  };

  const latestSelectedVersion = selectedKey
    ? (latestStubByKey.get(selectedKey)?.version ?? availableVersions[0])
    : availableVersions[0];
  const scaleGroups = useMemo<ScaleGroup[]>(() => {
    if (!currentDefinition) return [];

    const groups = new Map<string, ScaleGroup>();
    currentDefinition.schema.sections.forEach((section) => {
      section.questions.forEach((question) => {
        if (!question.scale?.length) return;
        const key = `${question.type}:${scaleSignature(question.scale)}`;
        const existing = groups.get(key);
        if (existing) {
          existing.questionCount += 1;
          return;
        }
        groups.set(key, {
          key,
          renderKey: `${question.type}:${section.id}:${question.id}`,
          type: question.type,
          title: question.scale.map((option) => option.label).join(" / "),
          questionCount: 1,
          scale: cloneScale(question.scale),
        });
      });
    });

    return Array.from(groups.values()).sort((a, b) => b.questionCount - a.questionCount);
  }, [currentDefinition]);
  const canDeleteSelected = !!selectedKey;
  const isSaving = saveState === "saving";
  const isEditorLoading = isDefinitionLoading && !currentDefinition;
  const saveStateLabel =
    saveState === "saving"
      ? "Se salvează..."
      : saveState === "saved"
        ? "Salvat"
        : saveState === "error"
          ? "Eroare la salvare"
          : isDirty
            ? "Modificări nesalvate"
            : null;

  const handleUpdateScaleGroup = (
    group: ScaleGroup,
    updater: (scale: QuestionnaireScaleOption[]) => QuestionnaireScaleOption[],
  ) => {
    const previousSignature = scaleSignature(group.scale);
    updateDefinitionDraft((definition) => ({
      ...definition,
      schema: {
        ...definition.schema,
        sections: definition.schema.sections.map((section) => ({
          ...section,
          questions: section.questions.map((question) => {
            if (question.type !== group.type || scaleSignature(question.scale) !== previousSignature) {
              return question;
            }
            return {
              ...question,
              scale: updater(cloneScale(group.scale)),
            };
          }),
        })),
      },
    }));
  };

  const toggleLocalScale = (scaleId: string) => {
    setExpandedLocalScaleIds((current) => {
      const next = new Set(current);
      if (next.has(scaleId)) {
        next.delete(scaleId);
      } else {
        next.add(scaleId);
      }
      return next;
    });
  };

  return (
    <div className="space-y-6">
      {!selectedKey ? (
        // GALLERY MODE
        <div className="space-y-6">
          <div className="filter-toolbar">
            <div className="relative w-full md:flex-1">
              <svg className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-foreground/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0z" />
              </svg>
              <input
                type="text"
                placeholder="Caută chestionar..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="control-input control-search w-full py-3 pl-12 pr-4"
              />
            </div>
            <button
              onClick={() => setShowCreateModal(true)}
              disabled={isCatalogLoading}
              className="btn-primary shrink-0"
            >
              {isCatalogLoading ? "..." : "+ Creează chestionar"}
            </button>
          </div>

          {isCatalogLoading ? (
            <div className="flex items-center justify-center h-64 rounded-xl border border-[var(--border)] bg-surface">
              <p className="text-sm font-semibold text-foreground/50">Se încarcă catalogul...</p>
            </div>
          ) : filteredStubs.length > 0 ? (
            <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
              {filteredStubs.map((stub) => (
                <article
                  key={`${stub.id}-${stub.version ?? "fără-versiune"}`}
                  role="button"
                  tabIndex={0}
                  onClick={() => handleSelectDefinition(stub.id, stub.version ?? 1)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      handleSelectDefinition(stub.id, stub.version ?? 1);
                    }
                  }}
                  aria-label={`Editează ${stub.name}`}
                  className="group flex cursor-pointer flex-col rounded-xl border border-[var(--border)] bg-surface p-6 text-left shadow-sm transition-colors hover:border-burgundy/25 focus:outline-none focus:ring-2 focus:ring-burgundy/30"
                >
                  <div className="flex h-full flex-col">
                    <div className="flex items-start justify-between mb-4">
                      <span className={`rounded-full border px-2 py-1 text-[10px] font-bold uppercase tracking-[0.2em] ${
                        stub.audience === "team"
                          ? "text-blue-700 bg-blue-50 border-blue-200 dark:bg-blue-900/30 dark:text-blue-300 dark:border-blue-800/50"
                          : stub.audience === "leadership"
                            ? "text-purple-700 bg-purple-50 border-purple-200 dark:bg-purple-900/30 dark:text-purple-300 dark:border-purple-800/50"
                            : "text-emerald-700 bg-emerald-50 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-800/50"
                      }`}>
                        {stub.audience}
                      </span>
                      <span className="rounded-full border border-[var(--border)] bg-surface-muted px-2 py-0.5 text-[10px] font-bold text-foreground/60">
                        v{stub.version ?? 1}
                      </span>
                    </div>
                    <h4 className="font-bold text-lg text-foreground mb-2 group-hover:text-burgundy transition-colors line-clamp-1">
                      {stub.name}
                    </h4>
                    <p className="text-sm text-foreground/60 mb-6 line-clamp-2 min-h-[2.5rem]">
                      {stub.description || "Fără descriere. Apasă pentru a edita detaliile."}
                    </p>
                    <div className="mt-auto pt-4 border-t border-[var(--border)] flex items-center justify-between text-xs font-semibold text-foreground/50">
                      <span>{stub.estimatedItems ?? "TBD"} întrebări</span>
                      <span className="capitalize">{stub.status}</span>
                    </div>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <div className="surface-panel-muted flex min-h-[40vh] flex-col items-center justify-center p-12 text-center">
              <p className="text-xl font-bold text-foreground">Catalog gol</p>
              <p className="mt-3 text-sm leading-relaxed text-foreground/60 max-w-md mx-auto">
                Nu s-au găsit chestionare. Apasă pe butonul de mai sus pentru a crea unul nou.
              </p>
            </div>
          )}
        </div>
      ) : (
        // EDIT MODE
        <div className="space-y-6">
          {/* Editor Header / Back Button */}
          <div className="flex items-center gap-4">
            <button
              onClick={() => {
                if (canDiscardDraftForNavigation()) {
                  setSelectedKey(null);
                  currentDefinitionRef.current = null;
                  setCurrentDefinition(null);
                }
              }}
              className="tap-soft rounded-full bg-surface px-4 py-2 text-sm font-bold text-foreground border border-[var(--border)] hover:bg-surface-muted hover:border-burgundy/30 transition-all flex items-center gap-2"
            >
              <span className="text-burgundy/70">&larr;</span> Înapoi la catalog
            </button>
          </div>
          
          {/* Main Content Area */}
          <main className="space-y-5">
            {isEditorLoading ? (
              <div className="flex h-64 items-center justify-center rounded-xl border border-[var(--border)] bg-surface">
                <p className="text-sm font-semibold text-foreground/50">Se încarcă detaliile chestionarului...</p>
              </div>
            ) : currentDefinition ? (
              <section className="surface-panel space-y-7 p-5 md:p-6">
                <div className="space-y-6">
              {/* Header info card */}
              <div className="grid gap-5 border-b border-[var(--border)] pb-6 xl:grid-cols-[minmax(0,1fr)_auto]">
                <div className="min-w-0 space-y-4">
                  <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full border border-[#890505]/35 bg-[#890505]/10 px-2.5 py-1 text-xs font-bold text-[#890505] shadow-none dark:border-[#e35f5f]/45 dark:bg-[#890505]/22 dark:text-[#e35f5f]">
                    Audiență: {currentDefinition.schema.audience ?? (currentDefinition.key === "distress_drivers" ? "leadership" : "team")}
                  </span>
                  <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-bold text-foreground/60 border border-[var(--border)]">
                    {canDeleteSelected ? "Local editabil" : "Definiție de bază"}
                  </span>
                  {saveStateLabel ? (
                    <span
                      className={`rounded-full border px-2.5 py-1 text-xs font-bold ${
                        saveState === "error"
                          ? "border-[#890505]/35 bg-[#890505]/10 text-[#890505] dark:border-[#e35f5f]/45 dark:bg-[#890505]/22 dark:text-[#e35f5f]"
                          : isDirty
                            ? "border-amber-500/35 bg-amber-500/10 text-amber-700 dark:text-amber-300"
                          : "border-success/25 bg-success/12 text-success-ink"
                      }`}
                    >
                      {saveStateLabel}
                    </span>
                  ) : null}
                </div>

                <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_15rem]">
                  <label className="space-y-1.5">
                    <span className="text-xs font-bold uppercase tracking-wider text-foreground/50">Nume chestionar</span>
                    <input
                      value={currentDefinition.title}
                      onChange={(e) => handleSaveMetadata({ title: e.target.value })}
                      className="control-input w-full py-3 text-lg"
                    />
                  </label>
                  <label className="space-y-1.5">
                    <span className="text-xs font-bold uppercase tracking-wider text-foreground/50">Categorie / Slug</span>
                    <select
                      value={currentDefinition.key}
                      onChange={handleRenameDefinitionKey}
                      className="control-input w-full py-3"
                    >
                      {categories.map((cat) => (
                        <option key={cat} value={cat}>
                          {cat}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                <label className="block space-y-1.5">
                  <span className="text-xs font-bold uppercase tracking-wider text-foreground/50">Descriere</span>
                  <textarea
                    value={currentDefinition.description}
                    onChange={(e) => handleSaveMetadata({ description: e.target.value })}
                    rows={2}
                    className="control-input w-full py-3 leading-6"
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
                    className="control-input w-full px-3 py-2 text-xs xl:w-48"
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
                    onChange={(e) => handleSelectVersion(Number(e.target.value))}
                    className="control-input w-full px-3 py-2 text-xs xl:w-48"
                  >
                    {availableVersions.map((v) => (
                      <option key={v} value={v}>
                        v{v} {v === latestSelectedVersion ? "(Activă)" : "(Veche)"}
                      </option>
                    ))}
                  </select>
                </label>
                <div className="flex flex-wrap gap-2 xl:justify-end">
                  <button
                    type="button"
                    onClick={() => void handleSaveDraft()}
                    disabled={!isDirty || isSaving || isDefinitionLoading}
                    className="btn-primary !px-4 !py-2 !text-xs !rounded-full"
                  >
                    {isSaving ? "Se salvează..." : "Salvează modificările"}
                  </button>
                  <button
                    type="button"
                    onClick={handleDiscardDraft}
                    disabled={!isDirty || isSaving || isDefinitionLoading}
                    className="tap-soft rounded-full border border-[var(--border)] bg-surface px-3 py-1.5 text-xs font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy disabled:cursor-not-allowed disabled:opacity-45"
                  >
                    Revino la ultima versiune salvată
                  </button>
                </div>
                {saveError ? (
                  <p className="max-w-xs text-xs font-semibold leading-5 text-[#890505] dark:text-[#e35f5f]">
                    {saveError}
                  </p>
                ) : null}
                <div className="flex flex-wrap gap-2 xl:justify-end">
                  <button
                    onClick={handleCreateNewVersion}
                    disabled={isSaving || isDefinitionLoading}
                    className="tap-soft rounded-full border border-[var(--border)] bg-surface px-3 py-1.5 text-xs font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy disabled:cursor-not-allowed disabled:text-foreground/35"
                  >
                    Versiune nouă (clonează)
                  </button>
                  <button
                    onClick={handleDeleteQuestionnaire}
                    disabled={!canDeleteSelected || isSaving || isDefinitionLoading}
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
                Instrucțiuni chestionar
              </label>
              <textarea
                value={currentDefinition.schema.instructions ?? ""}
                onChange={(e) =>
                  updateDefinitionDraft((definition) => ({
                    ...definition,
                    schema: { ...definition.schema, instructions: e.target.value },
                  }))
                }
                rows={2}
                className="control-input w-full py-3"
                placeholder="Instrucțiuni prezentate utilizatorului..."
              />
            </div>

            {scaleGroups.length > 0 ? (
              <section className="rounded-xl border border-[var(--border)] bg-surface p-4 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-bold text-foreground">Scări globale de răspuns</h3>
                    <p className="mt-1 max-w-2xl text-xs leading-5 text-foreground/52">
                      Editează aici opțiunile folosite în mai multe întrebări. Modificările se aplică tuturor
                      întrebărilor care au exact aceeași scară.
                    </p>
                  </div>
                  <span className="rounded-xl border border-[var(--border)] bg-background px-2.5 py-1 text-[11px] font-bold text-foreground/55">
                    {scaleGroups.length} {scaleGroups.length === 1 ? "scară" : "scări"}
                  </span>
                </div>
                <div className="mt-4 grid gap-3">
                  {scaleGroups.map((group) => (
                    <div key={group.renderKey} className="rounded-xl border border-[var(--border)] bg-surface p-3 shadow-sm">
                      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-xs font-bold text-foreground">{group.title}</p>
                          <p className="mt-0.5 text-[11px] font-semibold text-foreground/45">
                            {group.questionCount} {group.questionCount === 1 ? "întrebare" : "întrebări"} ·{" "}
                            {group.type === "statement_score_set" ? "set de afirmații" : "Likert"}
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={() =>
                            handleUpdateScaleGroup(group, (scale) => {
                              const numericValues = scale
                                .map((option) => option.value)
                                .filter((value): value is number => typeof value === "number");
                              const nextValue = numericValues.length > 0 ? Math.max(...numericValues) + 1 : 1;
                              return [...scale, { value: nextValue, label: `Opțiune ${nextValue}` }];
                            })
                          }
                          className="tap-soft rounded-full border border-dashed border-[var(--border)] px-2.5 py-1 text-[11px] font-bold text-foreground/60 hover:border-burgundy/45 hover:text-burgundy"
                        >
                          + Adaugă opțiune
                        </button>
                      </div>
                      <div className="grid gap-2">
                        {group.scale.map((option, optionIndex) => (
                          <div
                            key={`${group.renderKey}-${optionIndex}`}
                            className="grid gap-2 rounded-xl border border-[var(--border)] bg-background px-2.5 py-2 text-xs md:grid-cols-[3rem_10rem_minmax(0,1fr)_2rem] md:items-center"
                          >
                            <span className="font-bold text-burgundy">{option.value}</span>
                            <input
                              type="text"
                              value={option.label}
                              onChange={(event) =>
                                handleUpdateScaleGroup(group, (scale) => {
                                  scale[optionIndex] = { ...scale[optionIndex], label: event.target.value };
                                  return scale;
                                })
                              }
                              className="rounded-xl border border-[var(--border)] bg-surface px-2 py-1 font-semibold text-foreground/75 focus:border-burgundy/45 focus:outline-none"
                              placeholder="Etichetă"
                            />
                            <input
                              type="text"
                              value={option.description ?? ""}
                              onChange={(event) =>
                                handleUpdateScaleGroup(group, (scale) => {
                                  scale[optionIndex] = {
                                    ...scale[optionIndex],
                                    description: event.target.value || undefined,
                                  };
                                  return scale;
                                })
                              }
                              className="rounded-xl border border-[var(--border)] bg-surface px-2 py-1 font-medium text-foreground/70 focus:border-burgundy/45 focus:outline-none"
                              placeholder="Descriere opțională"
                            />
                            <button
                              type="button"
                              onClick={() =>
                                handleUpdateScaleGroup(group, (scale) => scale.filter((_, index) => index !== optionIndex))
                              }
                              className="tap-soft inline-flex h-8 w-8 items-center justify-center rounded-full text-foreground/40 hover:bg-red-500/10 hover:text-red-700"
                              aria-label={`Șterge opțiunea ${option.label}`}
                            >
                              ×
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </section>
            ) : null}

            {/* Sections & Questions Editor */}
            <div className="space-y-5">
              <div className="flex items-center justify-between border-b border-[var(--border)] pb-2">
                <h3 className="text-base font-bold text-foreground">Secțiuni ({currentDefinition.schema.sections.length})</h3>
                <button
                  onClick={handleAddSection}
                  className="btn-primary !px-4 !py-2 !text-xs !rounded-full"
                >
                  + Adaugă secțiune
                </button>
              </div>

              {currentDefinition.schema.sections.map((section, sIndex) => (
                <div key={section.id} className="rounded-xl border border-[var(--border)] bg-surface p-4 space-y-4 shadow-sm">
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
                        className="tap-soft rounded-full bg-burgundy/10 border border-burgundy/20 px-3 py-1.5 text-xs font-bold text-burgundy hover:bg-burgundy/20"
                      >
                        + Adaugă întrebare
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
                        Nicio întrebare în această secțiune. Apasă pe butonul de mai sus pentru a adăuga una.
                      </p>
                    ) : (
                      section.questions.map((question, qIndex) => (
	                        <div
	                          key={question.id}
	                          data-testid={`question-editor-${question.id}`}
	                          className="rounded-xl border border-[var(--border)] bg-surface p-4 space-y-3 shadow-sm"
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
                                className="w-16 rounded-xl border border-[var(--border)] bg-background px-2 py-1 text-xs font-bold text-foreground text-center"
                              />
                              <input
                                type="text"
                                value={question.label}
                                onChange={(e) =>
                                  handleUpdateQuestion(sIndex, qIndex, { label: e.target.value })
                                }
                                placeholder="Textul întrebării"
                                className="flex-1 rounded-xl border border-[var(--border)] bg-background px-3 py-1 text-xs font-semibold text-foreground"
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
                                className="rounded-xl border border-[var(--border)] bg-background px-2.5 py-1 text-xs font-semibold text-foreground"
                              >
                                <option value="likert">Scările Likert</option>
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
                              className="w-full rounded-xl border border-[var(--border)] bg-background px-3 py-1.5 text-xs font-semibold text-foreground/75 focus:border-burgundy/45"
                            />
                          </div>

                          {/* Likert Scale configuration */}
                          <div className="border-t border-[var(--border)] pt-3">
                            {(() => {
                              const scalePanelId = `${section.id}:${question.id}`;
                              const isExpanded = expandedLocalScaleIds.has(scalePanelId);
                              const scalePreview = question.scale
                                .slice(0, 4)
                                .map((option) => option.label)
                                .join(" / ");
                              return (
                                <div className="rounded-xl border border-[var(--border)] bg-background px-3 py-3">
                                  <div className="flex flex-wrap items-center justify-between gap-3">
                                    <div className="min-w-0">
                                      <p className="text-[10px] font-bold uppercase tracking-wider text-foreground/50">
                                        Scară locală
                                      </p>
                                      <p className="mt-1 truncate text-xs font-semibold text-foreground/65">
                                        {question.scale.length} opțiuni · {scalePreview}
                                        {question.scale.length > 4 ? " / ..." : ""}
                                      </p>
                                    </div>
                                    <button
                                      type="button"
                                      onClick={() => toggleLocalScale(scalePanelId)}
                                      className="tap-soft rounded-full border border-[var(--border)] bg-surface px-3 py-1.5 text-[11px] font-bold text-foreground/60 hover:border-burgundy/45 hover:text-burgundy"
                                      aria-expanded={isExpanded}
                                    >
                                      {isExpanded ? "Ascunde scara" : "Editează scara locală"}
                                    </button>
                                  </div>

                                  {isExpanded ? (
                                    <div className="mt-3 grid gap-2">
                                      {question.scale.map((opt, optIndex) => (
                                        <div key={optIndex} className="grid gap-2 rounded-xl border border-[var(--border)] bg-surface px-2.5 py-2 text-xs md:grid-cols-[3rem_10rem_minmax(0,1fr)_2rem] md:items-center">
                                          <span className="font-bold text-burgundy">{opt.value}</span>
                                          <input
                                            type="text"
                                            value={opt.label}
                                            onChange={(e) => {
                                              const newScale = [...question.scale];
                                              newScale[optIndex] = { ...newScale[optIndex], label: e.target.value };
                                              handleUpdateQuestion(sIndex, qIndex, { scale: newScale });
                                            }}
                                            className="rounded-xl border border-[var(--border)] bg-background px-2 py-1 font-semibold text-foreground/75 focus:border-burgundy/45 focus:outline-none text-xs"
                                            placeholder="Etichetă"
                                          />
                                          <input
                                            type="text"
                                            value={opt.description ?? ""}
                                            onChange={(e) => {
                                              const newScale = [...question.scale];
                                              newScale[optIndex] = { ...newScale[optIndex], description: e.target.value || undefined };
                                              handleUpdateQuestion(sIndex, qIndex, { scale: newScale });
                                            }}
                                            className="rounded-xl border border-[var(--border)] bg-background px-2 py-1 font-medium text-foreground/70 focus:border-burgundy/45 focus:outline-none text-xs"
                                            placeholder="Descriere opțională pentru această opțiune"
                                          />
                                          <button
                                            type="button"
                                            onClick={() => {
                                              const newScale = question.scale.filter((_, i) => i !== optIndex);
                                              handleUpdateQuestion(sIndex, qIndex, { scale: newScale });
                                            }}
                                            className="tap-soft inline-flex h-8 w-8 items-center justify-center rounded-full text-foreground/40 hover:bg-red-500/10 hover:text-red-700"
                                            aria-label={`Șterge opțiunea ${opt.label}`}
                                          >
                                            ×
                                          </button>
                                        </div>
                                      ))}
                                      <button
                                        type="button"
                                        onClick={() => {
                                          const numericValues = question.scale
                                            .map((option) => option.value)
                                            .filter((value): value is number => typeof value === "number");
                                          const nextVal = numericValues.length > 0 ? Math.max(...numericValues) + 1 : 1;
                                          const newScale = [...question.scale, { value: nextVal, label: `Opțiune ${nextVal}` }];
                                          handleUpdateQuestion(sIndex, qIndex, { scale: newScale });
                                        }}
                                        className="tap-soft justify-self-start rounded-full border border-dashed border-[var(--border)] px-2.5 py-1 text-[11px] font-bold text-foreground/60 hover:border-burgundy/45 hover:text-burgundy"
                                      >
                                        + Adaugă scor
                                      </button>
                                    </div>
                                  ) : null}
                                </div>
                              );
                            })()}
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
                                  className="tap-soft rounded-full border border-burgundy/20 bg-burgundy/10 px-3 py-1.5 text-[11px] font-bold text-burgundy hover:bg-burgundy/20"
                                >
                                  + Adaugă afirmație
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
                                      className="flex-1 rounded-xl border border-[var(--border)] bg-background px-3 py-1 text-xs font-semibold text-foreground"
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
            </div>
          </section>
        ) : null}
          </main>
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <form
            onSubmit={handleAddQuestionnaire}
            className="w-full max-w-md rounded-xl border border-[var(--border)] bg-surface p-6 shadow-xl space-y-4"
          >
            <h3 className="text-lg font-bold text-foreground">Adaugă chestionar nou</h3>
            
            <div className="space-y-1">
              <label className="text-xs font-bold text-foreground/60">Cod unic (slug / categorie)</label>
              <div className="flex gap-2">
                <select
                  value={newKey}
                  onChange={(e) => setNewKey(e.target.value)}
                  className="flex-1 rounded-xl border border-[var(--border)] bg-background px-3 py-2 text-sm font-semibold text-foreground focus:border-burgundy"
                  required
                >
                  <option value="">Alege o categorie...</option>
                  {categories.map((cat) => (
                    <option key={cat} value={cat}>
                      {cat}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  onClick={() => {
                    const name = prompt("Introduceți codul categoriei noi (litere mici, cifre, sublinieri):");
                    if (name) {
                      const cleanName = name.toLowerCase().replace(/[^a-z0-9_]/g, "_");
                      if (cleanName && !categories.includes(cleanName)) {
                        setCustomCategories((previous) => [...previous, cleanName]);
                        setNewKey(cleanName);
                      }
                    }
                  }}
                  className="tap-soft rounded-full bg-burgundy/10 px-3 text-xs font-bold text-burgundy border border-burgundy/20 hover:bg-burgundy/20"
                >
                  + Adaugă
                </button>
                <button
                  type="button"
                  onClick={() => {
                    if (newKey && window.confirm(`Ștergeți categoria "${newKey}" din listă?`)) {
                      setCustomCategories((previous) => previous.filter((cat) => cat !== newKey));
                      setNewKey("");
                    }
                  }}
                  className="tap-soft rounded-full bg-[#890505]/10 border border-[#890505]/20 px-3 text-xs font-bold text-[#890505] hover:bg-[#890505]/20"
                  disabled={!newKey}
                >
                  Șterge
                </button>
              </div>
            </div>

            <div className="space-y-1">
              <label className="text-xs font-bold text-foreground/60">Titlu</label>
              <input
                type="text"
                value={newTitle}
                onChange={(e) => setNewTitle(e.target.value)}
                placeholder="Chestionar nou"
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
              <label className="text-xs font-bold text-foreground/60">Audiență țintă</label>
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
                className="tap-soft rounded-full border border-[var(--border)] bg-background px-4 py-2 text-xs font-bold text-foreground hover:bg-surface-muted"
              >
                Anulează
              </button>
              <button
                type="submit"
                className="btn-primary !px-4 !py-2 !text-xs !rounded-full"
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
