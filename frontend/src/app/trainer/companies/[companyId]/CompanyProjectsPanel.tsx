"use client";

import {
  CalendarDaysIcon,
  ChevronRightIcon,
  FilterIcon,
  FolderPlusIcon,
  Loader2Icon,
  PlusIcon,
  XIcon,
} from "lucide-react";
import Link from "next/link";
import { useDeferredValue, useEffect, useMemo, useRef, useState, type FormEvent } from "react";

import {
  createCompanyProject,
  type CompanyAssignment,
  type CompanyProject,
  type CompanyProjectStatus,
} from "@/api/companies";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import {
  formatProjectDate,
  formatProjectDateRange,
  ProjectStatusBadge,
  projectTypeLabel,
  statusLabel,
  statusRank,
} from "@/components/projects/project-display";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyContent,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { ModalLayer } from "@/components/ui/modal-layer";
import { SelectControl } from "@/components/ui/select-control";
import { Textarea } from "@/components/ui/textarea";
import { useUrlState } from "@/hooks/use-url-state";
import {
  normalizeWorkspaceSearch,
  SearchableProjectFilter,
  WorkspaceSearchInput,
} from "../../projects/project-workspace-controls";

type CompanyProjectsPanelProps = {
  companyId: string;
  initialProjects: CompanyProject[];
  assignments: CompanyAssignment[];
};

type ProjectStatusFilter = "all" | CompanyProjectStatus;

const statusFilters: Array<{ value: ProjectStatusFilter; label: string }> = [
  { value: "all", label: "Toate" },
  { value: "active", label: "Active" },
  { value: "draft", label: "În pregătire" },
  { value: "completed", label: "Finalizate" },
  { value: "archived", label: "Arhivate" },
];

const statusFilterValues = new Set<ProjectStatusFilter>(statusFilters.map((filter) => filter.value));

export function CompanyProjectsPanel({
  companyId,
  initialProjects,
  assignments,
}: CompanyProjectsPanelProps) {
  const { get, searchKey, setParam, setParams } = useUrlState();
  const [projects, setProjects] = useState(initialProjects);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [projectType, setProjectType] = useState("team_coaching");
  const [startDate, setStartDate] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [formOpenDate, setFormOpenDate] = useState("");
  const [formCloseDate, setFormCloseDate] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const creatingRef = useRef(false);
  const [statusFilter, setStatusFilter] = useState<ProjectStatusFilter>(() => parseStatusFilter(get("status")));
  const [query, setQuery] = useState(() => get("q") ?? "");
  const [createOpen, setCreateOpen] = useState(get("modal") === "create-project");
  const deferredQuery = useDeferredValue(query);

  useEffect(() => {
    setStatusFilter(parseStatusFilter(get("status")));
    setQuery(get("q") ?? "");
    setCreateOpen(get("modal") === "create-project");
  }, [get, searchKey]);

  function closeCreateModal() {
    setCreateOpen(false);
    setParam("modal", null, "replace");
  }

  function updateStatusFilter(nextFilter: ProjectStatusFilter) {
    setStatusFilter(nextFilter);
    setParam("status", nextFilter === "all" ? null : nextFilter, "push");
  }

  function updateQuery(nextQuery: string) {
    setQuery(nextQuery);
    setParam("q", nextQuery || null, "replace");
  }

  const projectCounts = useMemo(() => {
    const counts: Record<ProjectStatusFilter, number> = {
      all: projects.length,
      active: 0,
      archived: 0,
      completed: 0,
      draft: 0,
    };

    for (const project of projects) {
      counts[project.status] += 1;
    }

    return counts;
  }, [projects]);

  const assignmentProgressByProject = useMemo(() => {
    const progress = new Map<string, { completed: number; total: number }>();

    for (const assignment of assignments) {
      if (!assignment.project_id) continue;
      const current = progress.get(assignment.project_id) ?? { completed: 0, total: 0 };
      current.total += 1;
      if (["submitted", "validated", "scored"].includes(assignment.status)) current.completed += 1;
      progress.set(assignment.project_id, current);
    }

    return progress;
  }, [assignments]);

  const visibleProjects = useMemo(() => {
    const normalizedQuery = normalizeWorkspaceSearch(deferredQuery);

    return projects
      .filter((project) => statusFilter === "all" || project.status === statusFilter)
      .filter((project) => {
        if (!normalizedQuery) return true;
        const searchableText = normalizeWorkspaceSearch([
          project.name,
          project.description,
          projectTypeLabel(project.project_type),
          statusLabel(project.status),
        ].filter(Boolean).join(" "));
        return searchableText.includes(normalizedQuery);
      })
      .sort((first, second) => {
        const rankDiff = statusRank(first.status) - statusRank(second.status);
        if (rankDiff !== 0) return rankDiff;
        return (second.updated_at ?? "").localeCompare(first.updated_at ?? "");
      });
  }, [deferredQuery, projects, statusFilter]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (creatingRef.current) return;

    const trimmedName = name.trim();
    if (!trimmedName) {
      setFormError("Completează numele proiectului.");
      setMessage(null);
      return;
    }

    creatingRef.current = true;
    setIsCreating(true);
    setMessage(null);
    setFormError(null);
    try {
      const created = await createCompanyProject(companyId, {
        name: trimmedName,
        description,
        projectType,
        status: "draft",
        startsAt: dateInputToIso(startDate),
        dueAt: dateInputToIso(dueDate),
        formOpensAt: dateInputToIso(formOpenDate),
        formClosesAt: dateInputToIso(formCloseDate),
      });
      setProjects((current) => [created, ...current]);
      setName("");
      setDescription("");
      setProjectType("team_coaching");
      setStartDate("");
      setDueDate("");
      setFormOpenDate("");
      setFormCloseDate("");
      updateStatusFilter("all");
      closeCreateModal();
      setMessage("Proiectul a fost salvat.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Proiectul nu a putut fi salvat.");
    } finally {
      creatingRef.current = false;
      setIsCreating(false);
    }
  }

  return (
    <section className="flex flex-col gap-5">
      <div className="rounded-lg border bg-surface p-3 text-foreground shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3 px-1">
          <div>
            <h2 className="text-lg font-semibold text-foreground">Proiecte</h2>
            <p className="mt-1 text-xs font-medium text-muted-foreground">
              {assignments.length === 0
                ? "Fără asignări"
                : assignments.length === 1
                  ? "1 asignare"
                  : `${assignments.length} asignări`}
            </p>
          </div>
          <Button
            type="button"
            size="sm"
            className="shrink-0"
            onClick={() => {
              setCreateOpen(true);
              setParams({ modal: "create-project" }, "push");
            }}
          >
            <PlusIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
            Proiect nou
          </Button>
        </div>

        <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(20rem,1fr)_auto] xl:items-center">
          <WorkspaceSearchInput
            id="company-projects-search"
            label="Caută proiect"
            value={query}
            onValueChange={updateQuery}
            placeholder="Caută proiect după nume, tip sau status"
          />

          <SearchableProjectFilter
            icon={FilterIcon}
            label="Status proiecte"
            value={statusFilter}
            allLabel={`Toate · ${projectCounts.all}`}
            options={statusFilters
              .filter((filter) => filter.value !== "all")
              .map((filter) => ({
                value: filter.value,
                label: `${filter.label} · ${projectCounts[filter.value]}`,
              }))}
            onValueChange={(value) => updateStatusFilter((value || "all") as ProjectStatusFilter)}
            className="xl:w-56"
          />
        </div>
      </div>

      <span className="sr-only" role="status" aria-live="polite">
        {query !== deferredQuery ? "Se actualizează lista" : ""}
      </span>

      {message ? <InlineFeedback>{message}</InlineFeedback> : null}

      {createOpen ? (
        <ModalLayer
          labelledBy="create-project-title"
          onClose={() => {
            if (!isCreating) closeCreateModal();
          }}
          closeOnBackdrop={!isCreating}
          panelClassName="max-w-2xl"
        >
          <div className="flex items-start justify-between gap-4">
            <h3 id="create-project-title" className="text-xl font-semibold text-foreground">Proiect nou</h3>
            <Button
              type="button"
              onClick={closeCreateModal}
              disabled={isCreating}
              variant="outline"
              size="icon-sm"
              aria-label="Închide"
            >
              <XIcon aria-hidden="true" strokeWidth={1.8} />
            </Button>
          </div>

          <form onSubmit={handleCreate} className="mt-6 flex flex-col gap-5" aria-busy={isCreating}>
            {formError ? (
              <InlineFeedback id="create-project-error" tone="danger">
                {formError}
              </InlineFeedback>
            ) : null}
            <FieldGroup className="grid gap-4 sm:grid-cols-2">
              <Field data-invalid={Boolean(formError && !name.trim()) || undefined}>
                <FieldLabel htmlFor="company-project-name">Nume proiect</FieldLabel>
                <Input
                  id="company-project-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Ex: Leadership Q3 2026"
                  aria-invalid={Boolean(formError && !name.trim())}
                  aria-describedby={formError ? "create-project-error" : undefined}
                  disabled={isCreating}
                  autoFocus
                />
              </Field>
              <Field>
                <FieldLabel>Tip proiect</FieldLabel>
                <SelectControl
                  label="Tip proiect"
                  value={projectType}
                  onChange={(event) => setProjectType(event.target.value)}
                  className="bg-surface"
                  disabled={isCreating}
                >
                  <option value="team_coaching">Coaching de echipă</option>
                  <option value="individual_coaching">Coaching individual</option>
                  <option value="leadership_program">Program de leadership</option>
                  <option value="custom">Personalizat</option>
                </SelectControl>
              </Field>
            </FieldGroup>
            <FieldGroup className="grid gap-4 sm:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="company-project-start-date">Start proiect</FieldLabel>
                <Input
                  id="company-project-start-date"
                  value={startDate}
                  onChange={(event) => setStartDate(event.target.value)}
                  type="date"
                  disabled={isCreating}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="company-project-due-date">Final proiect</FieldLabel>
                <Input
                  id="company-project-due-date"
                  value={dueDate}
                  onChange={(event) => setDueDate(event.target.value)}
                  type="date"
                  disabled={isCreating}
                />
              </Field>
            </FieldGroup>
            <FieldGroup className="grid gap-4 sm:grid-cols-2">
              <Field>
                <FieldLabel htmlFor="company-project-form-open-date">Formulare active din</FieldLabel>
                <Input
                  id="company-project-form-open-date"
                  value={formOpenDate}
                  onChange={(event) => setFormOpenDate(event.target.value)}
                  type="date"
                  disabled={isCreating}
                />
              </Field>
              <Field>
                <FieldLabel htmlFor="company-project-form-close-date">Active până la</FieldLabel>
                <Input
                  id="company-project-form-close-date"
                  value={formCloseDate}
                  onChange={(event) => setFormCloseDate(event.target.value)}
                  type="date"
                  disabled={isCreating}
                />
              </Field>
            </FieldGroup>
            <Field>
              <FieldLabel htmlFor="company-project-description">Notițe interne</FieldLabel>
              <Textarea
                id="company-project-description"
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={3}
                placeholder="Obiective, contextul intervenției"
                className="resize-none bg-surface leading-relaxed"
                disabled={isCreating}
              />
            </Field>
            {isCreating ? <p role="status" className="text-sm font-semibold text-muted-foreground">Creăm proiectul</p> : null}
            <Button
              type="submit"
              disabled={isCreating}
              className="w-full"
            >
              {isCreating ? <Loader2Icon data-icon="inline-start" className="animate-spin" aria-hidden="true" /> : null}
              {isCreating ? "Creăm proiectul" : "Salvează proiectul"}
            </Button>
          </form>
        </ModalLayer>
      ) : null}

      {visibleProjects.length === 0 ? (
        <Empty className="min-h-[18rem] border bg-surface shadow-sm">
          <EmptyHeader>
            <EmptyMedia variant="icon">
              <FolderPlusIcon aria-hidden="true" strokeWidth={1.8} />
            </EmptyMedia>
            <EmptyTitle>Niciun proiect găsit</EmptyTitle>
            <EmptyDescription>Schimbă filtrul sau creează un proiect.</EmptyDescription>
          </EmptyHeader>
          <EmptyContent>
            <Button
              type="button"
              onClick={() => {
                setCreateOpen(true);
                setParams({ modal: "create-project" }, "push");
              }}
            >
              <PlusIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
              Proiect nou
            </Button>
          </EmptyContent>
        </Empty>
      ) : (
        <div className="overflow-hidden rounded-lg border bg-surface shadow-sm">
          <div className="overflow-x-auto">
            <table className="w-full min-w-[64rem] text-left text-sm">
              <thead className="bg-muted/60 text-xs font-semibold text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-3">Proiect</th>
                  <th scope="col" className="min-w-28 px-4 py-3">Status</th>
                  <th scope="col" className="px-4 py-3">Tip</th>
                  <th scope="col" className="min-w-40 px-4 py-3">Calendar</th>
                  <th scope="col" className="min-w-36 px-4 py-3">Completare</th>
                  <th scope="col" className="px-4 py-3">Actualizat</th>
                  <th scope="col" className="min-w-44 px-4 py-3">Următorul pas</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {visibleProjects.map((project) => (
                  <tr key={project.id} className="transition-colors hover:bg-muted/45">
                    <td className="max-w-[22rem] px-4 py-4">
                      <Link href={`/trainer/projects/${project.id}`} className="group inline-flex max-w-full flex-col gap-1 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45">
                        <span className="truncate text-base font-semibold text-foreground group-hover:text-primary">{project.name}</span>
                        {project.description ? (
                          <span className="line-clamp-1 text-xs leading-5 text-muted-foreground">{project.description}</span>
                        ) : null}
                      </Link>
                    </td>
                    <td className="px-4 py-4">
                      <ProjectStatusBadge status={project.status} />
                    </td>
                    <td className="px-4 py-4 font-medium text-foreground">{projectTypeLabel(project.project_type)}</td>
                    <td className="min-w-40 px-4 py-4">
                      <span className="inline-flex items-center gap-2 whitespace-nowrap text-muted-foreground">
                        <CalendarDaysIcon aria-hidden="true" className="size-4 shrink-0" strokeWidth={1.8} />
                        <span>{formatProjectDateRange(project.starts_at, project.due_at)}</span>
                      </span>
                    </td>
                    <td className="px-4 py-4">
                      <ProjectCompletion progress={assignmentProgressByProject.get(project.id)} />
                    </td>
                    <td className="px-4 py-4 text-muted-foreground">{formatProjectDate(project.updated_at)}</td>
                    <td className="px-4 py-4">
                      <Link
                        href={`/trainer/projects/${project.id}`}
                        className="inline-flex items-center gap-1.5 font-semibold text-foreground hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45"
                      >
                        {projectActionLabel(project.status)}
                        <ChevronRightIcon aria-hidden="true" className="size-4" strokeWidth={1.8} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}

function ProjectCompletion({ progress }: { progress?: { completed: number; total: number } }) {
  if (!progress || progress.total === 0) {
    return <span className="text-xs font-medium text-muted-foreground">Nicio asignare</span>;
  }

  const percentage = Math.round((progress.completed / progress.total) * 100);

  return (
    <div className="min-w-28">
      <div className="flex items-center justify-between gap-3 text-xs">
        <span className="font-semibold tabular-nums text-foreground">{progress.completed}/{progress.total}</span>
        <span className="tabular-nums text-muted-foreground">{percentage}%</span>
      </div>
      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full bg-primary" style={{ width: `${percentage}%` }} />
      </div>
    </div>
  );
}

function projectActionLabel(status: CompanyProjectStatus): string {
  switch (status) {
    case "draft":
      return "Continuă configurarea";
    case "active":
      return "Urmărește progresul";
    case "completed":
      return "Deschide raportul";
    case "archived":
      return "Consultă istoricul";
  }
}

function parseStatusFilter(value: string | null): ProjectStatusFilter {
  if (!value) return "all";
  return statusFilterValues.has(value as ProjectStatusFilter) ? (value as ProjectStatusFilter) : "all";
}

function dateInputToIso(value: string): string | null {
  if (!value) return null;
  return `${value}T00:00:00.000Z`;
}
