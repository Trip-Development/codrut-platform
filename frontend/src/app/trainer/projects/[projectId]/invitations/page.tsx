import { getCompanyProjectById } from "@/api/companies";
import { getTrainingInvitations } from "@/api/practice";
import { getServerApiRequestOptions } from "@/api/server-request";
import { LazyInvitationDeliveryWorkspace } from "@/app/trainer/companies/[companyId]/invitations/LazyInvitationsWorkspace";
import { getProjectInvitationWorkspaceData } from "../project-data";
import { TrainingInvitations } from "./TrainingInvitations";

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
  // La un proiect de training nu exista niciun ciclu de evaluare, iar formularul
  // de coaching e construit in jurul lor — de aceea cere ceva ce n-are de unde lua.
  // Forma de training foloseste ACELASI mecanism de invitatie, fara ciclu.
  const project = await getCompanyProjectById(projectId, requestOptions);
  if (project?.project_type === "training") {
    const rows = await getTrainingInvitations(projectId, requestOptions);
    return (
      <TrainingInvitations
        companyId={project.company_id}
        projectId={projectId}
        rows={rows}
      />
    );
  }

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
