"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState } from "react";
import { ArrowLeftIcon, CheckIcon, Loader2Icon } from "lucide-react";

import {
  isQuestionnaireSessionError,
  saveQuestionnaireResponse,
  saveSecureQuestionnaireResponse,
  submitQuestionnaireResponse,
  submitSecureQuestionnaireResponse,
  type QuestionnaireAnswerValue,
  type QuestionnaireDefinition,
  type QuestionnaireQuestion,
  type QuestionnaireScaleOption,
} from "@/api/questionnaires";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { Button } from "@/components/ui/button";
import { ModalLayer } from "@/components/ui/modal-layer";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/utils/cn";

type AnswerState = Record<string, QuestionnaireAnswerValue>;
type SaveState = "idle" | "saving" | "saved" | "submitted" | "error";
type ActiveOperation = "autosave" | "exit" | "submit" | null;

const AUTOSAVE_DELAY_MS = 450;

export type QuestionnaireRunnerProps = {
  definition: QuestionnaireDefinition;
  assignmentId?: string;
  initialAnswers?: AnswerState;
  initialStatus?: "draft" | "submitted";
  returnHref?: string;
  returnLabel?: string;
  targetLabel?: string;
  secureInviteToken?: string;
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
  disabled?: boolean;
};

function DiscreteScaleSlider({ label, scale, selectedValue, onChange, disabled }: DiscreteScaleSliderProps) {
  const selectedDescriptionId = useId();
  const selectedOption = scale.find((option) => option.value === selectedValue);
  const hasSelectedOption = selectedOption !== undefined;
  const selectedNumber = typeof selectedValue === "number" ? selectedValue : Number(selectedValue);
  const sliderValue = hasSelectedOption && Number.isInteger(selectedNumber) && selectedNumber >= 1 && selectedNumber <= 10
    ? selectedNumber
    : 5;
  const valueText = selectedOption
    ? `${sliderValue}: ${selectedOption.label}${selectedOption.description ? `. ${selectedOption.description}` : ""}`
    : "Neselectat. Alege un scor de la 1 la 10.";

  return (
    <div
      data-testid="question-response-group"
      data-selected={hasSelectedOption || undefined}
      className="mt-4 rounded-lg border border-border bg-surface px-4 py-4 shadow-[0_1px_0_rgba(24,24,27,0.04)] data-[selected=true]:border-burgundy/35"
    >
      <Slider
        min={1}
        max={10}
        step={1}
        value={[sliderValue]}
        disabled={disabled}
        onValueChange={(value) => {
          const numericValue = value[0] ?? sliderValue;
          const option = scale.find((scaleOption) => numericScaleOptionValue(scaleOption) === numericValue);
          onChange(option?.value ?? numericValue);
        }}
        thumbLabel={label}
        thumbDescriptionId={selectedDescriptionId}
        thumbValueText={valueText}
        className="py-2"
      />
      <div className="mt-2 grid grid-cols-10 text-center text-[11px] font-bold text-muted-foreground">
        {scale.map((option) => (
          <span key={String(option.value)}>{numericScaleOptionValue(option)}</span>
        ))}
      </div>
      <div id={selectedDescriptionId} className="mt-3 min-h-10 rounded-lg border border-border bg-muted px-3 py-2 text-sm">
        {selectedOption ? (
          <>
            <p className="font-bold text-foreground">Scor selectat: {selectedOption.label}</p>
            {selectedOption.description ? (
              <p className="mt-1 text-xs font-medium leading-5 text-muted-foreground">{selectedOption.description}</p>
            ) : null}
          </>
        ) : (
          <p className="font-semibold text-muted-foreground">Alege un scor de la 1 la 10. Cursorul este poziționat neutru până selectezi.</p>
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
  secureInviteToken,
}: QuestionnaireRunnerProps) {
  const router = useRouter();
  const [answers, setAnswers] = useState<AnswerState>(initialAnswers ?? {});
  const [saveState, setSaveState] = useState<SaveState>(
    initialStatus === "submitted" ? "submitted" : "idle",
  );
  const [activeOperation, setActiveOperation] = useState<ActiveOperation>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [submitConfirmOpen, setSubmitConfirmOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [isExiting, setIsExiting] = useState(false);
  const questionnaireDetailsId = useId();
  const latestAnswersRef = useRef<AnswerState>(initialAnswers ?? {});
  const autosaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saveSequenceRef = useRef(0);
  const autosaveInFlightRef = useRef(false);
  const autosaveInFlightPromiseRef = useRef<Promise<void> | null>(null);
  const queuedAutosaveRef = useRef<{ assignmentId: string; sequence: number } | null>(null);
  const exitSubmittingRef = useRef(false);
  const finalSubmittingRef = useRef(false);

  useEffect(() => {
    const nextAnswers = initialAnswers ?? {};
    latestAnswersRef.current = nextAnswers;
    if (autosaveTimerRef.current) {
      clearTimeout(autosaveTimerRef.current);
      autosaveTimerRef.current = null;
    }
    setSaveState(initialStatus === "submitted" ? "submitted" : "idle");
    setActiveOperation(null);
    setSaveError(null);
    setAnswers(nextAnswers);
  }, [initialAnswers, initialStatus, assignmentId]);

  useEffect(() => () => {
    if (autosaveTimerRef.current) {
      clearTimeout(autosaveTimerRef.current);
    }
  }, []);
  const questions = useMemo(
    () => definition.schema.sections.flatMap((section) => section.questions),
    [definition.schema.sections],
  );
  const requiredAnswerKeys = useMemo(
    () =>
      questions.flatMap((question) => {
        if (!question.required) return [];
        if (question.type === "statement_score_set") {
          return (question.statements ?? []).map((statement) => answerKey(question, statement.id));
        }

        return [answerKey(question)];
      }),
    [questions],
  );
  const answeredCount = useMemo(
    () => requiredAnswerKeys.filter((key) => answers[key] !== undefined).length,
    [answers, requiredAnswerKeys],
  );
  const progress = requiredAnswerKeys.length > 0
    ? Math.round((answeredCount / requiredAnswerKeys.length) * 100)
    : 0;
  const canSubmit = answeredCount === requiredAnswerKeys.length && Boolean(assignmentId);
  const isComplete = saveState === "submitted";
  const responsesLocked = isComplete || isExiting || activeOperation === "submit";
  const targetCopy = evaluationTargetCopy(targetLabel, definition.key);
  const hideIcareMeasurementContext = isReview360Questionnaire(definition.key);
  const hasQuestionnaireDetails = Boolean(definition.description || definition.schema.instructions);

  useEffect(() => {
    if (saveState !== "saved") return;
    const timer = window.setTimeout(() => setSaveState("idle"), 1800);
    return () => window.clearTimeout(timer);
  }, [saveState]);

  async function handleAnswerChange(key: string, value: QuestionnaireAnswerValue) {
    if (responsesLocked) return;
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
    setActiveOperation("autosave");
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
      if (secureInviteToken) {
        await saveSecureQuestionnaireResponse(
          secureInviteToken,
          currentAssignmentId,
          latestAnswersRef.current,
        );
      } else {
        await saveQuestionnaireResponse(currentAssignmentId, latestAnswersRef.current);
      }
      if (saveSequenceRef.current === sequence) {
        setSaveState("saved");
        setActiveOperation(null);
        setSaveError(null);
      }
    })();
    autosaveInFlightPromiseRef.current = request;
    try {
      await request;
    } catch (error) {
      if (saveSequenceRef.current === sequence) {
        setSaveState("error");
        setActiveOperation(null);
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

  async function saveDraftAndExit() {
    if (exitSubmittingRef.current) return;

    if (!assignmentId || isComplete) {
      router.push(returnHref);
      return;
    }

    exitSubmittingRef.current = true;
    setIsExiting(true);
    if (autosaveTimerRef.current) {
      clearTimeout(autosaveTimerRef.current);
      autosaveTimerRef.current = null;
    }
    saveSequenceRef.current += 1;
    setSaveState("saving");
    setActiveOperation("exit");
    setSaveError(null);
    try {
      await autosaveInFlightPromiseRef.current?.catch(() => undefined);
      if (secureInviteToken) {
        await saveSecureQuestionnaireResponse(
          secureInviteToken,
          assignmentId,
          latestAnswersRef.current,
        );
      } else {
        await saveQuestionnaireResponse(assignmentId, latestAnswersRef.current);
      }
      setSaveState("saved");
      setActiveOperation(null);
      setSaveError(null);
      router.push(returnHref);
    } catch (error) {
      exitSubmittingRef.current = false;
      setIsExiting(false);
      setSaveState("error");
      setActiveOperation(null);
      setSaveError(errorMessage(error, "A apărut o eroare la salvarea draftului."));
    }
  }

  function submit() {
    if (!canSubmit || !assignmentId) return;
    setSubmitConfirmOpen(true);
  }

  async function confirmSubmit() {
    if (finalSubmittingRef.current) return;
    if (!canSubmit || !assignmentId) return;
    finalSubmittingRef.current = true;
    setSubmitConfirmOpen(false);
    if (autosaveTimerRef.current) {
      clearTimeout(autosaveTimerRef.current);
      autosaveTimerRef.current = null;
    }
    saveSequenceRef.current += 1;
    setSaveState("saving");
    setActiveOperation("submit");
    setSaveError(null);
    try {
      await autosaveInFlightPromiseRef.current?.catch(() => undefined);
      if (secureInviteToken) {
        await submitSecureQuestionnaireResponse(
          secureInviteToken,
          assignmentId,
          latestAnswersRef.current,
        );
      } else {
        await submitQuestionnaireResponse(assignmentId, latestAnswersRef.current);
      }
      setSaveState("submitted");
      setActiveOperation(null);
      setSaveError(null);
      router.push(returnHref);
    } catch (error) {
      finalSubmittingRef.current = false;
      setSaveState("error");
      setActiveOperation(null);
      setSaveError(errorMessage(error, "A apărut o eroare la trimiterea răspunsurilor."));
    }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_17rem] lg:items-start">
      <div className="overflow-hidden rounded-lg border border-border bg-surface shadow-[0_1px_0_rgba(24,24,27,0.04)]">
        <section className="border-b border-border px-5 py-5 md:px-6">
          <div className="flex items-center gap-4">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => void saveDraftAndExit()}
              aria-label={returnLabel}
              disabled={isExiting}
              className="-ml-2 text-muted-foreground hover:text-burgundy"
            >
              {isExiting ? (
                <Loader2Icon data-icon="inline-start" aria-hidden="true" className="animate-spin" />
              ) : (
                <ArrowLeftIcon aria-hidden="true" strokeWidth={2.3} />
              )}
              <span aria-hidden="true">{isExiting ? "Salvăm draftul" : "Înapoi"}</span>
            </Button>
          </div>

          <div className="mt-5 max-w-3xl">
            <p className="text-xs font-semibold uppercase tracking-[0.14em] text-burgundy">
              {targetCopy.eyebrow}
            </p>
            <h2 className="mt-2 text-3xl font-semibold leading-tight tracking-tight text-foreground md:text-4xl">
              {targetCopy.title}
              {targetCopy.targetName ? (
                <>
                  {" "}
                  <span className="font-medium italic text-burgundy">{targetCopy.targetName}</span>
                </>
              ) : null}
            </h2>
            <p className="mt-3 text-sm font-semibold text-muted-foreground">{definition.title}</p>
          </div>

          {hasQuestionnaireDetails ? (
            <div className="mt-4">
              <Button
                type="button"
                variant="outline"
                size="sm"
                aria-haspopup="dialog"
                aria-expanded={detailsOpen}
                aria-controls={questionnaireDetailsId}
                onClick={() => setDetailsOpen(true)}
                className="border-burgundy/30 text-burgundy hover:border-burgundy/60 hover:bg-burgundy/5 hover:text-burgundy"
              >
                Detalii chestionar
              </Button>
            </div>
          ) : null}
        </section>

        {detailsOpen ? (
          <ModalLayer
            labelledBy={`${questionnaireDetailsId}-title`}
            onClose={() => setDetailsOpen(false)}
            panelClassName="max-w-xl"
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-burgundy">Chestionar</p>
                <h3 id={`${questionnaireDetailsId}-title`} className="mt-1 text-xl font-semibold text-foreground">
                  Detalii chestionar
                </h3>
              </div>
              <Button
                type="button"
                onClick={() => setDetailsOpen(false)}
                aria-label="Închide detaliile"
                variant="outline"
                size="sm"
              >
                Închide
              </Button>
            </div>
            {definition.description ? (
              <p className="mt-4 text-sm leading-6 text-muted-foreground">{definition.description}</p>
            ) : null}
            {definition.schema.instructions ? (
              <p className="mt-4 rounded-lg border border-burgundy/18 bg-muted px-4 py-3 text-sm leading-6 text-muted-foreground">
                {definition.schema.instructions}
              </p>
            ) : null}
          </ModalLayer>
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
            <section key={section.id} className="border-b border-border last:border-b-0">
              {!hideIcareMeasurementContext ? (
                <div className="bg-muted px-5 py-3 md:px-6">
                  <h3 className="text-sm font-semibold text-muted-foreground">{section.title}</h3>
                </div>
              ) : null}
              <div className="divide-y divide-border">
                {section.questions.map((question, index) => (
                  <article key={question.id} className="px-5 py-5 md:px-6">
                    <div
                      className={hideIcareMeasurementContext ? "min-w-0" : "grid gap-3 md:grid-cols-[1.5rem_1fr]"}
                    >
                      {!hideIcareMeasurementContext ? (
                        <span className="pt-0.5 text-sm font-bold tabular-nums text-burgundy/72">{index + 1}</span>
                      ) : null}
                      <div className="min-w-0">
                        {!hideIcareMeasurementContext ? (
                          <>
                            <h4 className="text-base font-semibold leading-6 text-foreground">{question.label}</h4>
                            {question.instructions ? (
                              <p className="mt-2 text-sm leading-6 text-muted-foreground">{question.instructions}</p>
                            ) : null}
                          </>
                        ) : null}
                        {question.type === "likert" ? (
                          <LikertQuestion
                            question={question}
                            answers={answers}
                            disabled={responsesLocked}
                            onAnswerChange={handleAnswerChange}
                          />
                        ) : question.type === "single_choice" ? (
                          <SingleChoiceQuestion
                            question={question}
                            answers={answers}
                            disabled={responsesLocked}
                            onAnswerChange={handleAnswerChange}
                          />
                        ) : (
                          <StatementSetQuestion
                            question={question}
                            answers={answers}
                            disabled={responsesLocked}
                            onAnswerChange={handleAnswerChange}
                            hideStatementLabels={hideIcareMeasurementContext}
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

      <aside className="rounded-lg border border-border bg-surface p-4 shadow-[0_1px_0_rgba(24,24,27,0.04)] lg:sticky lg:top-8">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm font-semibold text-foreground">Progres</p>
          <p className="text-sm font-semibold tabular-nums text-muted-foreground">
            {answeredCount}/{requiredAnswerKeys.length}
          </p>
        </div>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-burgundy transition-[width] duration-200" style={{ width: `${progress}%` }} />
        </div>
        <p className="mt-3 text-xs font-semibold text-muted-foreground">{progress}% completat</p>

        <div className="mt-5 grid gap-2">
          <Button
            type="button"
            size="lg"
            disabled={!canSubmit || saveState === "saving" || isComplete || isExiting}
            onClick={submit}
          >
            {saveState === "saving" ? <Loader2Icon data-icon="inline-start" aria-hidden="true" className="animate-spin" /> : null}
            {saveState === "saving" ? (activeOperation === "submit" ? "Trimitem răspunsurile" : "Salvăm draftul") : "Trimite răspunsurile"}
          </Button>
        </div>
        <AutosaveStatus assignmentId={assignmentId} state={saveState} error={saveError} />
      </aside>
      {submitConfirmOpen ? (
        <ModalLayer
          labelledBy="submit-questionnaire-confirm-title"
          onClose={() => setSubmitConfirmOpen(false)}
          panelClassName="max-w-md"
        >
          <div className="flex flex-col gap-4">
            <div>
              <h2 id="submit-questionnaire-confirm-title" className="text-lg font-bold text-foreground">
                Trimiți răspunsurile finale?
              </h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                După trimitere nu le mai poți modifica decât dacă trainerul redeschide sarcina.
              </p>
            </div>
            <div className="flex justify-end gap-2 border-t border-border pt-3">
              <Button
                type="button"
                onClick={() => setSubmitConfirmOpen(false)}
                variant="outline"
              >
                Anulează
              </Button>
              <Button
                type="button"
                onClick={() => void confirmSubmit()}
              >
                Trimite
              </Button>
            </div>
          </div>
        </ModalLayer>
      ) : null}
    </div>
  );
}

function evaluationTargetCopy(
  targetLabel: string | undefined,
  questionnaireKey: string,
): { eyebrow: string; title: string; targetName?: string } {
  if (questionnaireKey === "lencioni" || questionnaireKey === "lencioni_en") {
    return {
      eyebrow: "Feedback pentru echipă",
      title: "Răspunzi despre echipa ta",
    };
  }
  const isReview360 = isReview360Questionnaire(questionnaireKey);
  const cleaned = targetLabel?.trim();
  if (isReview360) {
    const safeTarget = safeReviewTargetLabel(targetLabel);
    return safeTarget
      ? {
          eyebrow: "Feedback iCARE",
          title: "Completezi feedback pentru",
          targetName: safeTarget,
        }
      : {
          eyebrow: "Feedback iCARE",
          title: "Completezi feedback pentru persoana indicată",
        };
  }

  if (!cleaned || cleaned.toLocaleLowerCase("ro-RO") === "autoevaluare") {
    return {
      eyebrow: "Autoevaluare",
      title: "Răspunzi despre propria experiență în proiect",
    };
  }

  return {
    eyebrow: "Evaluezi",
    title: "Răspunzi pentru",
    targetName: cleaned,
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

function AutosaveStatus({
  assignmentId,
  state,
  error,
}: {
  assignmentId?: string;
  state: SaveState;
  error: string | null;
}) {
  if (state !== "error") return null;
  const message = assignmentId
    ? error || "A apărut o eroare la salvare."
    : "Salvarea nu este disponibilă pentru această sarcină.";

  return (
    <InlineFeedback
      tone="danger"
      className="mt-4 px-3 py-3"
      descriptionClassName="text-xs leading-5"
    >
      <span className="flex items-start gap-2">
        <span aria-hidden="true" className="mt-2 size-1.5 shrink-0 rounded-full bg-destructive" />
        <span>{message}</span>
      </span>
    </InlineFeedback>
  );
}

function errorMessage(error: unknown, fallback: string): string {
  if (isQuestionnaireSessionError(error)) {
    return "Sesiunea activă s-a schimbat în altă filă. Reîncarcă pagina sau intră din nou în contul de participant înainte să trimiți chestionarul.";
  }
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
      <div className="status-success-soft mx-auto flex size-14 items-center justify-center rounded-full text-xl font-semibold">
        <CheckIcon />
      </div>
      <h3 className="mt-5 text-2xl font-semibold text-foreground">Răspunsurile au fost trimise</h3>
      <p className="mx-auto mt-3 max-w-lg text-sm leading-6 text-muted-foreground">
        Am înregistrat {answeredCount}/{total} răspunsuri pentru această sarcină. Persoana evaluată nu vede răspunsuri
        individuale; trainerul lucrează cu raportarea configurată pentru proiect.
      </p>
      <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
        <Button asChild size="lg">
          <Link href={returnHref}>{returnLabel}</Link>
        </Button>
      </div>
    </section>
  );
}

type QuestionInputProps = {
  question: QuestionnaireQuestion;
  answers: AnswerState;
  disabled?: boolean;
  hideStatementLabels?: boolean;
  onAnswerChange: (key: string, value: QuestionnaireAnswerValue) => void;
};

function LikertQuestion({ question, answers, disabled, onAnswerChange }: QuestionInputProps) {
  const key = answerKey(question);

  if (isTenPointScale(question.scale)) {
    return (
      <DiscreteScaleSlider
        label={question.label}
        scale={question.scale}
        selectedValue={answers[key]}
        disabled={disabled}
        onChange={(value) => onAnswerChange(key, value)}
      />
    );
  }

  return (
    <div
      data-testid="question-response-group"
      role="radiogroup"
      aria-label={question.label}
      className="mt-4 grid gap-2 sm:grid-cols-3"
    >
      {question.scale.map((option) => {
        const selected = answers[key] === option.value;
        return (
          <Button
            key={option.value}
            type="button"
            variant={selected ? "default" : "outline"}
            size="lg"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => onAnswerChange(key, option.value)}
            className={cn(
              choiceButtonClass(selected),
              "min-h-11 px-3 py-2.5 text-center text-sm font-semibold",
            )}
          >
            {option.label}
          </Button>
        );
      })}
    </div>
  );
}

function choiceButtonClass(selected: boolean): string {
  return cn(
    "h-auto whitespace-normal disabled:opacity-55",
    selected
      ? "border-burgundy bg-burgundy text-white shadow-sm hover:bg-burgundy-700"
      : "border-border bg-surface text-muted-foreground hover:border-burgundy/45 hover:bg-muted/70 hover:text-burgundy",
  );
}

function SingleChoiceQuestion({ question, answers, disabled, onAnswerChange }: QuestionInputProps) {
  const key = answerKey(question);

  return (
    <div
      data-testid="question-response-group"
      role="radiogroup"
      aria-label={question.label}
      className="mt-4 grid gap-2 sm:grid-cols-2"
    >
      {question.scale.map((option) => {
        const selected = answers[key] === option.value;
        return (
          <Button
            key={String(option.value)}
            type="button"
            variant={selected ? "default" : "outline"}
            size="lg"
            role="radio"
            aria-checked={selected}
            disabled={disabled}
            onClick={() => onAnswerChange(key, option.value)}
            className={cn(choiceButtonClass(selected), "justify-start px-3 py-3 text-left text-sm")}
          >
            <span className="block font-bold">{option.label}</span>
            {option.description ? (
              <span className={["mt-1 block text-xs leading-5", selected ? "text-white/72" : "text-muted-foreground"].join(" ")}>
                {option.description}
              </span>
            ) : null}
          </Button>
        );
      })}
    </div>
  );
}

function StatementSetQuestion({
  question,
  answers,
  disabled,
  hideStatementLabels = false,
  onAnswerChange,
}: QuestionInputProps) {
  return (
    <div className="mt-4 overflow-hidden rounded-lg border border-border">
      {(question.statements ?? []).map((statement) => {
        const key = answerKey(question, statement.id);
        const scale = statement.scale?.length ? statement.scale : question.scale;
        const selectedValue = answers[key];
        return (
          <div
            key={statement.id}
            className="border-b border-border bg-surface px-4 py-4 last:border-b-0"
          >
            {!hideStatementLabels ? (
              <p className="text-sm font-medium leading-6 text-foreground/72">{statement.label}</p>
            ) : null}
            {isTenPointScale(scale) ? (
              <DiscreteScaleSlider
                label={statement.label}
                scale={scale}
                selectedValue={selectedValue}
                disabled={disabled}
                onChange={(value) => onAnswerChange(key, value)}
              />
            ) : (
              <div
                data-testid="question-response-group"
                role="radiogroup"
                aria-label={statement.label}
                className="mt-3 grid gap-2"
              >
                {scale.map((option) => {
                  const selected = selectedValue === option.value;
                  return (
                    <Button
                      key={String(option.value)}
                      type="button"
                      variant={selected ? "default" : "outline"}
                      size="sm"
                      role="radio"
                      aria-checked={selected}
                      disabled={disabled}
                      onClick={() => onAnswerChange(key, option.value)}
                      className={cn(choiceButtonClass(selected), "justify-start px-3 py-2.5 text-left text-xs")}
                    >
                      <span className="block text-sm font-bold">{option.label}</span>
                      {option.description ? (
                        <span className={["mt-1 block leading-5", selected ? "text-white/76" : "text-muted-foreground"].join(" ")}>
                          {option.description}
                        </span>
                      ) : null}
                    </Button>
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
