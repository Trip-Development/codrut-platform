import Link from "next/link";

import { getTrainerDashboardSummary } from "@/api/trainer";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";

export default async function TrainerProjectsPage() {
  const summary = await getTrainerDashboardSummary();

  return (
    <AppShell
      audience="trainer"
      eyebrow="Proiecte"
      title="Proiecte si programe active"
      description="Lista de lucru pentru companii, perioade, invitatii, completari si urmatorul pas operational."
      navItems={trainerNavItems}
      activeHref="/trainer/projects"
    >
      <section className="grid gap-4 lg:grid-cols-3">
        {summary.activeProjects.map((project) => {
          const completion = project.total > 0 ? Math.round((project.completed / project.total) * 100) : 0;

          return (
            <article key={project.id} className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">
                    {project.stage}
                  </p>
                  <h2 className="mt-2 text-lg font-semibold text-foreground">{project.company}</h2>
                  <p className="mt-1 text-sm font-semibold text-burgundy">{project.projectName}</p>
                </div>
                <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-semibold text-foreground/55">
                  {project.invited} invitati
                </span>
              </div>
              <p className="mt-4 text-sm leading-6 text-foreground/62">{project.nextAction}</p>
              <div className="mt-4 flex items-center justify-between text-sm font-semibold text-foreground/62">
                <span>{project.completed}/{project.total}</span>
                <span>{completion}%</span>
              </div>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-surface-muted">
                <div className="h-full rounded-full bg-burgundy" style={{ width: `${completion}%` }} />
              </div>
              <Link
                href={project.href}
                className="tap-soft mt-4 inline-flex w-full justify-center rounded-xl bg-foreground px-4 py-2.5 text-sm font-semibold text-background hover:bg-burgundy hover:text-white"
              >
                Deschide proiectul
              </Link>
            </article>
          );
        })}
      </section>
    </AppShell>
  );
}
