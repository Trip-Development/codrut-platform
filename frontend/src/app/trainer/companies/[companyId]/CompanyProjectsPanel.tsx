"use client";

import { useMemo, useState, type FormEvent } from "react";

import {
  createCompanyProject,
  type CompanyAssignment,
  type CompanyProject,
  type CompanyProjectStatus,
} from "@/api/companies";
import { ProjectCardLink } from "@/components/projects/project-card";

type CompanyProjectsPanelProps = {
  companyId: string;
  initialProjects: CompanyProject[];
  assignments: CompanyAssignment[];
  participantCount: number;
};

export function CompanyProjectsPanel({
  companyId,
  initialProjects,
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
  const [formError, setFormError] = useState<string | null>(null);
  const [isCreating, setIsCreating] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);

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

  async function handleCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedName = name.trim();
    if (!trimmedName) {
      setFormError("Completează numele proiectului. Restul câmpurilor pot fi ajustate mai târziu în Setări.");
      setMessage(null);
      return;
    }

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
      setCreateOpen(false);
      setMessage("Proiectul a fost salvat.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Proiectul nu a putut fi salvat.");
    } finally {
      setIsCreating(false);
    }
  }

  return (
    <section className="space-y-5">
      <div className="page-toolbar">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-foreground/50">Portofoliu</p>
          <h3 className="mt-1 font-display text-xl font-bold text-foreground">
            {projects.length} proiecte <span className="font-medium text-foreground/30">({activeProjects} active)</span>
          </h3>
          <p className="mt-2 max-w-xl text-sm leading-6 text-foreground/58">
            Creează proiectul, apoi adaugă rosterul și pregătește asignările în spațiul lui.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {archivedCount > 0 ? (
            <button
              type="button"
              onClick={() => setShowArchived((current) => !current)}
              className="btn-secondary !px-4 !py-2"
            >
              {showArchived ? "Ascunde arhiva" : `Arată arhiva (${archivedCount})`}
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => setCreateOpen(true)}
            className="btn-primary"
          >
            Adaugă proiect
          </button>
        </div>
      </div>

      {message ? (
        <p aria-live="polite" className="surface-panel px-4 py-3 text-[11px] font-bold text-foreground/70">
          {message}
        </p>
      ) : null}

      {createOpen ? (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => !isCreating && setCreateOpen(false)}>
          <section
            role="dialog"
            aria-modal="true"
            aria-labelledby="create-project-title"
            className="modal-panel max-w-2xl"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80">Proiect nou</p>
                <h3 id="create-project-title" className="mt-1 text-xl font-bold text-foreground">Inițiază un proiect</h3>
                <p className="mt-2 text-sm leading-6 text-foreground/60">
                  Perioada formularelor controlează când linkurile sunt active pentru participanți.
                  Rosterul poate fi adăugat după ce proiectul este creat.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setCreateOpen(false)}
                disabled={isCreating}
                className="tap-soft rounded-full border border-[var(--border)] bg-surface-muted px-3 py-2 text-xs font-bold text-foreground/60 hover:text-burgundy disabled:opacity-50"
              >
                Închide
              </button>
            </div>

            <form onSubmit={handleCreate} className="mt-6 space-y-5">
              {formError ? (
                <p id="create-project-error" className="rounded-xl border border-burgundy/20 bg-burgundy/10 px-4 py-3 text-sm font-semibold text-burgundy">
                  {formError}
                </p>
              ) : null}
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-2 block text-[10px] font-bold uppercase tracking-wider text-foreground/60">Nume proiect</span>
                  <input
                    value={name}
                    onChange={(event) => setName(event.target.value)}
                    placeholder="Ex: Leadership Q3 2026"
                    className="control-input w-full py-3"
                    aria-invalid={Boolean(formError && !name.trim())}
                    aria-describedby={formError ? "create-project-error" : undefined}
                    autoFocus
                  />
                </label>
                <label className="block">
                  <span className="mb-2 block text-[10px] font-bold uppercase tracking-wider text-foreground/60">Tip proiect</span>
                  <select
                    value={projectType}
                    onChange={(event) => setProjectType(event.target.value)}
                    className="control-input w-full appearance-none py-3"
                  >
                    <option value="team_coaching">Team coaching</option>
                    <option value="individual_coaching">Individual coaching</option>
                    <option value="leadership_program">Leadership program</option>
                    <option value="custom">Personalizat</option>
                  </select>
                </label>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-2 block text-[10px] font-bold uppercase tracking-wider text-foreground/60">Start proiect</span>
                  <input value={startDate} onChange={(event) => setStartDate(event.target.value)} type="date" className="control-input w-full py-3" />
                </label>
                <label className="block">
                  <span className="mb-2 block text-[10px] font-bold uppercase tracking-wider text-foreground/60">Final proiect</span>
                  <input value={dueDate} onChange={(event) => setDueDate(event.target.value)} type="date" className="control-input w-full py-3" />
                </label>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="mb-2 block text-[10px] font-bold uppercase tracking-wider text-foreground/60">Formulare active din</span>
                  <input value={formOpenDate} onChange={(event) => setFormOpenDate(event.target.value)} type="date" className="control-input w-full py-3" />
                </label>
                <label className="block">
                  <span className="mb-2 block text-[10px] font-bold uppercase tracking-wider text-foreground/60">Active până la</span>
                  <input value={formCloseDate} onChange={(event) => setFormCloseDate(event.target.value)} type="date" className="control-input w-full py-3" />
                </label>
              </div>
              <label className="block">
                <span className="mb-2 block text-[10px] font-bold uppercase tracking-wider text-foreground/60">Notițe interne</span>
                <textarea
                  value={description}
                  onChange={(event) => setDescription(event.target.value)}
                  rows={3}
                  placeholder="Obiective, contextul intervenției..."
                  className="control-input w-full resize-none py-3 leading-relaxed"
                />
              </label>
              <button
                type="submit"
                disabled={isCreating}
                className="btn-primary w-full"
              >
                {isCreating ? "Se salvează..." : "Salvează proiectul"}
              </button>
            </form>
          </section>
        </div>
      ) : null}

      {visibleProjects.length === 0 ? (
        <div className="surface-panel-muted flex min-h-[20rem] flex-col items-center justify-center border-dashed p-12 text-center">
          <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-xl bg-surface text-foreground/30">
            <svg className="h-8 w-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
          </div>
          <h4 className="text-lg font-bold text-foreground">Niciun proiect</h4>
          <p className="mt-2 max-w-sm text-sm font-medium leading-relaxed text-foreground/50">
            Adaugă primul proiect al acestei companii din butonul de sus.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2 2xl:grid-cols-3">
          {visibleProjects.map((project) => (
            <ProjectCardLink key={project.id} project={project} />
          ))}
        </div>
      )}
    </section>
  );
}

function dateInputToIso(value: string): string | null {
  if (!value) return null;
  return `${value}T00:00:00.000Z`;
}
