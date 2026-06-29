import { notFound } from "next/navigation";

import { getAllCompanyProjects } from "@/api/companies";
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

  const basePath = `/trainer/projects/${project.id}`;

  return (
    <AppShell
      audience="trainer"
      eyebrow={project.company_name ?? "Proiect"}
      title={project.name}
      description="Spațiu de lucru pentru roster, asignări, invitații, organigramă și rezultate în acest proiect."
      navItems={trainerNavItems}
      activeHref="/trainer/projects"
    >
      <ProjectTabs basePath={basePath} />
      {children}
    </AppShell>
  );
}
