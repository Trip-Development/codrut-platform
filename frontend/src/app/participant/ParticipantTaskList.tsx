import Link from "next/link";

import {
  participantTaskGroupHref,
  participantTaskStatusCopy,
  type ParticipantTaskGroup,
} from "./task-display";

type ParticipantTaskListProps = {
  groups: ParticipantTaskGroup[];
  returnTo: string;
  emptyTitle: string;
  emptyDescription: string;
};

export function ParticipantTaskList({
  groups,
  returnTo,
  emptyTitle,
  emptyDescription,
}: ParticipantTaskListProps) {
  const pendingGroups = groups.filter((group) => group.status !== "completed");
  const completedGroups = groups.filter((group) => group.status === "completed");

  if (groups.length === 0) {
    return (
      <div className="rounded-xl border border-[var(--border)] bg-surface-muted p-5">
        <h3 className="text-base font-semibold text-foreground">{emptyTitle}</h3>
        <p className="mt-1 text-sm leading-6 text-foreground/62">{emptyDescription}</p>
      </div>
    );
  }

  return (
    <div className="grid gap-5">
      {pendingGroups.length > 0 ? (
        <TaskGroupSection title="De completat" groups={pendingGroups} returnTo={returnTo} />
      ) : null}
      {completedGroups.length > 0 ? (
        <TaskGroupSection title="Finalizate" groups={completedGroups} returnTo={returnTo} />
      ) : null}
    </div>
  );
}

function TaskGroupSection({
  title,
  groups,
  returnTo,
}: {
  title: string;
  groups: ParticipantTaskGroup[];
  returnTo: string;
}) {
  return (
    <section aria-label={title} className="grid gap-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-bold uppercase tracking-[0.14em] text-foreground/48">{title}</h3>
        <span className="text-xs font-semibold text-foreground/45">
          {groups.length} {groups.length === 1 ? "intrare" : "intrări"}
        </span>
      </div>
      {groups.map((group) => (
        <ParticipantTaskCard key={group.id} group={group} returnTo={returnTo} />
      ))}
    </section>
  );
}

function ParticipantTaskCard({
  group,
  returnTo,
}: {
  group: ParticipantTaskGroup;
  returnTo: string;
}) {
  const copy = participantTaskStatusCopy[group.status];
  const href = participantTaskGroupHref(group, { returnTo });
  const isComplete = group.status === "completed";

  return (
    <article className="group/task rounded-xl border border-[var(--border)] bg-surface p-4 shadow-sm transition hover:border-burgundy/24">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={[
                "rounded-full px-2.5 py-1 text-[11px] font-bold uppercase tracking-[0.12em]",
                isComplete
                  ? "bg-success/12 text-success-ink"
                  : "bg-burgundy/10 text-burgundy",
              ].join(" ")}
            >
              {copy.label}
            </span>
            <span className="text-xs font-semibold text-foreground/45">
              {group.estimatedMinutes} min
            </span>
          </div>
          <h3 className="mt-3 text-lg font-semibold tracking-tight text-foreground">{group.title}</h3>
          <p className="mt-1.5 max-w-2xl text-sm leading-6 text-foreground/62">{group.detail}</p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-foreground/48">
            <span>{group.targetSummary}</span>
            <span aria-hidden="true">·</span>
            <span>
              {group.completedCount}/{group.totalCount} finalizate
            </span>
            <span aria-hidden="true">·</span>
            <span>{copy.helper}</span>
          </div>
        </div>
        {href ? (
          <Link
            href={href}
            className="tap-soft inline-flex items-center justify-center gap-2 rounded-full bg-burgundy px-5 py-3 text-sm font-bold text-white shadow-sm hover:bg-burgundy-dark"
          >
            {group.kind === "review360" ? "Continuă review-ul" : "Continuă"}
            <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.4" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14m-6-6 6 6-6 6" />
            </svg>
          </Link>
        ) : (
          <span className="status-pill border-success/25 bg-surface-muted px-5 py-3 text-sm text-success-ink">
            Finalizat
          </span>
        )}
      </div>
    </article>
  );
}
