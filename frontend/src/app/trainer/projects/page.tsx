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

export default async function TrainerProjectsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; company?: string; status?: string; type?: string }>;
}) {
  const filters = await searchParams;
  const projects = await getAllCompanyProjects(await getServerApiRequestOptions());
  const query = (filters.q ?? "").trim().toLowerCase();
  const filteredProjects = projects
    .filter((project) => !query || `${project.name} ${project.company_name ?? ""}`.toLowerCase().includes(query))
    .filter((project) => !filters.company || project.company_id === filters.company)
    .filter((project) => !filters.status || project.status === filters.status)
    .filter((project) => !filters.type || project.project_type === filters.type)
    .sort((first, second) => {
      const statusRank = (status: CompanyProjectStatus) => status === "active" ? 0 : status === "draft" ? 1 : status === "completed" ? 2 : 3;
      const rankDiff = statusRank(first.status) - statusRank(second.status);
      if (rankDiff !== 0) return rankDiff;
      return (second.updated_at ?? "").localeCompare(first.updated_at ?? "");
    });
  const activeCount = projects.filter((project) => project.status === "active").length;
  const companies = Array.from(
    new Map(projects.map((project) => [project.company_id, project.company_name ?? "Companie"])).entries(),
  ).sort((first, second) => first[1].localeCompare(second[1]));
  const projectTypes = Array.from(new Set(projects.map((project) => project.project_type).filter(Boolean))).sort();

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

        <form className="grid gap-3 rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm md:grid-cols-4">
          <input
            name="q"
            defaultValue={filters.q ?? ""}
            placeholder="Caută proiect sau companie"
            className="min-h-11 rounded-xl border border-[var(--border)] bg-background px-3 text-sm font-semibold text-foreground outline-none focus:border-burgundy/45"
          />
          <select name="company" defaultValue={filters.company ?? ""} className="min-h-11 rounded-xl border border-[var(--border)] bg-background px-3 text-sm font-semibold text-foreground outline-none focus:border-burgundy/45">
            <option value="">Toate companiile</option>
            {companies.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select>
          <select name="status" defaultValue={filters.status ?? ""} className="min-h-11 rounded-xl border border-[var(--border)] bg-background px-3 text-sm font-semibold text-foreground outline-none focus:border-burgundy/45">
            <option value="">Toate statusurile</option>
            <option value="active">Active</option>
            <option value="draft">În pregătire</option>
            <option value="completed">Finalizate</option>
            <option value="archived">Arhivate</option>
          </select>
          <div className="flex gap-2">
            <select name="type" defaultValue={filters.type ?? ""} className="min-h-11 min-w-0 flex-1 rounded-xl border border-[var(--border)] bg-background px-3 text-sm font-semibold text-foreground outline-none focus:border-burgundy/45">
              <option value="">Toate tipurile</option>
              {projectTypes.map((type) => <option key={type} value={type ?? ""}>{type}</option>)}
            </select>
            <button type="submit" className="tap-soft rounded-xl bg-burgundy px-4 text-sm font-bold text-white hover:bg-burgundy-700">
              Filtrează
            </button>
          </div>
        </form>

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
            {filteredProjects.map((project) => (
              <Link
                key={project.id}
                href={`/trainer/projects/${project.id}`}
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
                  Deschide proiectul
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
