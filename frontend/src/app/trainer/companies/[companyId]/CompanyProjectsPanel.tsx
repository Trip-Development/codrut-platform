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
  const [projectType, setProjectType] = useState("team_coaching");
  const [startDate, setStartDate] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [formOpenDate, setFormOpenDate] = useState("");
  const [formCloseDate, setFormCloseDate] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [showArchived, setShowArchived] = useState(false);

  const activeProjects = useMemo(
    () => projects.filter((project) => project.status === "active").length,
    [projects],
  );
  const visibleProjects = useMemo(
    () =>
      projects
        .filter((project) => showArchived || project.status !== "archived")
        .sort((first, second) => {
          const rank = (status: CompanyProjectStatus) => status === "active" ? 0 : status === "draft" ? 1 : status === "completed" ? 2 : 3;
          const rankDiff = rank(first.status) - rank(second.status);
          if (rankDiff !== 0) return rankDiff;
          return (second.updated_at ?? "").localeCompare(first.updated_at ?? "");
        }),
    [projects, showArchived],
  );
  const archivedCount = projects.filter((project) => project.status === "archived").length;
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
        projectType: project.project_type,
        status,
        startsAt: project.starts_at,
        dueAt: project.due_at,
        formOpensAt: project.form_opens_at,
        formClosesAt: project.form_closes_at,
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
    <section className="bento-card overflow-hidden">
      <div className="grid gap-0 xl:grid-cols-[22rem_minmax(0,1fr)]">
        {/* Create Project Form - Sidebar */}
        <form onSubmit={handleCreate} className="border-b border-[var(--border)] bg-surface-muted/30 p-6 xl:border-b-0 xl:border-r relative overflow-hidden">
          <div className="absolute top-0 right-0 p-32 bg-burgundy/5 blur-3xl rounded-full -mr-16 -mt-16 pointer-events-none z-0"></div>
          <div className="relative z-10">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80">Proiecte</p>
            <h2 className="mt-1 text-xl font-bold text-foreground">Inițiază un proiect</h2>
            <p className="mt-3 text-sm leading-relaxed text-foreground/60">
              Setează un proiect nou. Perioada formularelor controlează când linkurile sunt active pentru participanți.
            </p>
            <div className="mt-6 space-y-5">
              <label className="block">
                <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-2 block">Nume proiect</span>
                <input
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="Ex: Leadership Q3 2026"
                  className="w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-bold text-foreground focus:border-burgundy/50 focus:ring-2 focus:ring-burgundy/10 transition-all shadow-inner placeholder:text-foreground/30"
                />
              </label>
              <label className="block">
                <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-2 block">Tip proiect</span>
                <select
                  value={projectType}
                  onChange={(event) => setProjectType(event.target.value)}
                  className="w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-bold text-foreground focus:border-burgundy/50 focus:ring-2 focus:ring-burgundy/10 transition-all shadow-sm appearance-none"
                >
                  <option value="team_coaching">Team coaching</option>
                  <option value="individual_coaching">Individual coaching</option>
                  <option value="leadership_program">Leadership program</option>
                  <option value="custom">Personalizat</option>
                </select>
              </label>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-2 block">Start proiect</span>
                  <input
                    value={startDate}
                    onChange={(event) => setStartDate(event.target.value)}
                    type="date"
                    className="w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-bold text-foreground focus:border-burgundy/50 focus:ring-2 focus:ring-burgundy/10 transition-all shadow-sm"
                  />
                </label>
                <label className="block">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-2 block">Final proiect</span>
                  <input
                    value={dueDate}
                    onChange={(event) => setDueDate(event.target.value)}
                    type="date"
                    className="w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-bold text-foreground focus:border-burgundy/50 focus:ring-2 focus:ring-burgundy/10 transition-all shadow-sm"
                  />
                </label>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-2 block">Formulare active din</span>
                  <input
                    value={formOpenDate}
                    onChange={(event) => setFormOpenDate(event.target.value)}
                    type="date"
                    className="w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-bold text-foreground focus:border-burgundy/50 focus:ring-2 focus:ring-burgundy/10 transition-all shadow-sm"
                  />
                </label>
                <label className="block">
                  <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-2 block">Active până la</span>
                  <input
                    value={formCloseDate}
                    onChange={(event) => setFormCloseDate(event.target.value)}
                    type="date"
                    className="w-full rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-bold text-foreground focus:border-burgundy/50 focus:ring-2 focus:ring-burgundy/10 transition-all shadow-sm"
                  />
                </label>
              </div>
              <label className="block">
                <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-2 block">Notițe interne</span>
                <textarea
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  rows={2}
                  placeholder="Obiective, contextul intervenției..."
                  className="w-full resize-none rounded-xl border border-[var(--border)] bg-surface px-4 py-3 text-sm font-medium leading-relaxed text-foreground focus:border-burgundy/50 focus:ring-2 focus:ring-burgundy/10 transition-all shadow-inner"
                />
              </label>
              <button
                type="submit"
                disabled={isCreating || !name.trim()}
                className="btn-premium w-full mt-2"
              >
                {isCreating ? "Se salvează..." : "Adaugă proiect"}
              </button>
            </div>
            {message ? (
              <p aria-live="polite" className="mt-4 rounded-xl bg-surface-muted/50 border border-[var(--border)] px-4 py-3 text-[11px] font-bold text-foreground/70">
                {message}
              </p>
            ) : null}
          </div>
        </form>

        {/* Projects Grid */}
        <div className="p-6 md:p-8 bg-background/50 flex flex-col h-full">
          <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--border)] pb-5 mb-6">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-foreground/50">Portofoliu</p>
              <h3 className="mt-1 text-xl font-display font-bold text-foreground">
                {projects.length} proiecte <span className="text-foreground/30 font-medium">({activeProjects} active)</span>
              </h3>
            </div>
            {archivedCount > 0 ? (
              <button
                type="button"
                onClick={() => setShowArchived((current) => !current)}
                className="tap-soft rounded-full border border-[var(--border)] bg-surface px-4 py-2 text-[11px] font-bold text-foreground/60 hover:border-burgundy/30 hover:text-burgundy hover:shadow-sm transition-all shadow-sm"
              >
                {showArchived ? "Ascunde arhiva" : `Arată arhiva (${archivedCount})`}
              </button>
            ) : null}
          </div>

          <div className="flex-1">
            {visibleProjects.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full min-h-[400px] rounded-3xl border border-dashed border-[var(--border)] bg-surface/40 p-12 text-center">
                <div className="w-16 h-16 rounded-full bg-surface-muted/50 flex items-center justify-center mb-4 text-foreground/30">
                  <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
                </div>
                <h4 className="text-lg font-bold text-foreground mb-2">Niciun proiect</h4>
                <p className="text-sm font-medium text-foreground/50 max-w-[250px]">
                  Utilizați formularul din stânga pentru a adăuga primul proiect al acestei companii.
                </p>
              </div>
            ) : (
              <div className="grid gap-6 grid-cols-1 lg:grid-cols-2 2xl:grid-cols-3">
                {visibleProjects.map((project) => {
                  const metrics = metricsByProject.get(project.id) ?? {
                    total: 0,
                    completed: 0,
                  };
                  return (
                    <article
                      key={project.id}
                      className="group flex flex-col rounded-3xl border border-[var(--border)] bg-surface p-6 transition-all duration-300 hover:-translate-y-1 hover:shadow-[0_12px_32px_-12px_rgba(137,5,5,0.12)] hover:border-burgundy/20 relative overflow-hidden"
                    >
                      {/* Status Accent Line */}
                      <div className={`absolute top-0 left-0 w-full h-1 ${
                        project.status === 'active' ? 'bg-gradient-to-r from-green-400 to-emerald-500' :
                        project.status === 'completed' ? 'bg-gradient-to-r from-burgundy/40 to-burgundy/80' :
                        project.status === 'draft' ? 'bg-gradient-to-r from-surface-muted to-[var(--border)]' :
                        'bg-foreground/10'
                      }`} />

                      <div className="flex-1 min-w-0 mb-5">
                        <div className="flex flex-wrap items-start justify-between gap-3 mb-3">
                          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[9px] font-bold uppercase tracking-wider border shadow-sm ${statusTone[project.status]}`}>
                            {project.status === "active" ? <span className="h-1.5 w-1.5 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]" /> : null}
                            {statusLabel(project.status)}
                          </span>
                          <span className="text-[10px] font-bold uppercase tracking-wider text-burgundy/70 bg-burgundy/5 px-2 py-1 rounded-md">
                            {projectTypeLabel(project.project_type)}
                          </span>
                        </div>
                        <h4 className="text-lg font-bold text-foreground leading-tight line-clamp-2" title={project.name}>{project.name}</h4>
                        
                        <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] font-semibold text-foreground/50">
                          <div>
                            <span className="block text-[9px] uppercase tracking-wider text-foreground/40 mb-0.5">Perioadă</span>
                            {formatDate(project.starts_at) ?? "TBD"} - {formatDate(project.due_at) ?? "TBD"}
                          </div>
                          <div>
                            <span className="block text-[9px] uppercase tracking-wider text-foreground/40 mb-0.5">Formulare live</span>
                            {formatDate(project.form_opens_at) ?? "oricând"} - {formatDate(project.form_closes_at) ?? "nelimitat"}
                          </div>
                        </div>

                        {project.description ? (
                          <p className="mt-4 text-xs font-medium leading-relaxed text-foreground/60 line-clamp-2" title={project.description}>{project.description}</p>
                        ) : null}
                      </div>

                      <div className="grid grid-cols-2 gap-3 mt-auto mb-5">
                        <div className="rounded-xl border border-[var(--border)] bg-surface-muted/20 px-4 py-3 text-center">
                          <p className="text-[10px] font-bold uppercase tracking-wider text-foreground/50">Asignări</p>
                          <p className="mt-1 text-xl font-display font-bold text-foreground">{metrics.total}</p>
                        </div>
                        <div className="rounded-xl border border-[var(--border)] bg-surface-muted/20 px-4 py-3 text-center">
                          <p className="text-[10px] font-bold uppercase tracking-wider text-foreground/50">Finalizate</p>
                          <p className="mt-1 text-xl font-display font-bold text-burgundy">{metrics.completed}</p>
                        </div>
                      </div>

                      <div className="pt-5 border-t border-[var(--border)] grid grid-cols-2 gap-2">
                        <Link
                          href={`/trainer/projects/${project.id}/participants`}
                          className="tap-soft flex items-center justify-center h-10 rounded-xl bg-surface-muted/50 text-xs font-bold text-foreground hover:bg-surface hover:border hover:border-[var(--border)] hover:shadow-sm transition-all"
                        >
                          Participanți
                        </Link>
                        <Link
                          href={`/trainer/projects/${project.id}/invitations`}
                          className="tap-soft flex items-center justify-center h-10 rounded-xl bg-surface-muted/50 text-xs font-bold text-foreground hover:bg-surface hover:border hover:border-[var(--border)] hover:shadow-sm transition-all"
                        >
                          Invitații
                        </Link>
                        <Link
                          href={`/trainer/projects/${project.id}/reports`}
                          className="tap-soft flex items-center justify-center h-10 rounded-xl bg-surface-muted/50 text-xs font-bold text-foreground hover:bg-surface hover:border hover:border-[var(--border)] hover:shadow-sm transition-all col-span-2"
                        >
                          Vizualizare Rapoarte
                        </Link>
                        <select
                          value={project.status}
                          onChange={(event) => handleStatusChange(project, event.target.value as CompanyProjectStatus)}
                          disabled={busyId === project.id}
                          className="h-10 rounded-xl border border-[var(--border)] bg-surface px-3 text-xs font-bold text-foreground outline-none transition-colors hover:border-burgundy/30 focus:border-burgundy/40 appearance-none col-span-2 shadow-sm text-center"
                        >
                          {statusOptions.map((option) => (
                            <option key={option.value} value={option.value}>
                              Status: {option.label}
                            </option>
                          ))}
                        </select>
                        <button
                          type="button"
                          onClick={() => handleDelete(project)}
                          disabled={busyId === project.id}
                          className="tap-soft h-10 rounded-xl bg-red-50/50 text-xs font-bold text-red-600 hover:bg-red-50 hover:text-red-700 disabled:cursor-not-allowed disabled:opacity-45 transition-colors col-span-2"
                        >
                          Șterge proiectul
                        </button>
                      </div>
                    </article>
                  );
                })}
              </div>
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

function projectTypeLabel(value: string | null): string {
  if (value === "individual_coaching") return "Individual coaching";
  if (value === "leadership_program") return "Leadership program";
  if (value === "custom") return "Personalizat";
  return "Team coaching";
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
