import { getTrainerSession } from "@/api/auth-server";
import { getAllCompanyProjects } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { LazyProjectsWorkspace } from "./LazyProjectsWorkspace";

export default async function TrainerProjectsPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string; company?: string; status?: string; type?: string }>;
}) {
  const projectsPromise = getServerApiRequestOptions().then((requestOptions) =>
    getAllCompanyProjects(requestOptions),
  );
  const [filters, projects, trainer] = await Promise.all([
    searchParams,
    projectsPromise,
    getTrainerSession(),
  ]);
  const companies = Array.from(
    new Map(projects.map((project) => [project.company_id, project.company_name ?? "Companie"])).entries(),
  ).sort((first, second) => first[1].localeCompare(second[1]));
  const projectTypes = Array.from(
    new Set(projects.map((project) => project.project_type).filter((type): type is string => Boolean(type))),
  ).sort();

  return (
    <AppShell
      audience="trainer"
      eyebrow=""
      title="Proiecte"
      description=""
      navItems={trainerNavItems}
      activeHref="/trainer/projects"
      userLabel={trainer.user.name}
      session={trainer}
    >
      <LazyProjectsWorkspace
        projects={projects}
        initialFilters={filters}
        companies={companies}
        projectTypes={projectTypes}
      />
    </AppShell>
  );
}
