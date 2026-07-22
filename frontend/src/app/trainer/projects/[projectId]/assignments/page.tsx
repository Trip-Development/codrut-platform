import { getServerApiRequestOptions } from "@/api/server-request";
import { LazyAssignmentWorkspace } from "@/app/trainer/companies/[companyId]/invitations/LazyInvitationsWorkspace";
import { getProjectAssignmentWorkspaceData } from "../project-data";

export default async function ProjectAssignmentsPage({
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
  const data = await getProjectAssignmentWorkspaceData(projectId, requestOptions, {
    assessmentCycleId: query.cycle,
  });

  return (
    <LazyAssignmentWorkspace
      companyId={data.project.company_id}
      companyName={data.project.company_name ?? "Companie"}
      projects={[data.project]}
      selectedProjectId={data.project.id}
      participants={data.participants}
      assignments={data.assignments}
      teams={data.teams}
      initialAssessmentCycles={data.assessmentCycles}
      initialSelectedCycleId={data.selectedAssessmentCycleId}
      showProjectSelector={false}
    />
  );
}
