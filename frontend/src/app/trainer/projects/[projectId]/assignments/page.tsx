import { getServerApiRequestOptions } from "@/api/server-request";
import { InvitationsWorkspace } from "@/app/trainer/companies/[companyId]/invitations/InvitationsWorkspace";
import { getProjectWorkspaceData } from "../project-data";

export default async function ProjectAssignmentsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const data = await getProjectWorkspaceData(projectId, await getServerApiRequestOptions());

  return (
    <InvitationsWorkspace
      companyId={data.project.company_id}
      companyName={data.project.company_name ?? "Companie"}
      projects={data.companyProjects}
      selectedProjectId={data.project.id}
      participants={data.participants}
      assignments={data.assignments}
      invitationStatuses={data.invitationStatuses}
      teams={data.teams}
    />
  );
}
