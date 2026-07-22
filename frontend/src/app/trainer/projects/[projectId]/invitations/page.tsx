import { getServerApiRequestOptions } from "@/api/server-request";
import { LazyInvitationDeliveryWorkspace } from "@/app/trainer/companies/[companyId]/invitations/LazyInvitationsWorkspace";
import { getProjectInvitationWorkspaceData } from "../project-data";

export default async function ProjectInvitationsPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<{ cycle?: string }>;
}) {
  const [{ projectId }, query, requestOptions] = await Promise.all([
    params,
    searchParams,
    getServerApiRequestOptions(),
  ]);
  const data = await getProjectInvitationWorkspaceData(projectId, requestOptions, {
    assessmentCycleId: query.cycle,
  });

  return (
    <LazyInvitationDeliveryWorkspace
      companyId={data.project.company_id}
      companyName={data.project.company_name ?? "Companie"}
      projects={[data.project]}
      selectedProjectId={data.project.id}
      participants={data.participants}
      assignments={data.assignments}
      invitationStatuses={data.invitationStatuses}
      teams={data.teams}
      initialAssessmentCycles={data.assessmentCycles}
      initialSelectedCycleId={data.selectedAssessmentCycleId}
      showProjectSelector={false}
    />
  );
}
