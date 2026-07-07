"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";

import {
  saveQuestionnaireResponse,
  submitQuestionnaireResponse,
  type QuestionnaireAnswerValue,
  type QuestionnaireDefinition,
  type QuestionnaireQuestion,
  type QuestionnaireScaleOption,
} from "@/api/questionnaires";

type AnswerState = Record<string, QuestionnaireAnswerValue>;

const AUTOSAVE_DELAY_MS = 450;

type QuestionnaireRunnerProps = {
  definition: QuestionnaireDefinition;
  assignmentId?: string;
  initialAnswers?: AnswerState;
  initialStatus?: "draft" | "submitted";
  returnHref?: string;
  returnLabel?: string;
  targetLabel?: string;
};

function answerKey(question: QuestionnaireQuestion, statementId?: string): string {
  return statementId ? `${question.id}:${statementId}` : question.id;
}

function numericScaleOptionValue(option: QuestionnaireScaleOption): number | null {
  if (typeof option.value === "number" && Number.isInteger(option.value)) {
    return option.value;
  }
  if (typeof option.value === "string" && /^\d+$/.test(option.value)) {
    return Number(option.value);
  }
  return null;
}

function isTenPointScale(scale: QuestionnaireScaleOption[]): boolean {
  if (scale.length !== 10) return false;
  const values = scale.map(numericScaleOptionValue);
  if (values.some((value) => value === null)) return false;
  return values.every((value, index) => value === index + 1);
}

type DiscreteScaleSliderProps = {
  label: string;
  scale: QuestionnaireScaleOption[];
  selectedValue: QuestionnaireAnswerValue | undefined;
  onChange: (value: QuestionnaireAnswerValue) => void;
};

function DiscreteScaleSlider({ label, scale, selectedValue, onChange }: DiscreteScaleSliderProps) {
  const selectedDescriptionId = useId();
  const selectedOption = scale.find((option) => option.value === selectedValue);
  const selectedNumber = typeof selectedValue === "number" ? selectedValue : Number(selectedValue);
  const sliderValue = Number.isInteger(selectedNumber) && selectedNumber >= 1 && selectedNumber <= 10
    ? selectedNumber
    : 1;
  const valueText = selectedOption
    ? `${sliderValue}: ${selectedOption.label}${selectedOption.description ? `. ${selectedOption.description}` : ""}`
    : `${sliderValue}: Alege un scor de la 1 la 10.`;

  return (
    <div data-testid="question-response-group" className="mt-4 rounded-xl border border-[var(--border)] bg-surface px-4 py-4">
      <input
        type="range"
        min={1}
        max={10}
        step={1}
        value={sliderValue}
        onChange={(event) => {
          const numericValue = Number(event.target.value);
          const option = scale.find((scaleOption) => numericScaleOptionValue(scaleOption) === numericValue);
          onChange(option?.value ?? numericValue);
        }}
        aria-label={label}
        aria-describedby={selectedDescriptionId}
        aria-valuetext={valueText}
        className="w-full accent-burgundy"
      />
      <div className="mt-2 grid grid-cols-10 text-center text-[11px] font-bold text-foreground/50">
        {scale.map((option) => (
          <span key={String(option.value)}>{numericScaleOptionValue(option)}</span>
        ))}
      </div>
      <div id={selectedDescriptionId} className="mt-3 min-h-10 rounded-xl border border-[var(--border)] bg-background px-3 py-2 text-sm">
        {selectedOption ? (
          <>
            <p className="font-bold text-foreground">Scor selectat: {selectedOption.label}</p>
            {selectedOption.description ? (
              <p className="mt-1 text-xs font-medium leading-5 text-foreground/56">{selectedOption.description}</p>
            ) : null}
          </>
        ) : (
          <p className="font-semibold text-foreground/52">Alege un scor de la 1 la 10.</p>
        )}
      </div>
    </div>
  );
}

export function QuestionnaireRunner({
  definition,
  assignmentId,
  initialAnswers,
  initialStatus = "draft",
  returnHref = "/participant/questionnaires",
  returnLabel = "Înapoi la chestionare",
  targetLabel,
}: QuestionnaireRunnerProps) {
  const router = useRouter();
  const [answers, setAnswers] = useState<AnswerState>(initialAnswers ?? {});
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "submitted" | "error">(
    initialStatus === "submitted" ? "submitted" : "idle",
  );
  const [saveError, setSaveError] = useState<string | null>(null);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const questionnaireDetailsId = useId();
  const latestAnswersRef = useRef<AnswerState>(initialAnswers ?? {});
  const autosaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveSequenceRef = useRef(0);
  const autosaveInFlightRef = useRef(false);
  const autosaveInFlightPromiseRef = useRef<Promise<void> | null>(null);
  const queuedAutosaveRef = useRef<{ assignmentId: string; sequence: number } | null>(null);

  useEffect(() => {
    const nextAnswers = initialAnswers ?? {};
    latestAnswersRef.current = nextAnswers;
    if (autosaveTimerRef.current) {
      clearTimeout(autosaveTimerRef.current);
      autosaveTimerRef.current = null;
    }
    setSaveState(initialStatus === "submitted" ? "submitted" : "idle");
    setSaveError(null);
    setAnswers(nextAnswers);
  }, [initialAnswers, initialStatus, assignmentId]);

  useEffect(() => () => {
    if (autosaveTimerRef.current) {
      clearTimeout(autosaveTimerRef.current);
    }
  }, []);
  useEffect(() => {
    if (!detailsOpen) return undefined;

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setDetailsOpen(false);
      }
    }

    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [detailsOpen]);
  const questions = definition.schema.sections.flatMap((section) => section.questions);
  const requiredAnswerKeys = useMemo(
    () =>
      questions.flatMap((question) => {
        if (question.type === "statement_score_set") {
          return (question.statements ?? []).map((statement) => answerKey(question, statement.id));
        }

        return [answerKey(question)];
      }),
    [questions],
  );
  const answeredCount = requiredAnswerKeys.filter((key) => answers[key] !== undefined).length;
  const progress = requiredAnswerKeys.length > 0
    ? Math.round((answeredCount / requiredAnswerKeys.length) * 100)
    : 0;
  const canSubmit = answeredCount === requiredAnswerKeys.length && Boolean(assignmentId);
  const isComplete = saveState === "submitted";
  const targetCopy = evaluationTargetCopy(targetLabel, definition.key);
  const hasQuestionnaireDetails = Boolean(definition.description || definition.schema.instructions);

  async function handleAnswerChange(key: string, value: QuestionnaireAnswerValue) {
    if (isComplete) return;
    const newAnswers = { ...latestAnswersRef.current, [key]: value };
    latestAnswersRef.current = newAnswers;
    setAnswers(newAnswers);

    if (assignmentId) {
      scheduleAutosave(assignmentId);
    }
  }

  function scheduleAutosave(currentAssignmentId: string) {
    if (autosaveTimerRef.current) {
      clearTimeout(autosaveTimerRef.current);
    }

    const sequence = saveSequenceRef.current + 1;
    saveSequenceRef.current = sequence;
    setSaveState("saving");
    setSaveError(null);
    autosaveTimerRef.current = setTimeout(() => {
      void runAutosave(currentAssignmentId, sequence);
    }, AUTOSAVE_DELAY_MS);
  }

  async function runAutosave(currentAssignmentId: string, sequence: number) {
    if (autosaveInFlightRef.current) {
      queuedAutosaveRef.current = { assignmentId: currentAssignmentId, sequence };
      return;
    }

    autosaveInFlightRef.current = true;
    const request = (async () => {
      await saveQuestionnaireResponse(currentAssignmentId, latestAnswersRef.current);
      if (saveSequenceRef.current === sequence) {
        setSaveState("saved");
        setSaveError(null);
      }
    })();
    autosaveInFlightPromiseRef.current = request;
    try {
      await request;
    } catch (error) {
      if (saveSequenceRef.current === sequence) {
        setSaveState("error");
        setSaveError(errorMessage(error, "A apărut o eroare la salvarea draftului."));
      }
    } finally {
      autosaveInFlightRef.current = false;
      if (autosaveInFlightPromiseRef.current === request) {
        autosaveInFlightPromiseRef.current = null;
      }
      const queued = queuedAutosaveRef.current;
      queuedAutosaveRef.current = null;
      if (queued && queued.sequence === saveSequenceRef.current) {
        void runAutosave(queued.assignmentId, queued.sequence);
      }
    }
  }

  async function saveDraft() {
    if (!assignmentId) {
      router.push(returnHref);
      return;
    }
    if (autosaveTimerRef.current) {
      clearTimeout(autosaveTimerRef.current);
      autosaveTimerRef.current = null;
    }
    saveSequenceRef.current += 1;
    setSaveState("saving");
    setSaveError(null);
    try {
      await autosaveInFlightPromiseRef.current?.catch(() => undefined);
      await saveQuestionnaireResponse(assignmentId, latestAnswersRef.current);
      setSaveState("saved");
      setSaveError(null);
      router.push(returnHref);
    } catch (error) {
      setSaveState("error");
      setSaveError(errorMessage(error, "A apărut o eroare la salvarea draftului."));
    }
  }

  async function submit() {
    if (!canSubmit || !assignmentId) return;
    const confirmed = window.confirm(
      "Trimiți răspunsurile finale? După trimitere nu le mai poți modifica decât dacă trainerul redeschide sarcina.",
    );
    if (!confirmed) return;
    if (autosaveTimerRef.current) {
      clearTimeout(autosaveTimerRef.current);
      autosaveTimerRef.current = null;
    }
    saveSequenceRef.current += 1;
    setSaveState("saving");
    setSaveError(null);
    try {
      await autosaveInFlightPromiseRef.current?.catch(() => undefined);
      await submitQuestionnaireResponse(assignmentId, latestAnswersRef.current);
      setSaveState("submitted");
      setSaveError(null);
      router.push(returnHref);
    } catch (error) {
      setSaveState("error");
      setSaveError(errorMessage(error, "A apărut o eroare la trimiterea răspunsurilor."));
    }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_17rem] lg:items-start">
      <div className="surface-panel overflow-hidden">
        <section className="border-b border-[var(--border)] px-5 py-5 md:px-6">
          <div className="mb-4">
            <button
              onClick={() => router.push(returnHref)}
              className="tap-soft -ml-3 inline-flex items-center gap-2 rounded-full px-3 py-2 text-sm font-bold text-foreground/60 transition-colors hover:bg-surface-muted hover:text-burgundy"
            >
              <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.5" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="m15 18-6-6 6-6" />
              </svg>
              {returnLabel}
            </button>
          </div>
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-burgundy/75">
            Versiunea {definition.version}
          </p>
          <h2 className="mt-2 text-2xl font-semibold text-foreground">{definition.title}</h2>
          <div className="mt-4 rounded-xl border border-burgundy/18 bg-surface-muted px-4 py-3">
            {targetCopy.eyebrow ? (
              <p className="text-xs font-bold uppercase tracking-[0.12em] text-burgundy/75">
                {targetCopy.eyebrow}
              </p>
            ) : null}
            <p className={`${targetCopy.eyebrow ? "mt-1" : ""} text-sm font-semibold leading-6 text-foreground`}>
              {targetCopy.text}
            </p>
          </div>
          {hasQuestionnaireDetails ? (
            <div className="mt-4">
              <button
                type="button"
                aria-haspopup="dialog"
                aria-expanded={detailsOpen}
                aria-controls={questionnaireDetailsId}
                onClick={() => setDetailsOpen(true)}
                className="tap-soft rounded-full border border-burgundy/30 bg-surface px-4 py-2 text-sm font-bold text-burgundy hover:border-burgundy/60 hover:bg-burgundy/5"
              >
                Detalii chestionar
              </button>
            </div>
          ) : null}
        </section>

        {detailsOpen ? (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/35 px-4 py-6"
            onMouseDown={(event) => {
              if (event.target === event.currentTarget) setDetailsOpen(false);
            }}
          >
            <section
              id={questionnaireDetailsId}
              role="dialog"
              aria-modal="true"
              aria-labelledby={`${questionnaireDetailsId}-title`}
              className="w-full max-w-xl rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-xl"
            >
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.14em] text-burgundy/75">Chestionar</p>
                  <h3 id={`${questionnaireDetailsId}-title`} className="mt-1 text-xl font-semibold text-foreground">
                    Detalii chestionar
                  </h3>
                </div>
                <button
                  type="button"
                  onClick={() => setDetailsOpen(false)}
                  aria-label="Închide detaliile"
                  className="tap-soft rounded-full border border-[var(--border)] px-3 py-1.5 text-sm font-bold text-foreground/64 hover:border-burgundy/30 hover:text-burgundy"
                >
                  Închide
                </button>
              </div>
              {definition.description ? (
                <p className="mt-4 text-sm leading-6 text-foreground/70">{definition.description}</p>
              ) : null}
              {definition.schema.instructions ? (
                <p className="mt-4 rounded-xl border border-burgundy/18 bg-surface-muted px-4 py-3 text-sm leading-6 text-foreground/66">
                  {definition.schema.instructions}
                </p>
              ) : null}
            </section>
          </div>
        ) : null}

        {isComplete ? (
          <CompletionPanel
            answeredCount={answeredCount}
            total={requiredAnswerKeys.length}
            returnHref={returnHref}
            returnLabel={returnLabel}
          />
        ) : (
          definition.schema.sections.map((section) => (
            <section key={section.id} className="border-b border-[var(--border)] last:border-b-0">
              <div className="bg-surface-muted px-5 py-3 md:px-6">
                <h3 className="text-sm font-bold text-foreground/72">{section.title}</h3>
              </div>
              <div className="divide-y divide-[var(--border)]">
                {section.questions.map((question, index) => (
                  <article key={question.id} className="px-5 py-5 md:px-6">
                    <div className="grid gap-3 md:grid-cols-[1.5rem_1fr]">
                      <span className="pt-0.5 text-sm font-bold tabular-nums text-burgundy/72">{index + 1}</span>
                      <div className="min-w-0">
                        <h4 className="text-base font-semibold leading-6 text-foreground">{question.label}</h4>
                        {question.instructions ? (
                          <p className="mt-2 text-sm leading-6 text-foreground/58">{question.instructions}</p>
                        ) : null}
                        {question.type === "likert" ? (
                          <LikertQuestion
                            question={question}
                            answers={answers}
                            onAnswerChange={handleAnswerChange}
                          />
                        ) : question.type === "single_choice" ? (
                          <SingleChoiceQuestion
                            question={question}
                            answers={answers}
                            onAnswerChange={handleAnswerChange}
                          />
                        ) : (
                          <StatementSetQuestion
                            question={question}
                            answers={answers}
                            onAnswerChange={handleAnswerChange}
                          />
                        )}
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </section>
          ))
        )}
      </div>

      <aside className="surface-panel p-4 lg:sticky lg:top-8">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm font-semibold text-foreground">Progres</p>
          <p className="text-sm font-semibold tabular-nums text-foreground/62">
            {answeredCount}/{requiredAnswerKeys.length}
          </p>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-surface-muted">
          <div className="h-full rounded-full bg-burgundy transition-all" style={{ width: `${progress}%` }} />
        </div>
        <p className="mt-3 text-xs font-semibold text-foreground/52">{progress}% completat</p>

        <div className="mt-5 grid gap-2">
          <button
            type="button"
            className="tap-soft rounded-full border border-burgundy bg-surface px-4 py-3 text-sm font-bold text-burgundy disabled:cursor-not-allowed disabled:opacity-45"
            disabled={!assignmentId || saveState === "saving" || isComplete}
            onClick={saveDraft}
          >
            Salvează draft
          </button>
          <button
            type="button"
            className="tap-soft rounded-full bg-burgundy px-4 py-3 text-sm font-bold text-white shadow-brand disabled:cursor-not-allowed disabled:opacity-45"
            disabled={!canSubmit || saveState === "saving" || isComplete}
            onClick={submit}
          >
            Trimite răspunsurile
          </button>
        </div>
        <p className="mt-3 text-xs leading-5 text-foreground/55">
          {assignmentId
            ? saveState === "error" && saveError
              ? saveError
              : statusMessage(saveState)
            : "Linkul demo nu are încă o sarcină reală pentru salvare."}
        </p>
      </aside>
    </div>
  );
}

function evaluationTargetCopy(
  targetLabel: string | undefined,
  questionnaireKey: string,
): { eyebrow?: string; text: string } {
  const isReview360 = isReview360Questionnaire(questionnaireKey);
  const cleaned = targetLabel?.trim();
  if (isReview360) {
    const safeTarget = safeReviewTargetLabel(targetLabel);
    return safeTarget
      ? {
          text: `Completezi pentru ${safeTarget}`,
        }
      : {
          eyebrow: "Evaluezi",
          text: "Completezi feedback pentru persoana indicată în această sarcină.",
        };
  }

  if (!cleaned || cleaned.toLocaleLowerCase("ro-RO") === "autoevaluare") {
    return {
      eyebrow: "Autoevaluare",
      text: "Răspunzi despre propria ta experiență în acest proiect.",
    };
  }

  return {
    eyebrow: "Evaluezi",
    text: `Răspunzi pentru ${cleaned}. După trimitere, această persoană nu mai poate fi redeschisă din sarcina ta.`,
  };
}

function isReview360Questionnaire(questionnaireKey: string): boolean {
  return questionnaireKey === "boss_360" || questionnaireKey === "boss_360_en" || questionnaireKey === "icare";
}

function safeReviewTargetLabel(value?: string): string {
  const cleaned = value?.trim().replace(/\s+/g, " ") ?? "";
  if (!cleaned || cleaned.toLocaleLowerCase("ro-RO") === "autoevaluare") return "";
  if (cleaned.includes("@")) return "";
  if (/[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/i.test(cleaned)) {
    return "";
  }
  return cleaned;
}

function statusMessage(status: "idle" | "saving" | "saved" | "submitted" | "error"): string {
  if (status === "saving") return "Se salvează...";
  if (status === "saved") return "Draft salvat.";
  if (status === "submitted") return "Răspunsuri trimise. Poți reveni la lista de chestionare.";
  if (status === "error") return "A apărut o eroare la salvare.";
  return "Poți salva un draft oricând și poți trimite după ce ai completat toate câmpurile.";
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof Error && error.message.trim() ? error.message : fallback;
}

function CompletionPanel({
  answeredCount,
  total,
  returnHref,
  returnLabel,
}: {
  answeredCount: number;
  total: number;
  returnHref: string;
  returnLabel: string;
}) {
  return (
    <section className="px-5 py-10 text-center md:px-6">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-success/35 text-xl font-semibold text-success-ink">
        <CheckIcon />
      </div>
      <h3 className="mt-5 text-2xl font-semibold text-foreground">Răspunsurile au fost trimise</h3>
      <p className="mx-auto mt-3 max-w-lg text-sm leading-6 text-foreground/62">
        Am înregistrat {answeredCount}/{total} răspunsuri pentru această sarcină. Persoana evaluată nu vede răspunsuri
        individuale; trainerul lucrează cu raportarea configurată pentru proiect.
      </p>
      <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
        <Link
          href={returnHref}
          className="tap-soft rounded-full bg-burgundy px-4 py-3 text-sm font-semibold text-white"
        >
          {returnLabel}
        </Link>
      </div>
    </section>
  );
}

type QuestionInputProps = {
  question: QuestionnaireQuestion;
  answers: AnswerState;
  onAnswerChange: (key: string, value: QuestionnaireAnswerValue) => void;
};

function LikertQuestion({ question, answers, onAnswerChange }: QuestionInputProps) {
  const key = answerKey(question);

  if (isTenPointScale(question.scale)) {
    return (
      <DiscreteScaleSlider
        label={question.label}
        scale={question.scale}
        selectedValue={answers[key]}
        onChange={(value) => onAnswerChange(key, value)}
      />
    );
  }

  return (
    <div data-testid="question-response-group" className="mt-4 grid gap-2 sm:grid-cols-3">
      {question.scale.map((option) => {
        const selected = answers[key] === option.value;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onAnswerChange(key, option.value)}
            className={[
              "tap-soft min-h-11 rounded-full border px-3 py-2.5 text-sm font-bold",
              selected
                ? "border-burgundy bg-burgundy text-white shadow-sm"
                : "border-[var(--border)] bg-background text-foreground/70 hover:border-burgundy/45 hover:text-burgundy",
            ].join(" ")}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}

function SingleChoiceQuestion({ question, answers, onAnswerChange }: QuestionInputProps) {
  const key = answerKey(question);

  return (
    <div data-testid="question-response-group" className="mt-4 grid gap-2 sm:grid-cols-2">
      {question.scale.map((option) => {
        const selected = answers[key] === option.value;
        return (
          <button
            key={String(option.value)}
            type="button"
            onClick={() => onAnswerChange(key, option.value)}
            className={[
              "tap-soft rounded-full border px-3 py-3 text-left text-sm transition-colors",
              selected
                ? "border-burgundy bg-burgundy text-white shadow-sm"
                : "border-[var(--border)] bg-background text-foreground/72 hover:border-burgundy/45 hover:text-burgundy",
            ].join(" ")}
          >
            <span className="block font-bold">{option.label}</span>
            {option.description ? (
              <span className={["mt-1 block text-xs leading-5", selected ? "text-white/72" : "text-foreground/52"].join(" ")}>
                {option.description}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}

function StatementSetQuestion({ question, answers, onAnswerChange }: QuestionInputProps) {
  return (
    <div className="mt-4 overflow-hidden rounded-xl border border-[var(--border)]">
      {(question.statements ?? []).map((statement) => {
        const key = answerKey(question, statement.id);
        const scale = statement.scale?.length ? statement.scale : question.scale;
        const selectedValue = answers[key];
        return (
          <div
            key={statement.id}
            className="border-b border-[var(--border)] bg-surface px-4 py-4 last:border-b-0"
          >
            <p className="text-sm font-medium leading-6 text-foreground/72">
              <span className="mr-2 font-semibold text-burgundy">{statement.code}.</span>
              {statement.label}
            </p>
            {isTenPointScale(scale) ? (
              <DiscreteScaleSlider
                label={statement.label}
                scale={scale}
                selectedValue={selectedValue}
                onChange={(value) => onAnswerChange(key, value)}
              />
            ) : (
              <div data-testid="question-response-group" className="mt-3 grid gap-2">
                {scale.map((option) => {
                  const selected = selectedValue === option.value;
                  return (
                    <button
                      key={String(option.value)}
                      type="button"
                      onClick={() => onAnswerChange(key, option.value)}
                      className={[
                        "tap-soft rounded-xl border px-3 py-2.5 text-left text-xs transition-colors",
                        selected
                          ? "border-burgundy bg-burgundy text-white shadow-sm"
                          : "border-[var(--border)] bg-background text-foreground/70 hover:border-burgundy/45 hover:bg-surface-muted hover:text-burgundy",
                      ].join(" ")}
                    >
                      <span className="block text-sm font-bold">{option.label}</span>
                      {option.description ? (
                        <span className={["mt-1 block leading-5", selected ? "text-white/76" : "text-foreground/56"].join(" ")}>
                          {option.description}
                        </span>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

function CheckIcon() {
  return (
    <svg aria-hidden="true" className="h-6 w-6" viewBox="0 0 24 24" fill="none">
      <path d="m6.5 12.5 3.2 3.2 7.8-8.4" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.4" />
    </svg>
  );
}
