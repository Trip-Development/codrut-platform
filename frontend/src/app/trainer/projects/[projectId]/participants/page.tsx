import { notFound } from "next/navigation";

import { getCompanyInvitationStatuses, getCompanyProjectById, getProjectParticipants } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { ProjectParticipantsWorkspace } from "./ProjectParticipantsWorkspace";

export default async function ProjectParticipantsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const requestOptions = await getServerApiRequestOptions();
  const project = await getCompanyProjectById(projectId, requestOptions);

  if (!project) {
    notFound();
  }

  const [participants, invitationStatuses] = await Promise.all([
    getProjectParticipants(project.company_id, project.id, requestOptions),
    getCompanyInvitationStatuses(project.company_id, requestOptions, { projectId: project.id }),
  ]);

  return (
    <ProjectParticipantsWorkspace
      companyId={project.company_id}
      projectId={project.id}
      companyName={project.company_name ?? "Companie"}
      project={project}
      participants={participants}
      invitationStatuses={invitationStatuses}
    />
  );
}
