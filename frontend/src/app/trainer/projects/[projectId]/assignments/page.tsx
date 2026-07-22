import { getServerApiRequestOptions } from "@/api/server-request";
import { LazyAssignmentWorkspace } from "@/app/trainer/companies/[companyId]/invitations/LazyInvitationsWorkspace";
import { getProjectAssignmentWorkspaceData } from "../project-data";

export default async function ProjectAssignmentsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const [{ projectId }, requestOptions] = await Promise.all([
    params,
    getServerApiRequestOptions(),
  ]);
  const data = await getProjectAssignmentWorkspaceData(projectId, requestOptions);

  return (
    <LazyAssignmentWorkspace
      companyId={data.project.company_id}
      companyName={data.project.company_name ?? "Companie"}
      projects={[data.project]}
      selectedProjectId={data.project.id}
      participants={data.participants}
      assignments={data.assignments}
      teams={data.teams}
      showProjectSelector={false}
    />
  );
}
