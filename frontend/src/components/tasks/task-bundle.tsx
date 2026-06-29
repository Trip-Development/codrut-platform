import Link from "next/link";

import {
  inviteStatusLabel,
  inviteTaskHref,
  inviteTaskProgress,
  participantTaskTypeLabel,
  type InviteTask,
} from "@/api/invites";

type TaskBundleProps = {
  tasks: InviteTask[];
  projectName: string;
  participantEmail?: string;
  deadlineLabel?: string;
  compact?: boolean;
  returnTo?: string;
};

export function TaskBundle({
  tasks,
  projectName,
  participantEmail,
  compact = false,
  returnTo,
}: TaskBundleProps) {
  const progress = inviteTaskProgress(tasks);
  const nextHref = progress.nextTask ? inviteTaskHref(progress.nextTask, { returnTo }) : returnTo ?? "/participant/questionnaires";

  if (tasks.length === 0) {
    return (
      <section className="rounded-xl border border-[var(--border)] bg-surface px-5 py-7 text-center shadow-sm">
        <p className="text-base font-semibold text-foreground">Nu există sarcini active pentru acest proiect.</p>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-foreground/60">
          Când trainerul trimite invitațiile, sarcinile apar aici grupate după email și proiect.
        </p>
      </section>
    );
  }

  return (
    <section className="surface-panel overflow-hidden">
      <div className="border-b border-[var(--border)] bg-surface px-5 py-5 md:px-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-burgundy/75">
              {projectName}
            </p>
            <h2 className="mt-1.5 text-2xl font-semibold text-foreground">Sarcinile tale</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/62">
              {participantEmail ? `${participantEmail} · ` : null}
              Link activ. Răspunsurile sunt salvate securizat pentru acest proiect.
            </p>
          </div>
          <Link
            href={nextHref}
            className="tap-soft inline-flex justify-center rounded-full bg-burgundy px-5 py-3 text-sm font-bold text-white shadow-sm hover:bg-burgundy-700"
          >
            {progress.nextTask ? "Continuă următoarea sarcină" : "Vezi chestionarele"}
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
          <TaskRow key={task.id} task={task} returnTo={returnTo} />
        ))}
      </div>
    </section>
  );
}

function TaskRow({ task, returnTo }: { task: InviteTask; returnTo?: string }) {
  const isDone = task.status === "completed";

  return (
    <article className="group grid gap-3 px-5 py-4 transition-colors hover:bg-surface-muted md:grid-cols-[1fr_auto] md:items-center md:px-6">
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-base font-semibold text-foreground">{task.title}</h3>
          <span
            className={[
              "rounded-full px-2.5 py-1 text-xs font-bold",
              isDone ? "bg-success/35 text-success-ink" : "bg-burgundy-50 dark:bg-burgundy/10 text-burgundy",
            ].join(" ")}
          >
            {inviteStatusLabel(task.status)}
          </span>
        </div>
        <p className="mt-1 text-sm leading-6 text-foreground/62">{task.detail}</p>
        <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs font-semibold text-foreground/48">
          <span>{task.targetLabel}</span>
          <span>{task.estimatedMinutes} min</span>
          <span>{participantTaskTypeLabel(task.questionnaireKey)}</span>
        </div>
      </div>
      {isDone ? (
        <span className="inline-flex justify-center rounded-full border border-success/25 bg-success/12 px-4 py-2.5 text-sm font-bold text-success-ink">
          Finalizat
        </span>
      ) : (
        <Link
          href={inviteTaskHref(task, { returnTo })}
          className="tap-soft inline-flex justify-center rounded-full bg-foreground px-4 py-2.5 text-sm font-bold text-background group-hover:bg-burgundy group-hover:text-white"
        >
          Deschide
        </Link>
      )}
    </article>
  );
}
