"use client";

import Link from "next/link";
import { useMemo, useState, type FormEvent } from "react";

import {
  createCompanyProject,
  deleteCompanyProject,
  updateCompanyProject,
  type CompanyAssignment,
  type CompanyProject,
  type CompanyProjectStatus,
} from "@/api/companies";

type CompanyProjectsPanelProps = {
  companyId: string;
  initialProjects: CompanyProject[];
  assignments: CompanyAssignment[];
};

const statusOptions: Array<{ value: CompanyProjectStatus; label: string }> = [
  { value: "draft", label: "În pregătire" },
  { value: "active", label: "Activ" },
  { value: "completed", label: "Finalizat" },
  { value: "archived", label: "Arhivat" },
];

const statusTone: Record<CompanyProjectStatus, string> = {
  draft: "bg-surface-muted text-foreground/62",
  active: "bg-green-50 text-green-800 border-green-100",
  completed: "bg-burgundy/10 text-burgundy border-burgundy/15",
  archived: "bg-foreground/8 text-foreground/48",
};

export function CompanyProjectsPanel({
  companyId,
  initialProjects,
  assignments,
}: CompanyProjectsPanelProps) {
  const [projects, setProjects] = useState(initialProjects);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);

  const activeProjects = useMemo(
    () => projects.filter((project) => project.status === "active").length,
    [projects],
  );
  const metricsByProject = useMemo(() => buildProjectMetrics(assignments), [assignments]);

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) return;

    setIsCreating(true);
    setMessage(null);
    try {
      const created = await createCompanyProject(companyId, {
        name: trimmedName,
        description,
        status: "draft",
        dueAt: dateInputToIso(dueDate),
      });
      setProjects((current) => [created, ...current]);
      setName("");
      setDescription("");
      setDueDate("");
      setMessage("Proiectul a fost salvat.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Proiectul nu a putut fi salvat.");
    } finally {
      setIsCreating(false);
    }
  }

  async function handleStatusChange(project: CompanyProject, status: CompanyProjectStatus) {
    setBusyId(project.id);
    setMessage(null);
    try {
      const updated = await updateCompanyProject(companyId, project.id, {
        name: project.name,
        description: project.description,
        status,
        startsAt: project.starts_at,
        dueAt: project.due_at,
      });
      setProjects((current) => current.map((item) => (item.id === updated.id ? updated : item)));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Statusul proiectului nu a putut fi actualizat.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(project: CompanyProject) {
    const confirmed = window.confirm(`Ștergi proiectul „${project.name}”?`);
    if (!confirmed) return;

    setBusyId(project.id);
    setMessage(null);
    try {
      await deleteCompanyProject(companyId, project.id);
      setProjects((current) => current.filter((item) => item.id !== project.id));
      setMessage("Proiectul a fost șters.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Proiectul nu a putut fi șters.");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <section className="rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
      <div className="grid gap-0 xl:grid-cols-[22rem_minmax(0,1fr)]">
        <form onSubmit={handleCreate} className="border-b border-[var(--border)] p-5 xl:border-b-0 xl:border-r">
          <p className="text-xs font-semibold text-burgundy/75">Proiecte</p>
          <h2 className="mt-1 text-lg font-semibold text-foreground">Spațiul de lucru al companiei</h2>
          <p className="mt-2 text-sm leading-6 text-foreground/62">
            Creează proiectele clientului aici, apoi intră direct în planificarea asignărilor, invitații și rapoarte pentru fiecare proiect.
          </p>
          <div className="mt-4 space-y-3">
            <label className="block text-xs font-bold text-foreground/58">
              Nume proiect
              <input
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="Leadership training septembrie 2026"
                className="mt-1 min-h-10 w-full rounded-xl border border-[var(--border)] bg-background px-3 py-2 text-sm font-semibold text-foreground outline-none focus:border-burgundy/45 focus:ring-2 focus:ring-burgundy/10"
              />
            </label>
            <label className="block text-xs font-bold text-foreground/58">
              Data țintă
              <input
                value={dueDate}
                onChange={(event) => setDueDate(event.target.value)}
                type="date"
                className="mt-1 min-h-10 w-full rounded-xl border border-[var(--border)] bg-background px-3 py-2 text-sm font-semibold text-foreground outline-none focus:border-burgundy/45 focus:ring-2 focus:ring-burgundy/10"
              />
            </label>
            <label className="block text-xs font-bold text-foreground/58">
              Notițe
              <textarea
                value={description}
                onChange={(event) => setDescription(event.target.value)}
                rows={3}
                placeholder="Context, cohortă, obiectiv..."
                className="mt-1 w-full resize-none rounded-xl border border-[var(--border)] bg-background px-3 py-2 text-sm font-medium text-foreground outline-none focus:border-burgundy/45 focus:ring-2 focus:ring-burgundy/10"
              />
            </label>
            <button
              type="submit"
              disabled={isCreating || !name.trim()}
              className="tap-soft inline-flex min-h-10 w-full items-center justify-center rounded-xl bg-burgundy px-4 py-2 text-sm font-bold text-white shadow-sm shadow-burgundy/10 hover:bg-burgundy-700 disabled:cursor-not-allowed disabled:opacity-45"
            >
              {isCreating ? "Se salvează..." : "Creează proiect"}
            </button>
          </div>
          {message ? (
            <p aria-live="polite" className="mt-3 rounded-xl bg-background px-3 py-2 text-xs font-semibold text-foreground/62">
              {message}
            </p>
          ) : null}
        </form>

        <div className="p-5">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-foreground/48">Portofoliu client</p>
              <h3 className="mt-1 text-base font-semibold text-foreground">
                {projects.length} proiecte, {activeProjects} active
              </h3>
            </div>
          </div>

          <div className="mt-4 space-y-3">
            {projects.length === 0 ? (
              <div className="rounded-xl border border-dashed border-[var(--border)] bg-background/70 p-5 text-sm text-foreground/58">
                Niciun proiect creat încă.
              </div>
            ) : (
              projects.map((project) => {
                const metrics = metricsByProject.get(project.id) ?? {
                  total: 0,
                  completed: 0,
                };
                return (
                  <article
                    key={project.id}
                    className="rounded-xl border border-[var(--border)] bg-background p-4 transition-colors hover:border-burgundy/30 hover:bg-surface-muted/45"
                  >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h4 className="truncate text-sm font-semibold text-foreground">{project.name}</h4>
                      <p className="mt-1 text-xs font-semibold text-foreground/45">
                        {formatDate(project.starts_at) ?? "Fără start"} · {formatDate(project.due_at) ?? "Fără termen"}
                      </p>
                    </div>
                    <span className={`rounded-full border px-2.5 py-1 text-xs font-bold ${statusTone[project.status]}`}>
                      {statusLabel(project.status)}
                    </span>
                  </div>
                  {project.description ? (
                    <p className="mt-3 text-sm leading-6 text-foreground/62">{project.description}</p>
                  ) : null}
                  <div className="mt-4 grid grid-cols-2 gap-2 text-xs font-semibold text-foreground/58">
                    <ProjectMetric label="Asignări" value={metrics.total} />
                    <ProjectMetric label="Finalizate" value={metrics.completed} />
                  </div>
                  <div className="mt-4 flex flex-wrap gap-2">
                    <Link
                      href={`/trainer/companies/${companyId}/invitations?projectId=${project.id}`}
                      className="tap-soft min-h-9 rounded-lg border border-[var(--border)] bg-surface px-3 py-2 text-xs font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy"
                    >
                      Invitații
                    </Link>
                    <Link
                      href={`/trainer/companies/${companyId}/reports?projectId=${project.id}`}
                      className="tap-soft min-h-9 rounded-lg border border-[var(--border)] bg-surface px-3 py-2 text-xs font-bold text-foreground hover:border-burgundy/45 hover:text-burgundy"
                    >
                      Rapoarte
                    </Link>
                    <select
                      value={project.status}
                      onChange={(event) => handleStatusChange(project, event.target.value as CompanyProjectStatus)}
                      disabled={busyId === project.id}
                      className="min-h-9 rounded-lg border border-[var(--border)] bg-surface px-2.5 text-xs font-bold text-foreground outline-none hover:border-burgundy/45 focus:border-burgundy/45"
                    >
                      {statusOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                    <button
                      type="button"
                      onClick={() => handleDelete(project)}
                      disabled={busyId === project.id}
                      className="tap-soft min-h-9 rounded-lg border border-red-200 bg-red-50 px-3 text-xs font-bold text-red-800 hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-45"
                    >
                      Șterge
                    </button>
                  </div>
                </article>
                );
              })
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function statusLabel(status: CompanyProjectStatus): string {
  return statusOptions.find((option) => option.value === status)?.label ?? status;
}

function ProjectMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg bg-surface-muted/60 px-3 py-2">
      <p className="text-foreground/42">{label}</p>
      <p className="mt-1 text-sm text-foreground">{value}</p>
    </div>
  );
}

function buildProjectMetrics(assignments: CompanyAssignment[]) {
  const metrics = new Map<string, { total: number; completed: number }>();
  for (const assignment of assignments) {
    if (!assignment.project_id) continue;
    const current = metrics.get(assignment.project_id) ?? { total: 0, completed: 0 };
    current.total += 1;
    if (["submitted", "validated", "scored"].includes(assignment.status)) {
      current.completed += 1;
    }
    metrics.set(assignment.project_id, current);
  }
  return metrics;
}

function formatDate(value: string | null): string | null {
  if (!value) return null;
  return new Date(value).toLocaleDateString("ro-RO", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function dateInputToIso(value: string): string | null {
  if (!value) return null;
  return `${value}T00:00:00.000Z`;
}
