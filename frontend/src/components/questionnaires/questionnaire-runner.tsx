"use client";

import type { Dispatch, SetStateAction } from "react";
import { useMemo, useState } from "react";

import type { QuestionnaireDefinition, QuestionnaireQuestion } from "@/api/questionnaires";

type AnswerState = Record<string, number>;

type QuestionnaireRunnerProps = {
  definition: QuestionnaireDefinition;
};

function answerKey(question: QuestionnaireQuestion, statementId?: string): string {
  return statementId ? `${question.id}:${statementId}` : question.id;
}

export function QuestionnaireRunner({ definition }: QuestionnaireRunnerProps) {
  const [answers, setAnswers] = useState<AnswerState>({});
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

  return (
    <div className="space-y-4">
      <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-burgundy/80">
              v{definition.version} · {definition.key}
            </p>
            <h2 className="mt-2 text-xl font-bold text-foreground">{definition.title}</h2>
          </div>
          <div className="rounded-full border border-[var(--border)] bg-surface-muted px-3 py-1 text-sm font-bold text-foreground/70">
            {answeredCount}/{requiredAnswerKeys.length}
          </div>
        </div>
        <p className="mt-3 text-sm leading-6 text-foreground/65">{definition.description}</p>
        {definition.schema.instructions ? (
          <p className="mt-4 rounded-xl border border-[var(--border)] bg-surface-muted px-3 py-2 text-sm leading-6 text-foreground/70">
            {definition.schema.instructions}
          </p>
        ) : null}
        <div className="mt-4 h-2 overflow-hidden rounded-full bg-surface-muted">
          <div className="h-full rounded-full bg-burgundy" style={{ width: `${progress}%` }} />
        </div>
      </section>

      {definition.schema.sections.map((section) => (
        <section key={section.id} className="space-y-3">
          <h3 className="text-sm font-bold uppercase tracking-[0.14em] text-foreground/55">
            {section.title}
          </h3>
          {section.questions.map((question, index) => (
            <article key={question.id} className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
              <div className="flex items-start gap-3">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface-muted text-sm font-bold text-burgundy">
                  {index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <h4 className="text-base font-bold text-foreground">{question.label}</h4>
                  {question.instructions ? (
                    <p className="mt-2 text-sm leading-6 text-foreground/60">{question.instructions}</p>
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
        </section>
      ))}

      <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
        <button
          type="button"
          className="tap-soft w-full rounded-xl bg-burgundy px-4 py-3 text-sm font-bold text-white disabled:cursor-not-allowed disabled:opacity-45"
          disabled={answeredCount < requiredAnswerKeys.length}
        >
          Submit va fi conectat in task-ul de raspunsuri
        </button>
      </section>
    </div>
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
              "tap-soft rounded-xl border px-3 py-3 text-sm font-semibold",
              selected
                ? "border-burgundy bg-burgundy text-white"
                : "border-[var(--border)] bg-surface-muted text-foreground/75 hover:border-burgundy/50",
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
    <div className="mt-4 space-y-3">
      {(question.statements ?? []).map((statement) => {
        const key = answerKey(question, statement.id);
        return (
          <div key={statement.id} className="rounded-xl border border-[var(--border)] bg-surface-muted p-3">
            <div className="flex flex-col gap-3 md:flex-row md:items-center">
              <p className="flex-1 text-sm font-semibold leading-6 text-foreground/75">
                <span className="mr-2 font-bold text-burgundy">{statement.code}.</span>
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
                className="rounded-xl border border-[var(--border)] bg-surface px-3 py-2 text-sm font-bold text-foreground"
              >
                <option value="" disabled>
                  Scor
                </option>
                {question.scale.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
        );
      })}
    </div>
  );
}
