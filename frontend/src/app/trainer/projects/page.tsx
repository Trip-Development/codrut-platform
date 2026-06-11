import Link from "next/link";

import { getAllCompanyProjects, type CompanyProjectStatus } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";

const statusTone: Record<CompanyProjectStatus, string> = {
  draft: "bg-surface-muted text-foreground/62",
  active: "border-green-100 bg-green-50 text-green-800",
  completed: "border-burgundy/15 bg-burgundy/10 text-burgundy",
  archived: "bg-foreground/8 text-foreground/48",
};

export default async function TrainerProjectsPage() {
  const projects = await getAllCompanyProjects(await getServerApiRequestOptions());
  const activeCount = projects.filter((project) => project.status === "active").length;

  return (
    <AppShell
      audience="trainer"
      eyebrow="Proiecte"
      title="Proiecte pe companii"
      description="O privire rapidă peste proiectele active, în pregătire și finalizate pentru fiecare client."
      navItems={trainerNavItems}
      activeHref="/trainer/projects"
    >
      <div className="space-y-5">
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
          <div className="grid gap-4 md:grid-cols-3">
            <ProjectSummary label="Proiecte totale" value={projects.length} />
            <ProjectSummary label="Active" value={activeCount} />
            <ProjectSummary label="Companii" value={new Set(projects.map((project) => project.company_id)).size} />
          </div>
        </section>

        {projects.length === 0 ? (
          <section className="rounded-2xl border border-dashed border-[var(--border)] bg-surface/70 p-8 text-center">
            <p className="text-base font-semibold text-foreground">Nu există proiecte încă.</p>
            <p className="mt-2 text-sm text-foreground/58">
              Intră într-o companie și creează primul proiect din sumarul ei.
            </p>
            <Link
              href="/trainer/companies"
              className="tap-soft mt-4 inline-flex min-h-10 items-center justify-center rounded-xl bg-burgundy px-4 py-2.5 text-sm font-bold text-white hover:bg-burgundy-700"
            >
              Deschide companii
            </Link>
          </section>
        ) : (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {projects.map((project) => (
              <Link
                key={project.id}
                href={`/trainer/companies/${project.company_id}`}
                className="tap-soft group rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm transition-all hover:-translate-y-0.5 hover:border-burgundy/30 hover:shadow-md"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-xs font-bold text-burgundy/75">
                      {project.company_name ?? "Companie"}
                    </p>
                    <h2 className="mt-1 truncate text-base font-semibold text-foreground">{project.name}</h2>
                  </div>
                  <span className={`shrink-0 rounded-full border px-2.5 py-1 text-xs font-bold ${statusTone[project.status]}`}>
                    {statusLabel(project.status)}
                  </span>
                </div>
                {project.description ? (
                  <p className="mt-3 line-clamp-2 text-sm leading-6 text-foreground/62">{project.description}</p>
                ) : null}
                <div className="mt-5 grid grid-cols-2 gap-2 text-xs font-semibold text-foreground/54">
                  <ProjectMeta label="Start" value={formatDate(project.starts_at) ?? "---"} />
                  <ProjectMeta label="Termen" value={formatDate(project.due_at) ?? "---"} />
                </div>
                <p className="mt-4 text-sm font-semibold text-burgundy group-hover:text-burgundy-700">
                  Deschide spațiul companiei
                </p>
              </Link>
            ))}
          </div>
        )}
      </div>
    </AppShell>
  );
}

function ProjectSummary({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-background/80 px-4 py-3">
      <p className="text-xs font-semibold text-foreground/48">{label}</p>
      <p className="mt-1 text-2xl font-semibold text-foreground">{value}</p>
    </div>
  );
}

function ProjectMeta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-surface-muted/60 px-3 py-2">
      <p className="text-foreground/42">{label}</p>
      <p className="mt-1 text-foreground/72">{value}</p>
    </div>
  );
}

function statusLabel(status: CompanyProjectStatus): string {
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

function formatDate(value: string | null): string | null {
  if (!value) return null;
  return new Date(value).toLocaleDateString("ro-RO", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}
