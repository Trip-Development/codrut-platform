import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";

import type { CompanyProject, CompanyProjectStatus } from "@/api/companies";

const statusTone: Record<CompanyProjectStatus, string> = {
  draft: "border-zinc-300 bg-zinc-100 text-zinc-700 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-200",
  active: "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/35 dark:text-emerald-200",
  completed: "border-burgundy/25 bg-burgundy/10 text-burgundy",
  archived: "border-zinc-300 bg-zinc-50 text-zinc-500 dark:border-zinc-800 dark:bg-zinc-950 dark:text-zinc-400",
};

const statusPalette: Record<CompanyProjectStatus, Array<[string, string]>> = {
  draft: [
    ["#71717a", "#a1a1aa"],
    ["#52525b", "#d4d4d8"],
    ["#78716c", "#a8a29e"],
  ],
  active: [
    ["#15803d", "#b8860b"],
    ["#047857", "#ca8a04"],
    ["#166534", "#a16207"],
    ["#0f766e", "#b8860b"],
  ],
  completed: [
    ["#890505", "#b8860b"],
    ["#7f1d1d", "#ca8a04"],
    ["#991b1b", "#a16207"],
  ],
  archived: [
    ["#52525b", "#71717a"],
    ["#3f3f46", "#78716c"],
    ["#57534e", "#71717a"],
  ],
};

const projectTypeLabels: Record<string, string> = {
  team_coaching: "Team coaching",
  individual_coaching: "Individual coaching",
  leadership_program: "Leadership program",
  custom: "Personalizat",
};

type ProjectCardContentProps = {
  project: CompanyProject;
};

type ProjectCardFrameProps = ProjectCardContentProps & {
  children?: ReactNode;
};

export function ProjectCardLink({ project }: ProjectCardContentProps) {
  return (
    <Link
      href={`/trainer/projects/${project.id}`}
      className="project-status-card group flex flex-col overflow-hidden rounded-xl border bg-surface shadow-sm transition-colors hover:border-burgundy/35"
      style={projectVisualStyle(project)}
    >
      <ProjectCardContent project={project} />
    </Link>
  );
}

export function ProjectCardFrame({ project, children }: ProjectCardFrameProps) {
  return (
    <article
      className="project-status-card group flex flex-col overflow-hidden rounded-xl border bg-surface shadow-sm transition-colors hover:border-burgundy/35"
      style={projectVisualStyle(project)}
    >
      <ProjectCardContent project={project} />
      {children}
    </article>
  );
}

function ProjectCardContent({ project }: ProjectCardContentProps) {
  return (
    <>
      <div className="visual-band h-28 border-b border-[var(--border)] p-5">
        <div className="flex items-start justify-between gap-3">
          <span className="max-w-[58%] truncate rounded-full border border-[var(--border)] bg-surface px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-foreground/55">
            {project.company_name ?? "Companie"}
          </span>
          <span className={`flex shrink-0 items-center gap-1.5 rounded-full px-2.5 py-1 text-[9px] font-bold uppercase tracking-wider ${statusTone[project.status]}`}>
            {project.status === "active" ? <span className="h-1.5 w-1.5 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]" /> : null}
            {statusLabel(project.status)}
          </span>
        </div>
        <h2 className="mt-4 line-clamp-2 font-display text-xl font-bold leading-tight text-foreground" title={project.name}>
          {project.name}
        </h2>
      </div>

      <div className="flex min-w-0 flex-1 flex-col gap-4 p-5">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[11px] font-semibold text-foreground/62">
          <span className="inline-flex min-w-0 items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--band-a)]" />
            <span className="truncate">{formatCompactRange(project.starts_at, project.due_at)}</span>
          </span>
          <span className="inline-flex min-w-0 items-center gap-2">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--band-b)]" />
            <span className="truncate">{projectTypeLabel(project.project_type)}</span>
          </span>
        </div>
        <ProjectTimelineBar startsAt={project.starts_at} dueAt={project.due_at} />
      </div>
    </>
  );
}

export function ProjectMeta({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-surface-muted px-3 py-2.5 text-center">
      <p className="text-[9px] font-bold uppercase tracking-wider text-foreground/40">{label}</p>
      <p className="mt-1 truncate text-[11px] font-semibold text-foreground/80">{value}</p>
    </div>
  );
}

function ProjectTimelineBar({ startsAt, dueAt }: { startsAt: string | null; dueAt: string | null }) {
  const progress = timelineProgress(startsAt, dueAt);
  return (
    <div>
      <div className="flex items-center justify-between text-[10px] font-bold uppercase tracking-wider text-foreground/42">
        <span>Calendar</span>
        <span>{progress}%</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-muted">
        <div className="project-timeline-fill h-full rounded-full" style={{ width: `${progress}%` }} />
      </div>
    </div>
  );
}

function projectVisualStyle(project: CompanyProject): CSSProperties {
  return bandStyleFromSeed(project.status, `${project.id}:${project.name}`);
}

function bandStyleFromSeed(status: CompanyProjectStatus, seed: string): CSSProperties {
  const hash = hashString(seed);
  const variants = statusPalette[status];
  const [first, second] = variants[hash % variants.length];
  const angle = 116 + (hash % 40);
  const firstX = 12 + (hash % 24);
  const firstY = 14 + ((hash >> 3) % 18);
  const secondX = 68 + ((hash >> 5) % 18);
  const secondY = 18 + ((hash >> 7) % 24);
  return {
    "--band-a": first,
    "--band-b": second,
    "--band-angle": `${angle}deg`,
    "--band-a-x": `${firstX}%`,
    "--band-a-y": `${firstY}%`,
    "--band-b-x": `${secondX}%`,
    "--band-b-y": `${secondY}%`,
  } as CSSProperties;
}

function hashString(value: string): number {
  let hash = 0;
  for (let index = 0; index < value.length; index += 1) {
    hash = (hash * 31 + value.charCodeAt(index)) >>> 0;
  }
  return hash;
}

export function statusLabel(status: CompanyProjectStatus): string {
  switch (status) {
    case "draft":
      return "În pregătire";
    case "active":
      return "Activ";
    case "completed":
      return "Finalizat";
    case "archived":
      return "Arhivat";
    default:
      return status;
  }
}

function formatCompactRange(startsAt: string | null, dueAt: string | null): string {
  const start = formatDate(startsAt);
  const due = formatDate(dueAt);
  if (start && due) return `${start} - ${due}`;
  return start ?? due ?? "---";
}

function projectTypeLabel(value: string | null): string {
  if (!value) return "General";
  return projectTypeLabels[value] ?? value;
}

function formatDate(value: string | null): string | null {
  if (!value) return null;
  return new Date(value).toLocaleDateString("ro-RO", {
    day: "2-digit",
    month: "short",
  });
}

function timelineProgress(startsAt: string | null, dueAt: string | null): number {
  if (!startsAt || !dueAt) return 0;
  const start = new Date(startsAt).getTime();
  const end = new Date(dueAt).getTime();
  const now = Date.now();
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return 0;
  return Math.max(0, Math.min(100, Math.round(((now - start) / (end - start)) * 100)));
}
