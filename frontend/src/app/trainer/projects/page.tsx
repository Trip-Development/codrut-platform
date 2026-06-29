import { getAllCompanyProjects } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { ProjectsWorkspace } from "./ProjectsWorkspace";

export default async function TrainerProjectsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; company?: string; status?: string; type?: string }>;
}) {
  const filters = await searchParams;
  const projects = await getAllCompanyProjects(await getServerApiRequestOptions());
  const activeCount = projects.filter((project) => project.status === "active").length;
  const companies = Array.from(
    new Map(projects.map((project) => [project.company_id, project.company_name ?? "Companie"])).entries(),
  ).sort((first, second) => first[1].localeCompare(second[1]));
  const projectTypes = Array.from(
    new Set(projects.map((project) => project.project_type).filter((type): type is string => Boolean(type))),
  ).sort();

  return (
    <AppShell
      audience="trainer"
      eyebrow="Proiecte"
      title="Proiecte pe companii"
      description="O privire rapidă peste proiectele active, în pregătire și finalizate pentru fiecare client."
      navItems={trainerNavItems}
      activeHref="/trainer/projects"
    >
      <div className="space-y-8">
        <section className="surface-panel p-5 md:p-6">
          <div className="grid gap-4 md:grid-cols-3">
            <ProjectSummary label="Proiecte totale" value={projects.length} />
            <ProjectSummary label="Active" value={activeCount} />
            <ProjectSummary label="Companii" value={new Set(projects.map((project) => project.company_id)).size} />
          </div>
        </section>

        <ProjectsWorkspace
          projects={projects}
          initialFilters={filters}
          companies={companies}
          projectTypes={projectTypes}
        />
      </div>
    </AppShell>
  );
}

function ProjectSummary({ label, value }: { label: string; value: number }) {
  return (
    <div className="surface-panel p-5">
      <p className="text-[10px] font-bold uppercase tracking-wider text-foreground/50">{label}</p>
      <p className="mt-2 text-4xl font-display font-bold text-foreground">{value}</p>
    </div>
  );
}
