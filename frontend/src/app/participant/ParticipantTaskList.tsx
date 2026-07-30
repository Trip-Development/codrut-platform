"use client";

import Link from "next/link";
import {
  ArrowRightIcon,
  CheckIcon,
  ChevronDownIcon,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { serverLinkButtonClassName } from "@/components/ui/server-link-button";
import { cn } from "@/utils/cn";

import {
  participantTaskGroupHref,
  participantTaskStatusCopy,
  type ParticipantTaskGroup,
  type ParticipantTaskProject,
} from "./task-display";

type ParticipantTaskListProps = {
  projects: ParticipantTaskProject[];
  persistenceIdentityKey: string;
  returnTo: string;
  emptyTitle: string;
  emptyDescription: string;
  inviteToken?: string;
};

type ProjectAccent = {
  borderClassName: string;
  markerClassName: string;
  label: string;
};

const projectAccents: ProjectAccent[] = [
  {
    borderClassName: "border-l-chart-1",
    markerClassName: "bg-chart-1",
    label: "vișiniu",
  },
  {
    borderClassName: "border-l-chart-2",
    markerClassName: "bg-chart-2",
    label: "ocru",
  },
  {
    borderClassName: "border-l-chart-3",
    markerClassName: "bg-chart-3",
    label: "verde",
  },
  {
    borderClassName: "border-l-info",
    markerClassName: "bg-info",
    label: "albastru",
  },
  {
    borderClassName: "border-l-chart-4",
    markerClassName: "bg-chart-4",
    label: "gri",
  },
];

export function projectAccentIndex(projectId: string): number {
  let hash = 2166136261;
  for (const character of projectId) {
    hash ^= character.codePointAt(0) ?? 0;
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0) % projectAccents.length;
}

function defaultExpandedState(
  projects: ParticipantTaskProject[],
): Record<string, boolean> {
  return Object.fromEntries(
    projects.map((project) => [
      project.id,
      project.historyBucket === "current"
        && project.status === "active"
        && project.totalCount > 0
        && project.completedCount < project.totalCount,
    ]),
  );
}

function storageKey(identityKey: string): string {
  return `codrut:participant-questionnaire-tree:${identityKey}`;
}

export function ParticipantTaskList({
  projects,
  persistenceIdentityKey,
  returnTo,
  emptyTitle,
  emptyDescription,
  inviteToken,
}: ParticipantTaskListProps) {
  const defaults = useMemo(() => defaultExpandedState(projects), [projects]);
  const [expandedProjects, setExpandedProjects] =
    useState<Record<string, boolean>>(defaults);

  useEffect(() => {
    setExpandedProjects(() => {
      try {
        const stored = window.localStorage.getItem(
          storageKey(persistenceIdentityKey),
        );
        if (!stored) return defaults;
        const parsed = JSON.parse(stored) as Record<string, unknown>;
        const remembered = Object.fromEntries(
          Object.entries(parsed).filter(
            ([projectId, expanded]) =>
              projectId in defaults && typeof expanded === "boolean",
          ),
        ) as Record<string, boolean>;
        return { ...defaults, ...remembered };
      } catch {
        return defaults;
      }
    });
  }, [defaults, persistenceIdentityKey]);

  if (projects.length === 0) {
    return (
      <div className="border-y border-border py-8">
        <h3 className="text-base font-semibold text-foreground">{emptyTitle}</h3>
        <p className="mt-1 text-sm leading-6 text-muted-foreground">
          {emptyDescription}
        </p>
      </div>
    );
  }

  function toggleProject(projectId: string) {
    setExpandedProjects((current) => {
      const next = {
        ...current,
        [projectId]: !current[projectId],
      };
      try {
        window.localStorage.setItem(
          storageKey(persistenceIdentityKey),
          JSON.stringify(next),
        );
      } catch {
        // Browser privacy settings can disable storage. The tree still works.
      }
      return next;
    });
  }

  return (
    <section aria-label="Chestionare pe proiecte">
      <div className="grid gap-3">
        {projects.map((project) => {
          const accent = projectAccents[projectAccentIndex(project.id)];
          const expanded = expandedProjects[project.id] ?? false;
          const contentId = `participant-project-${project.id.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
          const pendingCount = project.totalCount - project.completedCount;
          const complete = project.totalCount > 0 && pendingCount === 0;
          const readOnly =
            project.historyBucket === "history" || project.status !== "active";

          return (
            <article
              key={project.id}
              className={cn(
                "overflow-hidden rounded-lg border border-border border-l-4 bg-surface",
                accent.borderClassName,
              )}
            >
              <button
                type="button"
                aria-controls={contentId}
                aria-expanded={expanded}
                onClick={() => toggleProject(project.id)}
                className={cn(
                  "grid w-full grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 px-4 py-4 text-left",
                  "transition-colors hover:bg-muted/55 active:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring/45",
                  "sm:px-5",
                )}
              >
                <ChevronDownIcon
                  aria-hidden="true"
                  className={cn(
                    "size-4 text-muted-foreground transition-transform duration-150",
                    !expanded && "-rotate-90",
                  )}
                  strokeWidth={2.2}
                />
                <span className="min-w-0">
                  <span className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                    <span className="text-base font-semibold text-foreground">
                      {project.name}
                    </span>
                    <span className="sr-only">, marcaj {accent.label}</span>
                    {project.companyName ? (
                      <span className="text-xs text-muted-foreground">
                        {project.companyName}
                      </span>
                    ) : null}
                  </span>
                  <span className="mt-1 block text-xs text-muted-foreground">
                    {project.historyBucket === "history"
                      ? "Istoric"
                      : "În desfășurare"}
                    {" | "}
                    {project.deadlineLabel || "Fără termen"}
                  </span>
                </span>
                <span
                  className={cn(
                    "text-right text-xs font-semibold",
                    complete
                      ? "text-success-ink"
                      : readOnly
                        ? "text-muted-foreground"
                        : "text-burgundy",
                  )}
                >
                  {readOnly
                    ? "Istoric"
                    : complete
                    ? "Finalizat"
                    : `${pendingCount} de făcut`}
                  <span className="mt-1 block font-mono font-medium tabular-nums text-muted-foreground">
                    {project.completedCount}/{project.totalCount}
                  </span>
                </span>
              </button>

              {expanded ? (
                <div id={contentId} className="border-t border-border">
                  {project.groups.map((group) => (
                    <ParticipantTaskRow
                      key={group.id}
                      group={group}
                      returnTo={returnTo}
                      inviteToken={inviteToken}
                      readOnly={readOnly}
                    />
                  ))}
                </div>
              ) : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}

function ParticipantTaskRow({
  group,
  returnTo,
  inviteToken,
  readOnly,
}: {
  group: ParticipantTaskGroup;
  returnTo: string;
  inviteToken?: string;
  readOnly: boolean;
}) {
  const copy = participantTaskStatusCopy[group.status];
  const href = readOnly
    ? null
    : participantTaskGroupHref(group, { returnTo, inviteToken });
  const isComplete = group.status === "completed";
  const firstTask = group.tasks[0];
  const cycleLabel = firstTask?.cycleSequence
    ? `Ciclul ${firstTask.cycleSequence}${firstTask.cycleName ? `, ${firstTask.cycleName}` : ""}`
    : firstTask?.cycleName ||
      (firstTask?.assessmentCycleId ? "Ciclul invitației" : "Fără ciclu");
  const deadlineLabel =
    firstTask?.deadlineLabel &&
    firstTask.deadlineLabel !== "Fără termen"
      ? firstTask.deadlineLabel
      : null;
  const targetSummary =
    group.kind === "single" &&
    (firstTask?.questionnaireKey === "lencioni" ||
      firstTask?.questionnaireKey === "lencioni_en")
      ? "Echipa ta"
      : group.targetSummary;

  return (
    <div className="grid gap-4 border-b border-border px-4 py-4 last:border-b-0 sm:px-5 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
      <div className="min-w-0 pl-7">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <h3 className="text-sm font-semibold text-foreground">{group.title}</h3>
          <span
            className={cn(
              "text-xs font-semibold",
              isComplete
                ? "text-success-ink"
                : readOnly
                  ? "text-muted-foreground"
                  : "text-burgundy",
            )}
          >
            {readOnly && !isComplete ? "Închis" : copy.label}
          </span>
        </div>
        <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span>{cycleLabel}</span>
          <span>{targetSummary}</span>
          {deadlineLabel ? <span>{deadlineLabel}</span> : null}
          {group.totalCount > 1 ? (
            <span>
              {group.completedCount}/{group.totalCount} finalizate
            </span>
          ) : null}
        </div>
      </div>
      <div className="pl-7 md:pl-0">
        {href ? (
          <Link
            href={href}
            className={serverLinkButtonClassName({
              variant: "outline",
              className: "w-fit",
            })}
          >
            {group.kind === "review360"
              ? group.completedCount > 0
                ? "Continuă review-ul"
                : "Începe review-ul"
              : group.status === "in_progress"
                ? "Continuă"
                : "Deschide"}
            <ArrowRightIcon
              data-icon="inline-end"
              aria-hidden="true"
              strokeWidth={2.3}
            />
          </Link>
        ) : isComplete ? (
          <span className="inline-flex items-center gap-2 text-sm font-semibold text-success-ink">
            <CheckIcon
              aria-hidden="true"
              className="size-4"
              strokeWidth={2.2}
            />
            Finalizat
          </span>
        ) : (
          <span className="text-sm font-semibold text-muted-foreground">
            Proiect încheiat
          </span>
        )}
      </div>
    </div>
  );
}
