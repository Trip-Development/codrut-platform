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
  // Trainingul are calea lui si de trimitere, nu doar de afisare: ruta obisnuita
  // cere o asignare de chestionar, pe care un proiect de training n-o are.
  const project = await getCompanyProjectById(projectId, requestOptions);
  if (project?.project_type === "training") {
    const rows = await getTrainingInvitations(projectId, requestOptions);
    return <TrainingInvitations projectId={projectId} rows={rows} />;
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
