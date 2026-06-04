import Link from "next/link";

import { inviteStatusLabel, inviteTaskProgress, type InviteTask } from "@/api/invites";

type TaskBundleProps = {
  tasks: InviteTask[];
  projectName: string;
  participantEmail?: string;
  deadlineLabel: string;
  compact?: boolean;
};

export function TaskBundle({
  tasks,
  projectName,
  participantEmail,
  deadlineLabel,
  compact = false,
}: TaskBundleProps) {
  const progress = inviteTaskProgress(tasks);
  const nextHref = progress.nextTask?.href ?? "/participant/questionnaires";

  if (tasks.length === 0) {
    return (
      <section className="rounded-xl border border-[var(--border)] bg-surface px-5 py-6 text-center shadow-sm">
        <p className="text-base font-semibold text-foreground">Nu exista sarcini active pentru acest proiect.</p>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-foreground/60">
          Cand trainerul trimite invitatiile, task-urile apar aici grupate dupa email si proiect.
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
      <div className="border-b border-[var(--border)] px-5 py-4">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">
              {projectName}
            </p>
            <h2 className="mt-1 text-xl font-semibold text-foreground">Sarcinile tale</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/62">
              {participantEmail ? `${participantEmail} · ` : null}
              Link valid pana la {deadlineLabel}. Raspunsurile sunt asociate emailului, fara cont.
            </p>
          </div>
          <Link
            href={nextHref}
            className="tap-soft inline-flex justify-center rounded-xl bg-burgundy px-4 py-3 text-sm font-semibold text-white shadow-sm"
          >
            {progress.nextTask ? "Continua urmatorul task" : "Vezi chestionarele"}
          </Link>
        </div>
        <div className="mt-4 flex items-center gap-3">
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-muted">
            <div className="h-full rounded-full bg-burgundy" style={{ width: `${progress.percent}%` }} />
          </div>
          <span className="text-sm font-semibold tabular-nums text-foreground/65">
            {progress.completed}/{progress.total}
          </span>
        </div>
      </div>

      <div className={compact ? "divide-y divide-[var(--border)]" : "grid gap-0 divide-y divide-[var(--border)]"}>
        {tasks.map((task) => (
          <TaskRow key={task.id} task={task} />
        ))}
      </div>
    </section>
  );
}

function TaskRow({ task }: { task: InviteTask }) {
  const isDone = task.status === "completed";

  return (
    <article className="group grid gap-3 px-5 py-4 transition-colors hover:bg-surface-muted/55 md:grid-cols-[1fr_auto] md:items-center">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-base font-semibold text-foreground">{task.title}</h3>
          <span
            className={[
              "rounded-full px-2.5 py-1 text-xs font-semibold",
              isDone ? "bg-success/35 text-success-ink" : "bg-burgundy-50 text-burgundy",
            ].join(" ")}
          >
            {inviteStatusLabel(task.status)}
          </span>
        </div>
        <p className="mt-1 text-sm leading-6 text-foreground/62">{task.detail}</p>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs font-semibold text-foreground/48">
          <span>{task.targetLabel}</span>
          <span>{task.estimatedMinutes} min</span>
          <span>{task.questionnaireKey}</span>
        </div>
      </div>
      <Link
        href={task.href}
        aria-disabled={isDone}
        className={[
          "tap-soft inline-flex justify-center rounded-xl px-4 py-2.5 text-sm font-semibold",
          isDone
            ? "border border-[var(--border)] bg-surface text-foreground/52"
            : "bg-foreground text-background group-hover:bg-burgundy group-hover:text-white",
        ].join(" ")}
      >
        {isDone ? "Revizuieste" : "Deschide"}
      </Link>
    </article>
  );
}
