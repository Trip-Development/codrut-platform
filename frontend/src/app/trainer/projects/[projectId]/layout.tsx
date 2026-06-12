import { notFound } from "next/navigation";

import { getAllCompanyProjects, getProjectParticipants } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { ProjectTabs } from "./ProjectTabs";

export default async function ProjectLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const requestOptions = await getServerApiRequestOptions();
  const projects = await getAllCompanyProjects(requestOptions);
  const project = projects.find((item) => item.id === projectId);

  if (!project) {
    notFound();
  }

  const participants = await getProjectParticipants(project.company_id, project.id, requestOptions);
  const basePath = `/trainer/projects/${project.id}`;
  const locked = participants.length === 0;

  return (
    <AppShell
      audience="trainer"
      eyebrow={project.company_name ?? "Proiect"}
      title={project.name}
      description="Spațiu de lucru pentru roster, asignări, invitații, organigramă, echipe și rapoarte în acest proiect."
      navItems={trainerNavItems}
      activeHref="/trainer/projects"
    >
      <ProjectTabs basePath={basePath} locked={locked} />
      {locked ? (
        <section className="mb-5 rounded-2xl border border-amber-200 bg-amber-50/70 p-4 text-sm font-semibold text-amber-900">
          Proiectul nu are încă roster. Importul și setările sunt disponibile; restul instrumentelor se activează după salvarea participanților.
        </section>
      ) : null}
      {children}
    </AppShell>
  );
}
