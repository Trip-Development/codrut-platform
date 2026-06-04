"use client";

import Link from "next/link";
import type { Dispatch, SetStateAction } from "react";
import { useMemo, useState } from "react";

import {
  saveQuestionnaireResponse,
  submitQuestionnaireResponse,
  type QuestionnaireDefinition,
  type QuestionnaireQuestion,
} from "@/api/questionnaires";

type AnswerState = Record<string, number>;

type QuestionnaireRunnerProps = {
  definition: QuestionnaireDefinition;
  assignmentId?: string;
};

function answerKey(question: QuestionnaireQuestion, statementId?: string): string {
  return statementId ? `${question.id}:${statementId}` : question.id;
}

export function QuestionnaireRunner({ definition, assignmentId }: QuestionnaireRunnerProps) {
  const [answers, setAnswers] = useState<AnswerState>({});
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "submitted" | "error">("idle");
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

  async function saveDraft() {
    if (!assignmentId) return;
    setSaveState("saving");
    try {
      await saveQuestionnaireResponse(assignmentId, answers);
      setSaveState("saved");
    } catch {
      setSaveState("error");
    }
  }

  async function submit() {
    if (!canSubmit || !assignmentId) return;
    setSaveState("saving");
    try {
      await submitQuestionnaireResponse(assignmentId, answers);
      setSaveState("submitted");
    } catch {
      setSaveState("error");
    }
  }

  return (
    <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-start">
      <div className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
        <section className="border-b border-[var(--border)] px-5 py-5 md:px-6">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">
            v{definition.version} · {definition.key}
          </p>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/68">{definition.description}</p>
          {definition.schema.instructions ? (
            <p className="mt-4 max-w-3xl border-l-2 border-burgundy/45 pl-3 text-sm leading-6 text-foreground/62">
              {definition.schema.instructions}
            </p>
          ) : null}
        </section>

        {isComplete ? (
          <CompletionPanel answeredCount={answeredCount} total={requiredAnswerKeys.length} />
        ) : (
          definition.schema.sections.map((section) => (
            <section key={section.id} className="border-b border-[var(--border)] last:border-b-0">
              <div className="bg-surface-muted/50 px-5 py-3 md:px-6">
                <h3 className="text-sm font-semibold text-foreground/70">{section.title}</h3>
              </div>
              <div className="divide-y divide-[var(--border)]">
                {section.questions.map((question, index) => (
                  <article key={question.id} className="px-5 py-5 md:px-6">
                    <div className="grid gap-4 md:grid-cols-[2.5rem_1fr]">
                      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-surface-muted text-sm font-semibold text-burgundy">
                        {index + 1}
                      </span>
                      <div className="min-w-0">
                        <h4 className="text-base font-semibold leading-6 text-foreground">{question.label}</h4>
                        {question.instructions ? (
                          <p className="mt-2 text-sm leading-6 text-foreground/58">{question.instructions}</p>
                        ) : null}
                        {question.type === "likert" ? (
                          <LikertQuestion question={question} answers={answers} setAnswers={setAnswers} />
                        ) : (
                          <StatementSetQuestion question={question} answers={answers} setAnswers={setAnswers} />
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

      <aside className="sticky top-32 rounded-2xl border border-[var(--border)] bg-surface p-4 shadow-sm">
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
            className="tap-soft rounded-xl border border-burgundy bg-surface px-4 py-3 text-sm font-semibold text-burgundy disabled:cursor-not-allowed disabled:opacity-45"
            disabled={!assignmentId || saveState === "saving" || isComplete}
            onClick={saveDraft}
          >
            Salveaza draft
          </button>
          <button
            type="button"
            className="tap-soft rounded-xl bg-burgundy px-4 py-3 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-45"
            disabled={!canSubmit || saveState === "saving" || isComplete}
            onClick={submit}
          >
            Trimite raspunsurile
          </button>
        </div>
        <p className="mt-3 text-xs leading-5 text-foreground/55">
          {assignmentId
            ? statusMessage(saveState)
            : "Linkul demo nu are inca un assignment real pentru salvare."}
        </p>
      </aside>
    </div>
  );
}

function statusMessage(status: "idle" | "saving" | "saved" | "submitted" | "error"): string {
  if (status === "saving") return "Se salveaza...";
  if (status === "saved") return "Draft salvat.";
  if (status === "submitted") return "Raspunsuri trimise. Poti reveni la lista de sarcini.";
  if (status === "error") return "A aparut o eroare la salvare.";
  return "Poti salva un draft oricand si poti trimite dupa ce ai completat toate campurile.";
}

function CompletionPanel({ answeredCount, total }: { answeredCount: number; total: number }) {
  return (
    <section className="px-5 py-10 text-center md:px-6">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-success/35 text-xl font-semibold text-success-ink">
        OK
      </div>
      <h3 className="mt-5 text-2xl font-semibold text-foreground">Raspunsurile au fost trimise</h3>
      <p className="mx-auto mt-3 max-w-lg text-sm leading-6 text-foreground/62">
        Am inregistrat {answeredCount}/{total} raspunsuri pentru acest task. Persoana evaluata nu vede raspunsuri
        individuale; trainerul lucreaza cu raportarea configurata pentru proiect.
      </p>
      <div className="mt-6 flex flex-col justify-center gap-3 sm:flex-row">
        <Link
          href="/participant"
          className="tap-soft rounded-xl bg-burgundy px-4 py-3 text-sm font-semibold text-white"
        >
          Inapoi la sarcinile mele
        </Link>
        <Link
          href="/participant/questionnaires"
          className="tap-soft rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-semibold text-foreground/72"
        >
          Vezi chestionarele
        </Link>
      </div>
    </section>
  );
}

type QuestionInputProps = {
  question: QuestionnaireQuestion;
  answers: AnswerState;
  setAnswers: Dispatch<SetStateAction<AnswerState>>;
};

function LikertQuestion({ question, answers, setAnswers }: QuestionInputProps) {
  return (
    <div className="mt-4 grid gap-2 sm:grid-cols-3">
      {question.scale.map((option) => {
        const key = answerKey(question);
        const selected = answers[key] === option.value;
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => setAnswers((current) => ({ ...current, [key]: option.value }))}
            className={[
              "tap-soft rounded-lg border px-3 py-2.5 text-sm font-semibold",
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

function StatementSetQuestion({ question, answers, setAnswers }: QuestionInputProps) {
  return (
    <div className="mt-4 overflow-hidden rounded-xl border border-[var(--border)]">
      {(question.statements ?? []).map((statement) => {
        const key = answerKey(question, statement.id);
        return (
          <div
            key={statement.id}
            className="grid gap-3 border-b border-[var(--border)] bg-background px-3 py-3 last:border-b-0 md:grid-cols-[1fr_11rem] md:items-center"
          >
            <p className="text-sm font-medium leading-6 text-foreground/72">
              <span className="mr-2 font-semibold text-burgundy">{statement.code}.</span>
              {statement.label}
            </p>
            <select
              value={answers[key] ?? ""}
              onChange={(event) =>
                setAnswers((current) => ({
                  ...current,
                  [key]: Number(event.target.value),
                }))
              }
              className="rounded-lg border border-[var(--border)] bg-surface px-3 py-2 text-sm font-semibold text-foreground"
            >
              <option value="" disabled>
                Alege scorul
              </option>
              {question.scale.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        );
      })}
    </div>
  );
}
