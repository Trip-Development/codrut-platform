"use client";

import { useEffect, useRef, useState } from "react";
import {
  AlertCircleIcon,
  ArrowDownIcon,
  ArrowLeftIcon,
  ArrowUpIcon,
  CheckIcon,
  CopyPlusIcon,
  FileSlidersIcon,
  ListTreeIcon,
  Loader2Icon,
  PlusIcon,
  RotateCcwIcon,
  SaveIcon,
  Settings2Icon,
  SlidersHorizontalIcon,
  Trash2Icon,
} from "lucide-react";

import type {
  QuestionnaireDefinition,
  QuestionnaireQuestion,
  QuestionnaireScaleOption,
  QuestionnaireStatement,
} from "@/api/questionnaires";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { SelectControl } from "@/components/ui/select-control";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/utils/cn";

export type QuestionnaireScaleGroup = {
  key: string;
  renderKey: string;
  type: QuestionnaireQuestion["type"];
  title: string;
  questionCount: number;
  scale: QuestionnaireScaleOption[];
};

type InspectorView = "question" | "questionnaire" | "scales";

type QuestionnaireEditorProps = {
  definition: QuestionnaireDefinition;
  categories: string[];
  availableVersions: number[];
  selectedVersion: number;
  latestSelectedVersion?: number;
  scaleGroups: QuestionnaireScaleGroup[];
  saveState: "idle" | "saving" | "saved" | "error";
  saveStateLabel: string | null;
  saveError: string | null;
  isDirty: boolean;
  isBusy: boolean;
  canDelete: boolean;
  onBack: () => void;
  onSave: () => void;
  onDiscard: () => void;
  onSelectVersion: (version: number) => void;
  onCreateVersion: () => void;
  onDeleteQuestionnaire: () => void;
  onUpdateMetadata: (
    fields: Partial<Pick<QuestionnaireDefinition, "title" | "description">> & {
      audience?: "leadership" | "team" | "participant";
    },
  ) => void;
  onRenameKey: () => void;
  onUpdateInstructions: (instructions: string) => void;
  onAddSection: () => string | null;
  onUpdateSectionTitle: (sectionIndex: number, title: string) => void;
  onDeleteSection: (sectionIndex: number) => void;
  onAddQuestion: (sectionIndex: number) => string | null;
  onUpdateQuestion: (
    sectionIndex: number,
    questionIndex: number,
    updates: Partial<QuestionnaireQuestion>,
  ) => void;
  onDeleteQuestion: (sectionIndex: number, questionIndex: number) => void;
  onMoveQuestion: (sectionIndex: number, questionIndex: number, direction: -1 | 1) => void;
  onAddStatement: (sectionIndex: number, questionIndex: number) => void;
  onUpdateStatement: (
    sectionIndex: number,
    questionIndex: number,
    statementIndex: number,
    updates: Partial<QuestionnaireStatement>,
  ) => void;
  onDeleteStatement: (sectionIndex: number, questionIndex: number, statementIndex: number) => void;
  onUpdateScaleGroup: (
    group: QuestionnaireScaleGroup,
    updater: (scale: QuestionnaireScaleOption[]) => QuestionnaireScaleOption[],
  ) => void;
};

function questionTypeLabel(type: QuestionnaireQuestion["type"]): string {
  if (type === "statement_score_set") return "Set de afirmații";
  if (type === "single_choice") return "Alegere unică";
  return "Scară Likert";
}

function nextScaleOption(scale: QuestionnaireScaleOption[]): QuestionnaireScaleOption {
  const numericValues = scale
    .map((option) => option.value)
    .filter((value): value is number => typeof value === "number");

  if (numericValues.length === scale.length) {
    const nextValue = numericValues.length > 0 ? Math.max(...numericValues) + 1 : 1;
    return { value: nextValue, label: `Opțiune ${nextValue}` };
  }

  const nextIndex = scale.length + 1;
  return { value: `option_${nextIndex}`, label: `Opțiune ${nextIndex}` };
}

function hasStatementSpecificScales(question: QuestionnaireQuestion): boolean {
  return (
    question.type === "statement_score_set" &&
    (question.statements?.length ?? 0) > 0 &&
    question.statements?.every((statement) => (statement.scale?.length ?? 0) > 0) === true
  );
}

function firstSelection(definition: QuestionnaireDefinition): { sectionId: string | null; questionId: string | null } {
  const firstSection = definition.schema.sections[0];
  return {
    sectionId: firstSection?.id ?? null,
    questionId: firstSection?.questions[0]?.id ?? null,
  };
}

function SaveStatus({
  state,
  label,
  error,
}: {
  state: QuestionnaireEditorProps["saveState"];
  label: string | null;
  error: string | null;
}) {
  if (!label) return null;

  const Icon = state === "saving" ? Loader2Icon : state === "saved" ? CheckIcon : state === "error" ? AlertCircleIcon : null;

  return (
    <span
      role="status"
      className={cn(
        "inline-flex min-w-0 items-center gap-1.5 text-xs font-semibold",
        state === "error" ? "text-destructive" : "text-muted-foreground",
      )}
      title={error ?? undefined}
    >
      {Icon ? <Icon aria-hidden="true" className={cn("size-3.5", state === "saving" && "animate-spin")} /> : null}
      <span className="truncate">{label}</span>
    </span>
  );
}

export function QuestionnaireEditor({
  definition,
  categories,
  availableVersions,
  selectedVersion,
  latestSelectedVersion,
  scaleGroups,
  saveState,
  saveStateLabel,
  saveError,
  isDirty,
  isBusy,
  canDelete,
  onBack,
  onSave,
  onDiscard,
  onSelectVersion,
  onCreateVersion,
  onDeleteQuestionnaire,
  onUpdateMetadata,
  onRenameKey,
  onUpdateInstructions,
  onAddSection,
  onUpdateSectionTitle,
  onDeleteSection,
  onAddQuestion,
  onUpdateQuestion,
  onDeleteQuestion,
  onMoveQuestion,
  onAddStatement,
  onUpdateStatement,
  onDeleteStatement,
  onUpdateScaleGroup,
}: QuestionnaireEditorProps) {
  const initialSelection = firstSelection(definition);
  const [selectedSectionId, setSelectedSectionId] = useState<string | null>(initialSelection.sectionId);
  const [selectedQuestionId, setSelectedQuestionId] = useState<string | null>(initialSelection.questionId);
  const [inspectorView, setInspectorView] = useState<InspectorView>(
    initialSelection.questionId ? "question" : "questionnaire",
  );
  const [expandedLocalScaleIds, setExpandedLocalScaleIds] = useState<Set<string>>(new Set());
  const editorHeadingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    const section = definition.schema.sections.find((candidate) => candidate.id === selectedSectionId);
    if (!section) {
      const next = firstSelection(definition);
      setSelectedSectionId(next.sectionId);
      setSelectedQuestionId(next.questionId);
      setInspectorView(next.questionId ? "question" : "questionnaire");
      return;
    }

    if (selectedQuestionId && !section.questions.some((question) => question.id === selectedQuestionId)) {
      setSelectedQuestionId(section.questions[0]?.id ?? null);
      setInspectorView(section.questions.length > 0 ? "question" : "questionnaire");
    }
  }, [definition, selectedQuestionId, selectedSectionId]);

  const selectedSectionIndex = definition.schema.sections.findIndex((section) => section.id === selectedSectionId);
  const selectedSection = selectedSectionIndex >= 0 ? definition.schema.sections[selectedSectionIndex] : null;
  const selectedQuestionIndex = selectedSection?.questions.findIndex((question) => question.id === selectedQuestionId) ?? -1;
  const selectedQuestion = selectedQuestionIndex >= 0 ? selectedSection?.questions[selectedQuestionIndex] ?? null : null;

  const selectSection = (sectionId: string) => {
    const section = definition.schema.sections.find((candidate) => candidate.id === sectionId);
    setSelectedSectionId(sectionId);
    setSelectedQuestionId(section?.questions[0]?.id ?? null);
    setInspectorView(section?.questions.length ? "question" : "questionnaire");
    requestAnimationFrame(() => editorHeadingRef.current?.focus());
  };

  const selectQuestion = (sectionId: string, questionId: string) => {
    setSelectedSectionId(sectionId);
    setSelectedQuestionId(questionId);
    setInspectorView("question");
    requestAnimationFrame(() => editorHeadingRef.current?.focus());
  };

  const toggleLocalScale = (scaleId: string) => {
    setExpandedLocalScaleIds((current) => {
      const next = new Set(current);
      if (next.has(scaleId)) next.delete(scaleId);
      else next.add(scaleId);
      return next;
    });
  };

  return (
    <section data-testid="questionnaire-editor-workspace" className="min-w-0 bg-background">
      <header className="sticky top-0 z-20 border-b border-border bg-background/95 px-3 py-2.5 backdrop-blur-sm lg:px-4">
        <div className="grid min-w-0 grid-cols-[auto_minmax(0,1fr)] gap-x-2 gap-y-2 sm:flex sm:items-center">
          <Button type="button" variant="ghost" size="icon-sm" onClick={onBack} aria-label="Înapoi la catalog" title="Înapoi la catalog">
            <ArrowLeftIcon aria-hidden="true" />
          </Button>
          <div className="min-w-0 flex-1 border-l border-border pl-3">
            <h1 className="truncate text-sm font-semibold text-foreground">{definition.title}</h1>
            <div className="mt-0.5 flex min-w-0 items-center gap-2">
              <span className="text-[11px] text-muted-foreground">v{selectedVersion}</span>
              <SaveStatus state={saveState} label={saveStateLabel} error={saveError} />
            </div>
          </div>

          <div className="col-span-2 flex min-w-0 items-end gap-1 border-t border-border pt-2 sm:col-span-1 sm:ml-auto sm:border-0 sm:pt-0">
            <SelectControl
              label="Versiune"
              wrapperClassName="mr-auto min-w-0 flex-1 sm:w-28 sm:flex-none"
              value={selectedVersion}
              onChange={(event) => onSelectVersion(Number(event.target.value))}
              disabled={isBusy}
            >
              {availableVersions.map((version) => (
                <option key={version} value={version}>
                  v{version} {version === latestSelectedVersion ? "(Activă)" : "(Veche)"}
                </option>
              ))}
            </SelectControl>

            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={onDiscard}
              disabled={!isDirty || isBusy}
              aria-label="Revino la ultima versiune salvată"
              title="Revino la ultima versiune salvată"
            >
              <RotateCcwIcon aria-hidden="true" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={onCreateVersion}
              disabled={isBusy}
              aria-label="Versiune nouă (clonează)"
              title="Versiune nouă (clonează)"
            >
              <CopyPlusIcon aria-hidden="true" />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon-sm"
              onClick={onDeleteQuestionnaire}
              disabled={!canDelete || isBusy}
              aria-label="Pensionează chestionarul"
              title="Pensionează chestionarul"
              className="text-destructive hover:bg-destructive/10 hover:text-destructive"
            >
              <Trash2Icon aria-hidden="true" />
            </Button>
            <Button
              type="button"
              size="sm"
              onClick={onSave}
              disabled={!isDirty || isBusy}
              aria-label="Salvează modificările"
              title="Salvează modificările"
              className="min-w-10 shrink-0 px-2.5 sm:px-3"
            >
              {saveState === "saving" ? (
                <Loader2Icon data-icon="inline-start" aria-hidden="true" className="animate-spin" />
              ) : (
                <SaveIcon data-icon="inline-start" aria-hidden="true" />
              )}
              <span className="hidden sm:inline">{saveState === "saving" ? "Salvăm" : "Salvează"}</span>
            </Button>
          </div>
        </div>
      </header>

      {saveError ? (
        <div role="alert" className="border-b border-destructive/20 bg-destructive/5 px-4 py-2 text-xs font-medium text-destructive">
          {saveError}
        </div>
      ) : null}

      <div className="grid min-h-[calc(100vh-10rem)] min-w-0 lg:grid-cols-[13.5rem_minmax(25rem,1fr)_19rem]">
        <nav
          aria-label="Structura chestionarului"
          className="max-h-64 min-w-0 overflow-y-auto border-r border-border bg-muted/35 p-2.5 lg:max-h-[calc(100vh-10rem)]"
        >
          <div className="mb-2 flex items-center justify-between px-1">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-foreground">
              <ListTreeIcon aria-hidden="true" className="size-3.5 text-muted-foreground" />
              Structură
            </div>
            <Button
              type="button"
              variant="ghost"
              size="icon-xs"
              onClick={() => {
                const sectionId = onAddSection();
                if (sectionId) {
                  setSelectedSectionId(sectionId);
                  setSelectedQuestionId(null);
                  setInspectorView("questionnaire");
                }
              }}
              aria-label="Adaugă secțiune"
              title="Adaugă secțiune"
            >
              <PlusIcon aria-hidden="true" />
            </Button>
          </div>

          <div className="space-y-1.5">
            {definition.schema.sections.map((section, sectionIndex) => {
              const sectionSelected = section.id === selectedSectionId;
              return (
                <div key={section.id}>
                  <button
                    type="button"
                    onClick={() => selectSection(section.id)}
                    aria-current={sectionSelected ? "true" : undefined}
                    className={cn(
                      "flex min-h-10 w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-xs font-semibold outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring/45 lg:min-h-0",
                      sectionSelected ? "bg-muted text-foreground" : "text-foreground hover:bg-muted/65",
                    )}
                  >
                    <span className="truncate">{section.title || `Secțiunea ${sectionIndex + 1}`}</span>
                    <span className="text-[10px] text-muted-foreground">
                      {section.questions.length}
                    </span>
                  </button>

                  {sectionSelected ? (
                    <div className="mt-1 space-y-0.5 pl-2">
                      {section.questions.map((question, questionIndex) => {
                        const questionSelected = question.id === selectedQuestionId;
                        return (
                          <button
                            key={question.id}
                            type="button"
                            data-testid={`question-row-${question.id}`}
                            onClick={() => selectQuestion(section.id, question.id)}
                            aria-current={questionSelected ? "true" : undefined}
                            aria-label={`Editează ${question.code || `întrebarea ${questionIndex + 1}`} ${question.label}`}
                            className={cn(
                              "grid min-h-10 w-full grid-cols-[2.25rem_minmax(0,1fr)] items-center gap-1.5 rounded-md px-2 py-1.5 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring/45 lg:min-h-0",
                              questionSelected ? "bg-muted text-brand-text" : "text-muted-foreground hover:bg-muted hover:text-foreground",
                            )}
                          >
                            <span className="truncate text-[10px] font-bold uppercase">{question.code || questionIndex + 1}</span>
                            <span className="truncate text-[11px] font-medium">{question.label || "Întrebare fără titlu"}</span>
                          </button>
                        );
                      })}
                      <Button
                        type="button"
                        variant="ghost"
                        size="xs"
                        className="mt-1 min-h-10 w-full justify-start text-muted-foreground lg:min-h-7"
                        onClick={() => {
                          const questionId = onAddQuestion(sectionIndex);
                          if (questionId) selectQuestion(section.id, questionId);
                        }}
                        aria-label={`Adaugă întrebare în secțiunea ${section.title}`}
                      >
                        <PlusIcon data-icon="inline-start" aria-hidden="true" />
                        Întrebare
                      </Button>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>
        </nav>

        <main className="min-w-0 bg-background px-5 py-5 xl:px-8 xl:py-7">
          {selectedSection ? (
            <div className="mx-auto w-full max-w-3xl">
              <div className="mb-6 flex items-center gap-2 border-b border-border pb-4">
                <Input
                  aria-label="Nume secțiune"
                  value={selectedSection.title}
                  onChange={(event) => onUpdateSectionTitle(selectedSectionIndex, event.target.value)}
                  className="h-9 min-w-0 flex-1 border-transparent bg-transparent px-1 text-lg font-semibold shadow-none hover:border-border focus-visible:border-ring"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => {
                    const questionId = onAddQuestion(selectedSectionIndex);
                    if (questionId) selectQuestion(selectedSection.id, questionId);
                  }}
                  aria-label={`Adaugă întrebare în secțiunea ${selectedSection.title}`}
                  title="Adaugă întrebare"
                >
                  <PlusIcon aria-hidden="true" />
                </Button>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => onDeleteSection(selectedSectionIndex)}
                  aria-label={`Șterge secțiunea ${selectedSection.title}`}
                  title="Șterge secțiunea"
                  className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                >
                  <Trash2Icon aria-hidden="true" />
                </Button>
              </div>

              {selectedQuestion ? (
                <article data-testid={`question-editor-${selectedQuestion.id}`} className="min-w-0">
                  <div className="mb-5 flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[11px] font-semibold text-muted-foreground">
                        Întrebarea {selectedQuestionIndex + 1} din {selectedSection.questions.length}
                      </p>
                      <h2 ref={editorHeadingRef} tabIndex={-1} className="mt-1 text-xl font-semibold text-foreground outline-none">
                        {selectedQuestion.label || "Întrebare fără titlu"}
                      </h2>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => onMoveQuestion(selectedSectionIndex, selectedQuestionIndex, -1)}
                        disabled={selectedQuestionIndex === 0}
                        aria-label="Mută întrebarea mai sus"
                        title="Mută mai sus"
                      >
                        <ArrowUpIcon aria-hidden="true" />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => onMoveQuestion(selectedSectionIndex, selectedQuestionIndex, 1)}
                        disabled={selectedQuestionIndex === selectedSection.questions.length - 1}
                        aria-label="Mută întrebarea mai jos"
                        title="Mută mai jos"
                      >
                        <ArrowDownIcon aria-hidden="true" />
                      </Button>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        onClick={() => onDeleteQuestion(selectedSectionIndex, selectedQuestionIndex)}
                        aria-label="Șterge întrebarea"
                        title="Șterge întrebarea"
                        className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                      >
                        <Trash2Icon aria-hidden="true" />
                      </Button>
                    </div>
                  </div>

                  <FieldGroup className="gap-5">
                    <Field>
                      <FieldLabel htmlFor={`question-code-${selectedQuestion.id}`}>Cod</FieldLabel>
                      <Input
                        id={`question-code-${selectedQuestion.id}`}
                        value={selectedQuestion.code}
                        onChange={(event) => onUpdateQuestion(selectedSectionIndex, selectedQuestionIndex, { code: event.target.value })}
                        className="max-w-36 font-mono text-xs"
                      />
                    </Field>
                    <Field>
                      <FieldLabel htmlFor={`question-label-${selectedQuestion.id}`}>Întrebare</FieldLabel>
                      <Textarea
                        id={`question-label-${selectedQuestion.id}`}
                        value={selectedQuestion.label}
                        onChange={(event) => onUpdateQuestion(selectedSectionIndex, selectedQuestionIndex, { label: event.target.value })}
                        rows={3}
                        className="min-h-24 text-base leading-7"
                        placeholder="Textul întrebării"
                      />
                    </Field>
                  </FieldGroup>

                  {!hasStatementSpecificScales(selectedQuestion) ? (
                    <LocalScaleEditor
                      sectionId={selectedSection.id}
                      question={selectedQuestion}
                      expanded={expandedLocalScaleIds.has(`${selectedSection.id}:${selectedQuestion.id}`)}
                      onToggle={() => toggleLocalScale(`${selectedSection.id}:${selectedQuestion.id}`)}
                      onChange={(scale) => onUpdateQuestion(selectedSectionIndex, selectedQuestionIndex, { scale })}
                    />
                  ) : null}

                  {selectedQuestion.type === "statement_score_set" ? (
                    <section className="mt-6 border-t border-border pt-5">
                      <div className="mb-3 flex items-center justify-between gap-3">
                        <h3 className="text-sm font-semibold text-foreground">Afirmații</h3>
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => onAddStatement(selectedSectionIndex, selectedQuestionIndex)}
                          aria-label={`Adaugă afirmație în întrebarea ${selectedQuestion.code}`}
                          title="Adaugă afirmație"
                        >
                          <PlusIcon aria-hidden="true" />
                        </Button>
                      </div>
                      <div className="divide-y divide-border border-y border-border">
                        {(selectedQuestion.statements ?? []).map((statement, statementIndex) => (
                          <div key={statement.id} className="py-3">
                            <div className="grid grid-cols-[2.75rem_minmax(0,1fr)_2.25rem] items-center gap-2">
                              <span className="text-xs font-semibold text-muted-foreground">{statement.code}</span>
                              <Input
                                aria-label={`Afirmația ${statement.code}`}
                                value={statement.label}
                                onChange={(event) =>
                                  onUpdateStatement(selectedSectionIndex, selectedQuestionIndex, statementIndex, {
                                    label: event.target.value,
                                  })
                                }
                                className="h-9"
                              />
                              <Button
                                type="button"
                                variant="ghost"
                                size="icon-sm"
                                onClick={() => onDeleteStatement(selectedSectionIndex, selectedQuestionIndex, statementIndex)}
                                aria-label={`Șterge afirmația ${statement.code}`}
                                title="Șterge afirmația"
                                className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                              >
                                <Trash2Icon aria-hidden="true" />
                              </Button>
                            </div>
                            {statement.scale?.length ? (
                              <StatementParticipantScaleEditor
                                statement={statement}
                                onChange={(scale) =>
                                  onUpdateStatement(selectedSectionIndex, selectedQuestionIndex, statementIndex, { scale })
                                }
                              />
                            ) : null}
                          </div>
                        ))}
                      </div>
                    </section>
                  ) : null}
                </article>
              ) : (
                <div className="flex min-h-80 flex-col items-center justify-center border-y border-border text-center">
                  <p className="text-sm font-semibold text-foreground">Secțiune fără întrebări</p>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="mt-4"
                    onClick={() => {
                      const questionId = onAddQuestion(selectedSectionIndex);
                      if (questionId) selectQuestion(selectedSection.id, questionId);
                    }}
                  >
                    <PlusIcon data-icon="inline-start" aria-hidden="true" />
                    Adaugă întrebare
                  </Button>
                </div>
              )}
            </div>
          ) : null}
        </main>

        <aside aria-label="Inspector" className="min-w-0 border-l border-border bg-surface">
          <div className="sticky top-[3.75rem]">
            <div className="grid grid-cols-3 gap-1 border-b border-border p-2">
              <InspectorTab
                active={inspectorView === "question"}
                disabled={!selectedQuestion}
                label="Întrebare"
                icon={Settings2Icon}
                onClick={() => setInspectorView("question")}
              />
              <InspectorTab
                active={inspectorView === "questionnaire"}
                label="Setări"
                icon={FileSlidersIcon}
                onClick={() => setInspectorView("questionnaire")}
              />
              <InspectorTab
                active={inspectorView === "scales"}
                label="Scări"
                icon={SlidersHorizontalIcon}
                onClick={() => setInspectorView("scales")}
              />
            </div>

            <div className="max-h-[calc(100vh-13rem)] overflow-y-auto p-4">
              {inspectorView === "question" && selectedQuestion ? (
                <QuestionInspector
                  question={selectedQuestion}
                  sectionIndex={selectedSectionIndex}
                  questionIndex={selectedQuestionIndex}
                  onUpdateQuestion={onUpdateQuestion}
                />
              ) : null}
              {inspectorView === "questionnaire" ? (
                <QuestionnaireSettings
                  definition={definition}
                  categories={categories}
                  onUpdateMetadata={onUpdateMetadata}
                  onRenameKey={onRenameKey}
                  onUpdateInstructions={onUpdateInstructions}
                />
              ) : null}
              {inspectorView === "scales" ? (
                <GlobalScales groups={scaleGroups} onUpdateScaleGroup={onUpdateScaleGroup} />
              ) : null}
            </div>
          </div>
        </aside>
      </div>
    </section>
  );
}

function InspectorTab({
  active,
  disabled,
  label,
  icon: Icon,
  onClick,
}: {
  active: boolean;
  disabled?: boolean;
  label: string;
  icon: typeof Settings2Icon;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      aria-pressed={active}
      className={cn(
        "flex min-w-0 flex-col items-center gap-1 rounded-sm px-1 py-2 text-[10px] font-semibold outline-none transition-[background-color,color,transform] duration-150 focus-visible:ring-2 focus-visible:ring-ring/45 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-40 motion-reduce:active:transform-none",
        active ? "bg-muted text-foreground" : "text-muted-foreground hover:bg-muted/65 hover:text-foreground",
      )}
    >
      <Icon aria-hidden="true" className="size-3.5" />
      <span className="truncate">{label}</span>
    </button>
  );
}

function QuestionInspector({
  question,
  sectionIndex,
  questionIndex,
  onUpdateQuestion,
}: {
  question: QuestionnaireQuestion;
  sectionIndex: number;
  questionIndex: number;
  onUpdateQuestion: QuestionnaireEditorProps["onUpdateQuestion"];
}) {
  return (
    <section aria-labelledby="question-inspector-title">
      <h2 id="question-inspector-title" className="text-sm font-semibold text-foreground">Setări întrebare</h2>
      <FieldGroup className="mt-4 gap-4">
        <Field>
          <FieldLabel>Tip</FieldLabel>
          <SelectControl
            label={`Tip întrebare ${question.code || questionIndex + 1}`}
            value={question.type}
            onChange={(event) =>
              onUpdateQuestion(sectionIndex, questionIndex, {
                type: event.target.value as QuestionnaireQuestion["type"],
                statements: event.target.value === "statement_score_set" ? (question.statements ?? []) : undefined,
              })
            }
          >
            <option value="likert">Scară Likert</option>
            <option value="single_choice">Alegere unică</option>
            <option value="statement_score_set">Set de afirmații</option>
          </SelectControl>
        </Field>
        <Field orientation="horizontal" className="rounded-md border border-border px-3 py-2.5">
          <Checkbox
            id={`question-${question.id}-required`}
            checked={question.required}
            onCheckedChange={(checked) => onUpdateQuestion(sectionIndex, questionIndex, { required: checked === true })}
          />
          <FieldLabel htmlFor={`question-${question.id}-required`} className="cursor-pointer select-none text-xs font-medium">
            Obligatoriu
          </FieldLabel>
        </Field>
        <Field>
          <FieldLabel htmlFor={`question-instructions-${question.id}`}>Indicații</FieldLabel>
          <Textarea
            id={`question-instructions-${question.id}`}
            value={question.instructions ?? ""}
            onChange={(event) => onUpdateQuestion(sectionIndex, questionIndex, { instructions: event.target.value || undefined })}
            rows={4}
            className="min-h-24 text-xs"
            placeholder="Opțional"
          />
        </Field>
      </FieldGroup>
    </section>
  );
}

function QuestionnaireSettings({
  definition,
  categories,
  onUpdateMetadata,
  onRenameKey,
  onUpdateInstructions,
}: {
  definition: QuestionnaireDefinition;
  categories: string[];
  onUpdateMetadata: QuestionnaireEditorProps["onUpdateMetadata"];
  onRenameKey: () => void;
  onUpdateInstructions: (instructions: string) => void;
}) {
  return (
    <section aria-labelledby="questionnaire-settings-title">
      <h2 id="questionnaire-settings-title" className="text-sm font-semibold text-foreground">Setări chestionar</h2>
      <FieldGroup className="mt-4 gap-4">
        <Field>
          <FieldLabel htmlFor="questionnaire-title">Nume chestionar</FieldLabel>
          <Input id="questionnaire-title" value={definition.title} onChange={(event) => onUpdateMetadata({ title: event.target.value })} />
        </Field>
        <Field>
          <FieldLabel htmlFor="questionnaire-description">Descriere</FieldLabel>
          <Textarea
            id="questionnaire-description"
            value={definition.description}
            onChange={(event) => onUpdateMetadata({ description: event.target.value })}
            rows={4}
            className="min-h-24 text-xs"
          />
        </Field>
        <Field>
          <FieldLabel>Categorie / Slug</FieldLabel>
          <SelectControl label="Categorie / Slug" value={definition.key} onChange={onRenameKey}>
            {categories.map((category) => (
              <option key={category} value={category}>{category}</option>
            ))}
          </SelectControl>
        </Field>
        <Field>
          <FieldLabel>Audiență</FieldLabel>
          <SelectControl
            label="Audiență"
            value={definition.schema.audience ?? (definition.key === "distress_drivers" ? "leadership" : "team")}
            onChange={(event) => onUpdateMetadata({ audience: event.target.value as "leadership" | "team" | "participant" })}
          >
            <option value="team">Echipă</option>
            <option value="leadership">Leadership</option>
            <option value="participant">Individual</option>
          </SelectControl>
        </Field>
        <Field>
          <FieldLabel htmlFor="questionnaire-instructions">Instrucțiuni</FieldLabel>
          <Textarea
            id="questionnaire-instructions"
            value={definition.schema.instructions ?? ""}
            onChange={(event) => onUpdateInstructions(event.target.value)}
            rows={5}
            className="min-h-28 text-xs"
          />
        </Field>
      </FieldGroup>
    </section>
  );
}

function GlobalScales({
  groups,
  onUpdateScaleGroup,
}: {
  groups: QuestionnaireScaleGroup[];
  onUpdateScaleGroup: QuestionnaireEditorProps["onUpdateScaleGroup"];
}) {
  return (
    <section aria-labelledby="global-scales-title">
      <div className="flex items-center justify-between gap-2">
        <h2 id="global-scales-title" className="text-sm font-semibold text-foreground">Scări globale de răspuns</h2>
        <span className="text-[11px] font-semibold text-muted-foreground">{groups.length}</span>
      </div>
      {groups.length > 0 ? (
        <div className="mt-4 divide-y divide-border border-y border-border">
          {groups.map((group) => (
            <div key={group.renderKey} className="py-4">
              <div className="mb-3 flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate text-xs font-semibold text-foreground">{group.title}</p>
                  <p className="mt-0.5 text-[10px] text-muted-foreground">
                    {group.questionCount} {group.questionCount === 1 ? "întrebare" : "întrebări"} · {questionTypeLabel(group.type)}
                  </p>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => onUpdateScaleGroup(group, (scale) => [...scale, nextScaleOption(scale)])}
                  aria-label={`Adaugă opțiune în scara ${group.title}`}
                  title="Adaugă opțiune"
                >
                  <PlusIcon aria-hidden="true" />
                </Button>
              </div>
              <div className="space-y-2">
                {group.scale.map((option, optionIndex) => (
                  <div key={`${group.renderKey}-${String(option.value)}-${optionIndex}`} className="grid grid-cols-[2.5rem_minmax(0,1fr)_2.25rem] items-center gap-2">
                    <span className="truncate text-[10px] font-semibold text-primary">{option.value}</span>
                    <div className="space-y-1">
                      <Input
                        aria-label={`Etichetă opțiune ${option.value}`}
                        value={option.label}
                        onChange={(event) =>
                          onUpdateScaleGroup(group, (scale) => {
                            scale[optionIndex] = { ...scale[optionIndex], label: event.target.value };
                            return scale;
                          })
                        }
                        className="h-8 text-xs"
                      />
                      <Input
                        aria-label={`Descriere opțiune ${option.value}`}
                        value={option.description ?? ""}
                        onChange={(event) =>
                          onUpdateScaleGroup(group, (scale) => {
                            scale[optionIndex] = { ...scale[optionIndex], description: event.target.value || undefined };
                            return scale;
                          })
                        }
                        className="h-8 text-xs"
                        placeholder="Descriere opțională"
                      />
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => onUpdateScaleGroup(group, (scale) => scale.filter((_, index) => index !== optionIndex))}
                      aria-label={`Șterge opțiunea ${option.label}`}
                      title="Șterge opțiunea"
                    >
                      <Trash2Icon aria-hidden="true" />
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      ) : (
        <p className="mt-4 text-xs text-muted-foreground">Nu există scări definite.</p>
      )}
    </section>
  );
}

function LocalScaleEditor({
  sectionId,
  question,
  expanded,
  onToggle,
  onChange,
}: {
  sectionId: string;
  question: QuestionnaireQuestion;
  expanded: boolean;
  onToggle: () => void;
  onChange: (scale: QuestionnaireScaleOption[]) => void;
}) {
  const preview = question.scale.slice(0, 4).map((option) => option.label).join(" / ");
  return (
    <section aria-labelledby={`local-scale-${sectionId}-${question.id}`} className="mt-6 border-t border-border pt-5">
      <div className="flex items-center justify-between gap-3">
        <div className="min-w-0">
          <h3 id={`local-scale-${sectionId}-${question.id}`} className="text-sm font-semibold text-foreground">Scară de răspuns</h3>
          <p className="mt-1 truncate text-xs text-muted-foreground">
            {question.scale.length} opțiuni{preview ? ` · ${preview}` : ""}
          </p>
        </div>
        <Button type="button" variant="outline" size="sm" onClick={onToggle} aria-expanded={expanded}>
          {expanded ? "Ascunde scara" : "Editează scara locală"}
        </Button>
      </div>
      {expanded ? (
        <div className="mt-4 divide-y divide-border border-y border-border">
          {question.scale.map((option, optionIndex) => (
            <div key={`${String(option.value)}-${optionIndex}`} className="grid grid-cols-[3rem_minmax(0,1fr)_2.25rem] items-center gap-2 py-2">
              <span className="text-xs font-semibold text-primary">{option.value}</span>
              <div className="grid gap-2 md:grid-cols-2">
                <Input
                  value={option.label}
                  onChange={(event) => {
                    const scale = [...question.scale];
                    scale[optionIndex] = { ...scale[optionIndex], label: event.target.value };
                    onChange(scale);
                  }}
                  className="h-9 text-xs"
                  placeholder="Etichetă"
                />
                <Input
                  value={option.description ?? ""}
                  onChange={(event) => {
                    const scale = [...question.scale];
                    scale[optionIndex] = { ...scale[optionIndex], description: event.target.value || undefined };
                    onChange(scale);
                  }}
                  className="h-9 text-xs"
                  placeholder="Descriere opțională pentru această opțiune"
                />
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={() => onChange(question.scale.filter((_, index) => index !== optionIndex))}
                aria-label={`Șterge opțiunea ${option.label}`}
                title="Șterge opțiunea"
              >
                <Trash2Icon aria-hidden="true" />
              </Button>
            </div>
          ))}
          <div className="py-2">
            <Button type="button" variant="ghost" size="xs" onClick={() => onChange([...question.scale, nextScaleOption(question.scale)])}>
              <PlusIcon data-icon="inline-start" aria-hidden="true" />
              Adaugă opțiune
            </Button>
          </div>
        </div>
      ) : null}
    </section>
  );
}

function StatementParticipantScaleEditor({
  statement,
  onChange,
}: {
  statement: QuestionnaireStatement;
  onChange: (scale: QuestionnaireScaleOption[]) => void;
}) {
  const scale = statement.scale ?? [];

  return (
    <section className="ml-[3.25rem] mt-3 border-l-2 border-primary/20 pl-3">
      <p className="text-xs font-semibold text-foreground">Răspunsuri văzute de participant</p>
      <div className="mt-2 divide-y divide-border border-y border-border">
        {scale.map((option, optionIndex) => (
          <div
            key={`${String(option.value)}-${optionIndex}`}
            className="grid grid-cols-[2.5rem_minmax(0,1fr)] items-center gap-2 py-2"
          >
            <span className="text-xs font-semibold tabular-nums text-primary">{option.value}</span>
            <Input
              aria-label={`Descriere participant ${statement.code} ${option.value}`}
              value={option.description ?? ""}
              onChange={(event) => {
                const nextScale = [...scale];
                nextScale[optionIndex] = {
                  ...nextScale[optionIndex],
                  description: event.target.value || undefined,
                };
                onChange(nextScale);
              }}
              className="h-9 text-xs"
              placeholder={`Descriere pentru scorul ${option.value}`}
            />
          </div>
        ))}
      </div>
    </section>
  );
}
