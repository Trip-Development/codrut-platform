import Link from "next/link";
import { ArrowRightIcon, CheckIcon } from "lucide-react";

import { serverLinkButtonClassName } from "@/components/ui/server-link-button";

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
      <div className="border-y border-border py-8">
        <h3 className="text-base font-semibold text-foreground">{emptyTitle}</h3>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">{emptyDescription}</p>
      </div>
    );
  }

  return (
    <div className="grid gap-8">
      {pendingGroups.length > 0 ? (
        <TaskGroupSection title="Active" groups={pendingGroups} returnTo={returnTo} />
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
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
        <span className="font-mono text-xs tabular-nums text-muted-foreground">
          {groups.length}
        </span>
      </div>
      <div className="overflow-hidden rounded-lg border border-border bg-surface divide-y divide-border">
        {groups.map((group) => (
          <ParticipantTaskCard key={group.id} group={group} returnTo={returnTo} />
        ))}
      </div>
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
    <article className="group/task grid gap-4 px-4 py-4 transition-colors hover:bg-muted/50 md:grid-cols-[minmax(0,1fr)_auto] md:items-center md:px-5">
      <div className="flex min-w-0 items-start gap-3">
        <span
          aria-hidden="true"
          className={[
            "mt-1.5 size-2.5 shrink-0 rounded-full",
            isComplete ? "bg-success" : group.status === "in_progress" ? "bg-burgundy" : "bg-muted-foreground/50",
          ].join(" ")}
        />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <h3 className="text-base font-semibold tracking-tight text-foreground">{group.title}</h3>
            <span className={isComplete ? "text-xs font-semibold text-success" : "text-xs font-semibold text-burgundy"}>
              {copy.label}
            </span>
          </div>
          <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-sm text-muted-foreground">
            {group.projectName ? (
              <span className="font-semibold text-foreground/80">{group.projectName}</span>
            ) : null}
            <span>{group.targetSummary}</span>
            <span>{group.estimatedMinutes} min</span>
            {group.totalCount > 1 ? (
              <span>{group.completedCount}/{group.totalCount} finalizate</span>
            ) : null}
          </div>
        </div>
      </div>
      <div className="pl-5 md:pl-0">
        {href ? (
          <Link
            href={href}
            className={serverLinkButtonClassName({ variant: "outline", className: "w-fit" })}
          >
            {group.kind === "review360" ? "Continuă review-ul" : "Continuă"}
            <ArrowRightIcon data-icon="inline-end" aria-hidden="true" strokeWidth={2.3} />
          </Link>
        ) : (
          <span className="inline-flex items-center gap-2 text-sm font-semibold text-success">
            <CheckIcon aria-hidden="true" className="size-4" strokeWidth={2.2} />
            Finalizat
          </span>
        )}
      </div>
    </article>
  );
}
