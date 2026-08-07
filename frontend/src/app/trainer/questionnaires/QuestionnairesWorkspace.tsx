"use client";

import type { FormEvent } from "react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2Icon, PlusIcon } from "lucide-react";
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
  type QuestionnaireStatement,
} from "@/api/questionnaires";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { OperationFeedback } from "@/components/presentation/operation-feedback";
import {
  CatalogCard,
  CatalogToolbar,
  type CatalogStatusTone,
} from "@/components/presentation/catalog-card";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ModalLayer } from "@/components/ui/modal-layer";
import { SearchField } from "@/components/ui/search-field";
import { SelectControl } from "@/components/ui/select-control";
import { Textarea } from "@/components/ui/textarea";
import { useUrlState } from "@/hooks/use-url-state";
import {
  QuestionnaireEditor,
  type QuestionnaireScaleGroup,
} from "./QuestionnaireEditor";

type SaveState = "idle" | "saving" | "saved" | "error";

const AUDIENCE_LABELS: Record<string, string> = {
  leadership: "Leadership",
  participant: "Individual",
  team: "Echipă",
};

const QUESTIONNAIRE_STATUS_LABELS: Record<string, string> = {
  active: "Activ",
  draft: "Ciornă",
  inactive: "Inactiv",
  retired: "Pensionat",
};

function questionnaireStatusTone(status: string): CatalogStatusTone {
  if (status === "active") return "success";
  if (status === "draft") return "warning";
  return "neutral";
}

type ConfirmDialogState = {
  title: string;
  description: string;
  confirmLabel: string;
  tone?: "default" | "danger";
  onConfirm: () => void | Promise<void>;
};

function parseQuestionnaireVersion(value: string | null): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 1;
}

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

function hasStatementSpecificScales(question: QuestionnaireQuestion): boolean {
  return (
    question.type === "statement_score_set" &&
    (question.statements?.length ?? 0) > 0 &&
    question.statements?.every((statement) => (statement.scale?.length ?? 0) > 0) === true
  );
}

export function QuestionnairesWorkspace() {
  const { get, searchKey, setParam, setParams } = useUrlState();
  const [stubs, setStubs] = useState<QuestionnaireDefinitionStub[]>([]);
  const [versionStubs, setVersionStubs] = useState<QuestionnaireDefinitionStub[]>([]);
  const [selectedKey, setSelectedKey] = useState<string | null>(get("key"));
  const [selectedVersion, setSelectedVersion] = useState<number>(parseQuestionnaireVersion(get("version")));
  const [availableVersions, setAvailableVersions] = useState<number[]>([]);
  const [currentDefinition, setCurrentDefinition] = useState<QuestionnaireDefinition | null>(null);
  const [isCatalogLoading, setIsCatalogLoading] = useState<boolean>(false);
  const [isDefinitionLoading, setIsDefinitionLoading] = useState<boolean>(false);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [isDirty, setIsDirty] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [customCategories, setCustomCategories] = useState<string[]>([]);
  const selectedKeyRef = useRef<string | null>(null);
  const selectedVersionRef = useRef(selectedVersion);
  const hasBlockingDraftRef = useRef(false);
  const currentDefinitionRef = useRef<QuestionnaireDefinition | null>(null);
  const persistedDefinitionRef = useRef<QuestionnaireDefinition | null>(null);
  const definitionRequestRef = useRef(0);
  const saveRequestRef = useRef(0);
  const saveSubmittingRef = useRef(false);
  const versionCreatingRef = useRef(false);
  const questionnaireCreatingRef = useRef(false);
  const questionnaireDeletingRef = useRef(false);
  const localQuestionIdCounterRef = useRef(0);

  useEffect(() => {
    selectedKeyRef.current = selectedKey;
    selectedVersionRef.current = selectedVersion;
    hasBlockingDraftRef.current = isDirty && saveState !== "saving";
  }, [isDirty, saveState, selectedKey, selectedVersion]);

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
  const [showCreateModal, setShowCreateModal] = useState(get("modal") === "create");
  const [newKey, setNewKey] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [newDescription, setNewDescription] = useState("");
  const [newAudience, setNewAudience] = useState<"leadership" | "team" | "participant">("team");
  const [isAddingCategory, setIsAddingCategory] = useState(false);
  const [categoryDraft, setCategoryDraft] = useState("");

  // Search State
  const [searchQuery, setSearchQuery] = useState(get("q") ?? "");
  const [noticeMessage, setNoticeMessage] = useState<string | null>(null);
  const [confirmDialog, setConfirmDialog] = useState<ConfirmDialogState | null>(null);

  const filteredStubs = useMemo(() => {
    if (!searchQuery.trim()) return stubs;
    const q = searchQuery.toLowerCase();
    return stubs.filter(s => 
      (s.name && s.name.toLowerCase().includes(q)) || 
      (s.id && s.id.toLowerCase().includes(q))
    );
  }, [stubs, searchQuery]);

  const requestDiscardDraftForNavigation = useCallback(
    (onDiscard: () => void) => {
      if (!hasBlockingDraftRef.current) {
        onDiscard();
        return;
      }

      setConfirmDialog({
        title: "Modificări nesalvate",
        description: "Dacă schimbi chestionarul acum, pierzi modificările care nu au fost salvate.",
        confirmLabel: "Renunță la modificări",
        tone: "danger",
        onConfirm: onDiscard,
      });
    },
    [],
  );

  useEffect(() => {
    if (!isDirty || saveState === "saving") return;

    const protectedUrl = window.location.href;
    const handleBeforeUnload = (event: BeforeUnloadEvent) => {
      if (!hasBlockingDraftRef.current) return;
      event.preventDefault();
      event.returnValue = "";
    };
    const handleDocumentClick = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) {
        return;
      }
      const target = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null;
      if (!target || target.target === "_blank" || target.hasAttribute("download")) return;

      const destination = new URL(target.href, window.location.href);
      if (destination.origin !== window.location.origin || destination.href === window.location.href) return;

      event.preventDefault();
      requestDiscardDraftForNavigation(() => {
        hasBlockingDraftRef.current = false;
        window.location.assign(destination.href);
      });
    };
    const handlePopState = () => {
      const destination = window.location.href;
      window.history.pushState(window.history.state, "", protectedUrl);
      requestDiscardDraftForNavigation(() => {
        hasBlockingDraftRef.current = false;
        window.location.assign(destination);
      });
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    window.addEventListener("popstate", handlePopState);
    document.addEventListener("click", handleDocumentClick, true);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      window.removeEventListener("popstate", handlePopState);
      document.removeEventListener("click", handleDocumentClick, true);
    };
  }, [isDirty, requestDiscardDraftForNavigation, saveState]);

  useEffect(() => {
    setSearchQuery(get("q") ?? "");
    setShowCreateModal(get("modal") === "create");

    const nextKey = get("key");
    const nextVersion = parseQuestionnaireVersion(get("version"));
    const currentSelectedKey = selectedKeyRef.current;
    const currentSelectedVersion = selectedVersionRef.current;
    if (nextKey === currentSelectedKey && nextVersion === currentSelectedVersion) return;

    if (hasBlockingDraftRef.current) {
      setParams(
        {
          key: currentSelectedKey,
          version: currentSelectedKey ? currentSelectedVersion : null,
        },
        "replace",
      );
      requestDiscardDraftForNavigation(() => {
        setSelectedKey(nextKey);
        setSelectedVersion(nextVersion);
        if (!nextKey) {
          currentDefinitionRef.current = null;
          setCurrentDefinition(null);
        }
        setParams({ key: nextKey, version: nextKey ? nextVersion : null }, "push");
      });
      return;
    }

    setSelectedKey(nextKey);
    setSelectedVersion(nextVersion);
    if (!nextKey) {
      currentDefinitionRef.current = null;
      setCurrentDefinition(null);
    }
  }, [get, requestDiscardDraftForNavigation, searchKey, setParams]);

  // Load stubs list
  const loadStubs = useCallback(async () => {
    setIsCatalogLoading(true);
    try {
      const allVersions = await listQuestionnaireDefinitionStubs(false, { latestOnly: false });
      setVersionStubs(allVersions);
      setStubs(latestDefinitionStubs(allVersions));
    } catch (error) {
      setVersionStubs([]);
      setStubs([]);
      setNoticeMessage(error instanceof Error ? error.message : "Catalogul de chestionare nu a putut fi încărcat.");
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
      setParam("version", allVersions[0], "replace");
    }
  }, [selectedKey, selectedVersion, setParam, versionStubsByKey]);

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
        if (!def) {
          throw new Error("Chestionarul nu a putut fi încărcat.");
        }
        currentDefinitionRef.current = def;
        persistedDefinitionRef.current = def;
        setCurrentDefinition(def);
        setSaveState("idle");
        setIsDirty(false);
        setSaveError(null);
      } catch (error) {
        if (definitionRequestRef.current !== requestId) return;
        currentDefinitionRef.current = null;
        persistedDefinitionRef.current = null;
        setCurrentDefinition(null);
        setSaveState("error");
        setSaveError(error instanceof Error ? error.message : "Chestionarul nu a putut fi încărcat.");
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
    if (!draft || saveSubmittingRef.current || saveState === "saving" || !isDirty) return;
    const submittedDraft = draft;
    const requestId = saveRequestRef.current + 1;
    saveRequestRef.current = requestId;
    saveSubmittingRef.current = true;
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
      const currentDraft = currentDefinitionRef.current;
      const stillEditingSavedDefinition =
        selectedKeyRef.current === submittedDraft.key &&
        currentDraft?.key === submittedDraft.key &&
        currentDraft.version === submittedDraft.version;
      if (stillEditingSavedDefinition) {
        persistedDefinitionRef.current = saved;
        if (currentDraft === submittedDraft) {
          currentDefinitionRef.current = saved;
          setCurrentDefinition(saved);
          setIsDirty(false);
          setSaveState("saved");
        } else {
          setIsDirty(true);
          setSaveState("idle");
        }
      }
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
      const currentDraft = currentDefinitionRef.current;
      const stillEditingFailedDefinition =
        selectedKeyRef.current === submittedDraft.key &&
        currentDraft?.key === submittedDraft.key &&
        currentDraft.version === submittedDraft.version;
      if (saveRequestRef.current === requestId && stillEditingFailedDefinition) {
        setSaveState("error");
        setSaveError(error instanceof Error ? error.message : "Chestionarul nu a putut fi salvat.");
      }
    } finally {
      if (saveRequestRef.current === requestId) {
        saveSubmittingRef.current = false;
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

  const showNotice = (message: string) => {
    setNoticeMessage(message);
  };

  const handleSelectDefinition = (key: string, version: number) => {
    if (key === selectedKey && version === selectedVersion) return;
    requestDiscardDraftForNavigation(() => {
      setSelectedKey(key);
      setSelectedVersion(version);
      setParams({ key, version, modal: null }, "push");
    });
  };

  const handleSelectVersion = (version: number) => {
    if (version === selectedVersion) return;
    requestDiscardDraftForNavigation(() => {
      setSelectedVersion(version);
      setParam("version", version, "push");
    });
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
    showNotice("Redenumirea cheii nu este permisă pe server. Creează un chestionar nou cu o altă cheie dacă este necesar.");
  };

  const handleCreateNewVersion = async () => {
    const draftDefinition = currentDefinitionRef.current;
    if (!draftDefinition || versionCreatingRef.current || isDefinitionLoading || saveSubmittingRef.current) return;
    versionCreatingRef.current = true;
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
      setParam("version", saved.version, "replace");
      await loadStubs();
    } catch (e) {
      showNotice((e as Error).message ?? "Eroare la crearea unei noi versiuni.");
    } finally {
      versionCreatingRef.current = false;
      setIsDefinitionLoading(false);
    }
  };

  const handleDeleteQuestionnaire = () => {
    if (!selectedKey) return;
    const selectedName = currentDefinition?.title ?? selectedKey;
    setConfirmDialog({
      title: "Pensionezi chestionarul?",
      description: `"${selectedName}" va fi marcat ca inactiv pe server. Istoricul existent rămâne disponibil în proiectele care l-au folosit.`,
      confirmLabel: "Pensionează",
      tone: "danger",
      onConfirm: async () => {
        if (questionnaireDeletingRef.current) return;
        questionnaireDeletingRef.current = true;
        setIsDefinitionLoading(true);
        try {
          await deleteQuestionnaireDefinitionOnServer(selectedKey, selectedVersion);
          const remainingVersions = await listQuestionnaireDefinitionStubs(false, { latestOnly: false });
          const remainingLatest = latestDefinitionStubs(remainingVersions);
          setVersionStubs(remainingVersions);
          setStubs(remainingLatest);
          const nextSelection = remainingLatest.find((stub) => stub.id !== selectedKey) ?? remainingLatest[0];
          if (nextSelection) {
            setSelectedKey(nextSelection.id);
            setSelectedVersion(nextSelection.version ?? 1);
            setParams({ key: nextSelection.id, version: nextSelection.version ?? 1 }, "replace");
          } else {
            setSelectedKey(null);
            currentDefinitionRef.current = null;
            persistedDefinitionRef.current = null;
            setCurrentDefinition(null);
            setAvailableVersions([]);
            setParams({ key: null, version: null }, "replace");
          }
        } catch (e) {
          showNotice((e as Error).message ?? "Eroare la ștergerea/pensionarea chestionarului.");
        } finally {
          questionnaireDeletingRef.current = false;
          setIsDefinitionLoading(false);
        }
      },
    });
  };

  const handleAddQuestionnaire = async (e: FormEvent) => {
    e.preventDefault();
    if (!newKey || questionnaireCreatingRef.current) return;

    const key = newKey.toLowerCase().replace(/[^a-z0-9_]/g, "_");
    const title = newTitle.trim() || "Chestionar nou";
    questionnaireCreatingRef.current = true;
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
        active: true,
      });

      setShowCreateModal(false);
      setNewKey("");
      setNewTitle("");
      setNewDescription("");
      setSelectedKey(saved.key);
      setSelectedVersion(saved.version);
      setParams({ key: saved.key, version: saved.version, modal: null }, "replace");
      await loadStubs();
    } catch (e) {
      showNotice((e as Error).message ?? "Eroare la crearea chestionarului.");
    } finally {
      questionnaireCreatingRef.current = false;
      setIsCatalogLoading(false);
    }
  };

  // Section modifiers
  const handleAddSection = (): string | null => {
    const definition = currentDefinitionRef.current;
    if (!definition) return null;
    const sections = [...definition.schema.sections];
    const newSectionId = `sectiunea_${sections.length + 1}`;
    sections.push({
      id: newSectionId,
      title: `Secțiunea ${sections.length + 1}`,
      questions: [],
    });
    applyDefinitionDraft({
      ...definition,
      schema: {
        ...definition.schema,
        sections,
      },
    });
    return newSectionId;
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
      showNotice("Chestionarul trebuie să aibă cel puțin o secțiune.");
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

  const createLocalQuestionId = useCallback((definition: QuestionnaireDefinition, sectionIndex: number, nextIndex: number) => {
    localQuestionIdCounterRef.current += 1;
    const existingIds = new Set(
      definition.schema.sections.flatMap((section) => section.questions.map((question) => question.id)),
    );
    const prefix = `${definition.key}_s${sectionIndex + 1}_q${nextIndex}`;
    let candidate = `${prefix}_${localQuestionIdCounterRef.current}`;

    while (existingIds.has(candidate)) {
      localQuestionIdCounterRef.current += 1;
      candidate = `${prefix}_${localQuestionIdCounterRef.current}`;
    }

    return candidate;
  }, []);

  // Question modifiers
  const handleAddQuestion = (sectionIndex: number): string | null => {
    const definition = currentDefinitionRef.current;
    if (!definition) return null;
    const sections = [...definition.schema.sections];
    const section = sections[sectionIndex];
    if (!section) return null;
    const nextIndex = section.questions.length + 1;
    const questionId = createLocalQuestionId(definition, sectionIndex, nextIndex);
    const newQuestion: QuestionnaireQuestion = {
      id: questionId,
      code: `Q${nextIndex}`,
      type: "likert",
      label: "Întrebare nouă",
      required: true,
      scale: [
        { value: 1, label: "Rar" },
        { value: 2, label: "Uneori" },
        { value: 3, label: "De obicei" },
      ],
    };
    sections[sectionIndex] = {
      ...section,
      questions: [...section.questions, newQuestion],
    };
    applyDefinitionDraft({
      ...definition,
      schema: {
        ...definition.schema,
        sections,
      },
    });
    return questionId;
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

  const handleMoveQuestion = (sectionIndex: number, questionIndex: number, direction: -1 | 1) => {
    updateDefinitionDraft((definition) => {
      const sections = [...definition.schema.sections];
      const section = sections[sectionIndex];
      const targetIndex = questionIndex + direction;
      if (!section || targetIndex < 0 || targetIndex >= section.questions.length) return definition;
      const questions = [...section.questions];
      const [question] = questions.splice(questionIndex, 1);
      questions.splice(targetIndex, 0, question);
      sections[sectionIndex] = { ...section, questions };
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

  const handleUpdateStatement = (
    sectionIndex: number,
    questionIndex: number,
    statementIndex: number,
    updates: Partial<QuestionnaireStatement>,
  ) => {
    updateDefinitionDraft((definition) => {
      const sections = [...definition.schema.sections];
      const section = sections[sectionIndex];
      const questions = [...section.questions];
      const question = questions[questionIndex];
      const statements = [...(question.statements || [])];

      statements[statementIndex] = {
        ...statements[statementIndex],
        ...updates,
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
  const scaleGroups = useMemo<QuestionnaireScaleGroup[]>(() => {
    if (!currentDefinition) return [];

    const groups = new Map<string, QuestionnaireScaleGroup>();
    currentDefinition.schema.sections.forEach((section) => {
      section.questions.forEach((question) => {
        if (!question.scale?.length || hasStatementSpecificScales(question)) return;
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
      ? "Salvăm modificările"
      : saveState === "saved"
        ? "Salvat"
        : saveState === "error"
          ? "Eroare la salvare"
          : isDirty
            ? "Modificări nesalvate"
            : null;

  const handleUpdateScaleGroup = (
    group: QuestionnaireScaleGroup,
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

  const handleAddCustomCategory = () => {
    const cleanName = categoryDraft.toLowerCase().replace(/[^a-z0-9_]/g, "_");
    if (!cleanName) return;
    if (!categories.includes(cleanName)) {
      setCustomCategories((previous) => [...previous, cleanName]);
    }
    setNewKey(cleanName);
    setCategoryDraft("");
    setIsAddingCategory(false);
  };

  const handleDeleteSelectedCustomCategory = () => {
    if (!newKey || !customCategories.includes(newKey)) return;
    setConfirmDialog({
      title: "Ștergi categoria locală?",
      description: `"${newKey}" va fi eliminată doar din lista locală de creare. Chestionarele existente nu sunt modificate.`,
      confirmLabel: "Șterge categoria",
      tone: "danger",
      onConfirm: () => {
        setCustomCategories((previous) => previous.filter((cat) => cat !== newKey));
        setNewKey("");
      },
    });
  };

  const canDeleteSelectedCustomCategory = Boolean(newKey && customCategories.includes(newKey));

  return (
    <div className="flex flex-col gap-5 text-foreground">
      {!selectedKey ? (
        // GALLERY MODE
        <div className="flex flex-col gap-5">
          <CatalogToolbar>
            <SearchField
              id="questionnaire-search"
              label="Caută chestionar"
              placeholder="Caută chestionar"
              value={searchQuery}
              onValueChange={(value) => {
                setSearchQuery(value);
                setParam("q", value, "replace");
              }}
              className="w-full md:flex-1"
            />
            <Button
              type="button"
              onClick={() => {
                setShowCreateModal(true);
                setParam("modal", "create", "push");
              }}
              disabled={isCatalogLoading}
              className="shrink-0"
            >
              {isCatalogLoading ? (
                <Loader2Icon
                  data-icon="inline-start"
                  aria-hidden="true"
                  className="animate-spin"
                  strokeWidth={1.8}
                />
              ) : (
                <PlusIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
              )}
              {isCatalogLoading ? "Încărcăm catalogul" : "Creează chestionar"}
            </Button>
          </CatalogToolbar>

          {isCatalogLoading ? (
            <div className="flex min-h-64 items-center justify-center rounded-lg border border-border bg-surface p-6">
              <OperationFeedback
                className="w-full max-w-md"
                title="Încărcăm catalogul"
              />
            </div>
          ) : filteredStubs.length > 0 ? (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {filteredStubs.map((stub) => (
                <CatalogCard
                  key={`${stub.id}-${stub.version ?? "fără-versiune"}`}
                  onClick={() => handleSelectDefinition(stub.id, stub.version ?? 1)}
                  aria-label={`Editează ${stub.name}`}
                  eyebrow={AUDIENCE_LABELS[stub.audience] ?? stub.audience}
                  version={`v${stub.version ?? 1}`}
                  title={stub.name}
                  description={stub.description || "Fără descriere"}
                  metadata={<span className="font-medium tabular-nums">{stub.estimatedItems ?? "TBD"} întrebări</span>}
                  status={{
                    label: QUESTIONNAIRE_STATUS_LABELS[stub.status] ?? stub.status,
                    tone: questionnaireStatusTone(stub.status),
                  }}
                />
              ))}
            </div>
          ) : (
            <div className="flex min-h-[40vh] flex-col items-center justify-center rounded-lg border border-border bg-surface p-12 text-center">
              <p className="text-xl font-bold text-foreground">Catalog gol</p>
              <Button
                type="button"
                className="mt-4"
                onClick={() => {
                  setShowCreateModal(true);
                  setParam("modal", "create", "push");
                }}
              >
                <PlusIcon data-icon="inline-start" aria-hidden="true" />
                Creează chestionar
              </Button>
            </div>
          )}
        </div>
      ) : (
        <div className="min-w-0">
          {isEditorLoading ? (
            <div className="flex min-h-64 items-center justify-center border-y border-border bg-surface p-6">
              <OperationFeedback className="w-full max-w-md" title="Încărcăm chestionarul" />
            </div>
          ) : currentDefinition ? (
            <QuestionnaireEditor
              definition={currentDefinition}
              categories={categories}
              availableVersions={availableVersions}
              selectedVersion={selectedVersion}
              latestSelectedVersion={latestSelectedVersion}
              scaleGroups={scaleGroups}
              saveState={saveState}
              saveStateLabel={saveStateLabel}
              saveError={saveError}
              isDirty={isDirty}
              isBusy={isSaving || isDefinitionLoading}
              canDelete={canDeleteSelected}
              onBack={() => {
                requestDiscardDraftForNavigation(() => {
                  setSelectedKey(null);
                  currentDefinitionRef.current = null;
                  setCurrentDefinition(null);
                  setParams({ key: null, version: null }, "push");
                });
              }}
              onSave={() => void handleSaveDraft()}
              onDiscard={handleDiscardDraft}
              onSelectVersion={handleSelectVersion}
              onCreateVersion={() => void handleCreateNewVersion()}
              onDeleteQuestionnaire={handleDeleteQuestionnaire}
              onUpdateMetadata={handleSaveMetadata}
              onRenameKey={handleRenameDefinitionKey}
              onUpdateInstructions={(instructions) =>
                updateDefinitionDraft((definition) => ({
                  ...definition,
                  schema: { ...definition.schema, instructions },
                }))
              }
              onAddSection={handleAddSection}
              onUpdateSectionTitle={handleUpdateSectionTitle}
              onDeleteSection={handleDeleteSection}
              onAddQuestion={handleAddQuestion}
              onUpdateQuestion={handleUpdateQuestion}
              onDeleteQuestion={handleDeleteQuestion}
              onMoveQuestion={handleMoveQuestion}
              onAddStatement={handleAddStatement}
              onUpdateStatement={handleUpdateStatement}
              onDeleteStatement={handleDeleteStatement}
              onUpdateScaleGroup={handleUpdateScaleGroup}
            />
          ) : saveError ? (
            <InlineFeedback tone="danger" className="p-5">
              {saveError}
            </InlineFeedback>
          ) : null}
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <ModalLayer
          labelledBy="create-questionnaire-title"
          onClose={() => {
            if (isCatalogLoading) return;
            setShowCreateModal(false);
            setParam("modal", null, "replace");
          }}
          panelClassName="max-w-md"
        >
          <form
            onSubmit={handleAddQuestionnaire}
            className="flex flex-col gap-4"
          >
            <h3 id="create-questionnaire-title" className="text-lg font-bold text-foreground">Adaugă chestionar nou</h3>

            <FieldGroup>
              <Field>
                <FieldLabel>Cod unic (slug / categorie)</FieldLabel>
                <div className="flex gap-2">
                  <SelectControl
                    label="Cod unic (slug / categorie)"
                    wrapperClassName="min-w-0 flex-1"
                    value={newKey}
                    onChange={(e) => setNewKey(e.target.value)}
                    disabled={isCatalogLoading}
                    required
                  >
                    <option value="">Alege o categorie</option>
                    {categories.map((cat) => (
                      <option key={cat} value={cat}>
                        {cat}
                      </option>
                    ))}
                  </SelectControl>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => setIsAddingCategory((current) => !current)}
                    disabled={isCatalogLoading}
                  >
                    <PlusIcon data-icon="inline-start" aria-hidden="true" strokeWidth={2.2} />
                    Adaugă
                  </Button>
                  <Button
                    type="button"
                    variant="destructive"
                    size="sm"
                    onClick={handleDeleteSelectedCustomCategory}
                    disabled={isCatalogLoading || !canDeleteSelectedCustomCategory}
                  >
                    Șterge
                  </Button>
                </div>
                {isAddingCategory ? (
                  <div className="mt-2 rounded-md border border-border bg-muted p-2">
                    <FieldLabel className="sr-only" htmlFor="new-questionnaire-category">Categorie nouă</FieldLabel>
                    <div className="flex gap-2">
                      <Input
                        id="new-questionnaire-category"
                        value={categoryDraft}
                        onChange={(event) => setCategoryDraft(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            handleAddCustomCategory();
                          }
                        }}
                        placeholder="categorie_noua"
                        className="min-w-0 flex-1"
                        disabled={isCatalogLoading}
                      />
                      <Button
                        type="button"
                        size="sm"
                        onClick={handleAddCustomCategory}
                        disabled={isCatalogLoading || !categoryDraft.trim()}
                      >
                        Salvează
                      </Button>
                    </div>
                  </div>
                ) : null}
              </Field>

              <Field>
                <FieldLabel htmlFor="new-questionnaire-title">Titlu</FieldLabel>
                <Input
                  id="new-questionnaire-title"
                  type="text"
                  value={newTitle}
                  onChange={(e) => setNewTitle(e.target.value)}
                  placeholder="Chestionar nou"
                  disabled={isCatalogLoading}
                />
              </Field>

              <Field>
                <FieldLabel htmlFor="new-questionnaire-description">Descriere</FieldLabel>
                <Textarea
                  id="new-questionnaire-description"
                  value={newDescription}
                  onChange={(e) => setNewDescription(e.target.value)}
                  placeholder="Scurtă descriere a scopului acestui chestionar"
                  rows={2}
                  className="min-h-16"
                  disabled={isCatalogLoading}
                />
              </Field>

              <Field>
                <FieldLabel>Audiență țintă</FieldLabel>
                <SelectControl
                  label="Audiență țintă"
                  value={newAudience}
                  onChange={(e) => setNewAudience(e.target.value as "leadership" | "team" | "participant")}
                  disabled={isCatalogLoading}
                >
                  <option value="team">Echipă (ex. Lencioni)</option>
                  <option value="leadership">Lideri (ex. Distress Drivers, PCM)</option>
                  <option value="participant">Individual (ex. 360 Feedback)</option>
                </SelectControl>
              </Field>
            </FieldGroup>

            {isCatalogLoading ? (
              <OperationFeedback
                title="Creăm chestionarul"
              />
            ) : null}

            <div className="flex justify-end gap-2 border-t border-border pt-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => {
                  setShowCreateModal(false);
                  setParam("modal", null, "replace");
                }}
                disabled={isCatalogLoading}
              >
                Anulează
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={isCatalogLoading}
              >
                {isCatalogLoading ? <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" /> : null}
                {isCatalogLoading ? "Creăm" : "Creează"}
              </Button>
            </div>
          </form>
        </ModalLayer>
      )}
      {confirmDialog ? (
        <ModalLayer
          labelledBy="questionnaire-confirm-title"
          onClose={() => setConfirmDialog(null)}
          panelClassName="max-w-md"
        >
          <div className="flex flex-col gap-4">
            <div>
              <h3 id="questionnaire-confirm-title" className="text-lg font-bold text-foreground">
                {confirmDialog.title}
              </h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{confirmDialog.description}</p>
            </div>
            <div className="flex justify-end gap-2 border-t border-border pt-3">
              <Button type="button" variant="outline" size="sm" onClick={() => setConfirmDialog(null)}>
                Anulează
              </Button>
              <Button
                type="button"
                variant={confirmDialog.tone === "danger" ? "destructive" : "default"}
                size="sm"
                onClick={() => {
                  const action = confirmDialog.onConfirm;
                  setConfirmDialog(null);
                  void action();
                }}
              >
                {confirmDialog.confirmLabel}
              </Button>
            </div>
          </div>
        </ModalLayer>
      ) : null}
      {noticeMessage ? (
        <ModalLayer
          labelledBy="questionnaire-notice-title"
          onClose={() => setNoticeMessage(null)}
          panelClassName="max-w-md"
        >
          <div className="flex flex-col gap-4">
            <div>
              <h3 id="questionnaire-notice-title" className="text-lg font-bold text-foreground">
                Atenție
              </h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{noticeMessage}</p>
            </div>
            <div className="flex justify-end border-t border-border pt-3">
              <Button type="button" size="sm" onClick={() => setNoticeMessage(null)}>
                Am înțeles
              </Button>
            </div>
          </div>
        </ModalLayer>
      ) : null}
    </div>
  );
}
