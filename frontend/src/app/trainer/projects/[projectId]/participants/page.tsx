import { notFound } from "next/navigation";

import { getAllCompanyProjects, getCompanyInvitationStatuses, getProjectParticipants } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { RosterImporter } from "@/components/roster-importer";
import { ProjectParticipantsWorkspace } from "./ProjectParticipantsWorkspace";

export default async function ProjectParticipantsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const requestOptions = await getServerApiRequestOptions();
  const projects = await getAllCompanyProjects(requestOptions);
  const project = projects.find((item) => item.id === projectId);

  if (!project) {
    notFound();
  }

  const [participants, invitationStatuses] = await Promise.all([
    getProjectParticipants(project.company_id, project.id, requestOptions),
    getCompanyInvitationStatuses(project.company_id, requestOptions, { projectId: project.id }),
  ]);

  return (
    <div className="space-y-5">
      <RosterImporter
        companies={[{ id: project.company_id, name: project.company_name ?? "Companie" }]}
        defaultCompanyId={project.company_id}
        existingParticipants={participants}
        projects={[project]}
        defaultProjectId={project.id}
        requireProject
        lockCompany
      />

      <ProjectParticipantsWorkspace
        companyId={project.company_id}
        projectId={project.id}
        participants={participants}
        invitationStatuses={invitationStatuses}
      />
    </div>
  );
}
