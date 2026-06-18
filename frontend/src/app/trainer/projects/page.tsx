import Link from "next/link";

import { getAllCompanyProjects, type CompanyProjectStatus } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";

const statusTone: Record<CompanyProjectStatus, string> = {
  draft: "bg-surface-muted/50 text-foreground/60 border border-[var(--border)]",
  active: "bg-green-500/10 text-green-700 border border-green-500/20 dark:text-green-400",
  completed: "bg-burgundy/10 text-burgundy border border-burgundy/20",
  archived: "bg-foreground/5 text-foreground/40 border border-[var(--border)]",
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
      <div className="space-y-8 animate-fade-in-up">
        <section className="hero-shape shadow-glass relative overflow-hidden p-8 md:p-12">
          <div className="absolute inset-0 bg-hero-mesh opacity-100"></div>
          <div className="relative z-10 grid gap-6 md:grid-cols-3">
            <ProjectSummary label="Proiecte totale" value={projects.length} />
            <ProjectSummary label="Active" value={activeCount} />
            <ProjectSummary label="Companii" value={new Set(projects.map((project) => project.company_id)).size} />
          </div>
        </section>

        <form className="bento-card p-6 flex flex-col md:flex-row gap-4 items-center">
          <div className="w-full md:flex-1 relative">
            <svg className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-foreground/40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" /></svg>
            <input
              name="q"
              defaultValue={filters.q ?? ""}
              placeholder="Caută proiect sau companie..."
              className="w-full pl-12 pr-4 py-3 rounded-xl border border-[var(--border)] bg-surface text-sm font-bold text-foreground focus:border-burgundy/50 focus:ring-2 focus:ring-burgundy/10 transition-all shadow-inner placeholder:text-foreground/40"
            />
          </div>
          <select name="company" defaultValue={filters.company ?? ""} className="w-full md:w-auto min-h-[3rem] rounded-xl border border-[var(--border)] bg-surface px-4 text-sm font-bold text-foreground focus:border-burgundy/50 transition-all appearance-none shadow-sm cursor-pointer hover:border-burgundy/30">
            <option value="">Toate companiile</option>
            {companies.map(([id, name]) => <option key={id} value={id}>{name}</option>)}
          </select>
          <select name="status" defaultValue={filters.status ?? ""} className="w-full md:w-auto min-h-[3rem] rounded-xl border border-[var(--border)] bg-surface px-4 text-sm font-bold text-foreground focus:border-burgundy/50 transition-all appearance-none shadow-sm cursor-pointer hover:border-burgundy/30">
            <option value="">Status</option>
            <option value="active">Active</option>
            <option value="draft">În pregătire</option>
            <option value="completed">Finalizate</option>
            <option value="archived">Arhivate</option>
          </select>
          <div className="flex gap-4 w-full md:w-auto">
            <select name="type" defaultValue={filters.type ?? ""} className="w-full md:w-auto min-h-[3rem] rounded-xl border border-[var(--border)] bg-surface px-4 text-sm font-bold text-foreground focus:border-burgundy/50 transition-all appearance-none shadow-sm cursor-pointer hover:border-burgundy/30">
              <option value="">Tip proiect</option>
              {projectTypes.map((type) => <option key={type} value={type ?? ""}>{type}</option>)}
            </select>
            <button type="submit" className="tap-soft min-h-[3rem] rounded-xl bg-burgundy px-6 text-sm font-bold text-white shadow-md hover:shadow-lg transition-all whitespace-nowrap">
              Filtrează
            </button>
          </div>
        </form>

        {projects.length === 0 ? (
          <section className="flex flex-col items-center justify-center h-full min-h-[40vh] rounded-3xl border border-dashed border-[var(--border)] bg-surface/40 p-12 text-center">
            <div className="w-20 h-20 rounded-full bg-surface-muted/50 flex items-center justify-center mb-6 text-foreground/30">
              <svg className="w-10 h-10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 002-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" /></svg>
            </div>
            <p className="text-xl font-display font-bold text-foreground">Nu există proiecte încă.</p>
            <p className="mt-3 text-sm text-foreground/50 max-w-sm leading-relaxed">
              Intră într-o companie și creează primul proiect din sumarul ei pentru a începe lucrul cu participanții.
            </p>
            <Link
              href="/trainer/companies"
              className="tap-soft mt-8 inline-flex items-center justify-center rounded-full bg-burgundy px-6 py-3 text-sm font-bold text-white shadow-md hover:shadow-lg transition-all"
            >
              Deschide companii
            </Link>
          </section>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
            {filteredProjects.map((project) => (
              <Link
                key={project.id}
                href={`/trainer/projects/${project.id}`}
                className="group flex flex-col rounded-3xl border border-[var(--border)] bg-surface p-6 transition-all duration-150 hover:-translate-y-1 hover:shadow-[0_12px_32px_-12px_rgba(137,5,5,0.12)] hover:border-burgundy/20 relative overflow-hidden"
              >
                {/* Status Accent Line */}
                <div className={`absolute top-0 left-0 w-full h-1 ${
                  project.status === 'active' ? 'bg-gradient-to-r from-green-400 to-emerald-500' :
                  project.status === 'completed' ? 'bg-gradient-to-r from-burgundy/40 to-burgundy/80' :
                  project.status === 'draft' ? 'bg-gradient-to-r from-surface-muted to-[var(--border)]' :
                  'bg-foreground/10'
                }`} />

                <div className="flex-1 min-w-0 mb-6">
                  <div className="flex items-start justify-between gap-3 mb-4">
                    <span className="inline-flex items-center rounded-md bg-foreground/5 px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-foreground/70 truncate max-w-[60%]">
                      {project.company_name ?? "Companie"}
                    </span>
                    <span className={`shrink-0 rounded-full px-2.5 py-1 text-[9px] font-bold uppercase tracking-wider shadow-sm flex items-center gap-1.5 ${statusTone[project.status]}`}>
                      {project.status === "active" ? <span className="h-1.5 w-1.5 rounded-full bg-green-500 shadow-[0_0_8px_rgba(34,197,94,0.6)]" /> : null}
                      {statusLabel(project.status)}
                    </span>
                  </div>
                  <h2 className="text-xl font-display font-bold text-foreground leading-tight line-clamp-2" title={project.name}>{project.name}</h2>
                  
                  {project.description ? (
                    <p className="mt-3 line-clamp-2 text-xs font-medium leading-relaxed text-foreground/60">{project.description}</p>
                  ) : null}
                </div>
                
                <div className="mt-auto pt-5 border-t border-[var(--border)] grid grid-cols-2 gap-3">
                  <ProjectMeta label="Start" value={formatDate(project.starts_at) ?? "---"} />
                  <ProjectMeta label="Termen" value={formatDate(project.due_at) ?? "---"} />
                </div>
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
    <div className="rounded-2xl bg-surface/50-sm border border-[var(--border)] p-6 shadow-sm">
      <p className="text-[10px] font-bold uppercase tracking-wider text-foreground/50">{label}</p>
      <p className="mt-2 text-4xl font-display font-bold text-foreground">{value}</p>
    </div>
  );
}

function ProjectMeta({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-surface-muted/20 px-4 py-3 text-center transition-colors group-hover:bg-surface-muted/40 group-hover:border-burgundy/10">
      <p className="text-[9px] font-bold uppercase tracking-wider text-foreground/40">{label}</p>
      <p className="mt-1 text-[11px] font-semibold text-foreground/80">{value}</p>
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
