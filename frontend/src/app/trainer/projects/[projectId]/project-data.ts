import { notFound } from "next/navigation";

import {
  getAssessmentCycles,
  getCompanyAssignments,
  getCompanyInvitationStatuses,
  getCompanyProjectById,
  getCompanyReportAggregate,
  getCompanyTeams,
  getProjectParticipants,
} from "@/api/companies";
import type { ApiRequestOptions, ProjectScopeOptions } from "@/api/companies";
import type { AssessmentCycle } from "@/api/companies";

export function resolveProjectAssessmentCycle(
  cycles: AssessmentCycle[],
  requestedCycleId?: string | null,
): AssessmentCycle | null {
  return cycles.find((cycle) => cycle.id === requestedCycleId)
    ?? [...cycles].reverse().find((cycle) => cycle.status !== "closed")
    ?? cycles.at(-1)
    ?? null;
}

async function getRequiredProject(
  projectId: string,
  requestOptions: ApiRequestOptions,
) {
  const project = await getCompanyProjectById(projectId, requestOptions);

  if (!project) {
    notFound();
  }

  return project;
}

export async function getProjectAssignmentWorkspaceData(
  projectId: string,
  requestOptions: ApiRequestOptions,
  scope: ProjectScopeOptions = {},
) {
  const project = await getRequiredProject(projectId, requestOptions);
  const [participants, teams, assessmentCycles] = await Promise.all([
    getProjectParticipants(project.company_id, project.id, requestOptions),
    getCompanyTeams(project.company_id, requestOptions),
    getAssessmentCycles(project.company_id, project.id, requestOptions),
  ]);
  const selectedCycle = resolveProjectAssessmentCycle(
    assessmentCycles,
    scope.assessmentCycleId,
  );
  const assignments = await getCompanyAssignments(project.company_id, requestOptions, {
    projectId: project.id,
    assessmentCycleId: selectedCycle?.id,
  });

  return {
    project,
    participants,
    assignments,
    teams,
    assessmentCycles,
    selectedAssessmentCycleId: selectedCycle?.id ?? null,
  };
}

export async function getProjectInvitationWorkspaceData(
  projectId: string,
  requestOptions: ApiRequestOptions,
  scope: ProjectScopeOptions = {},
) {
  const project = await getRequiredProject(projectId, requestOptions);
  const [participants, teams, assessmentCycles] = await Promise.all([
    getProjectParticipants(project.company_id, project.id, requestOptions),
    getCompanyTeams(project.company_id, requestOptions),
    getAssessmentCycles(project.company_id, project.id, requestOptions),
  ]);
  const selectedCycle = resolveProjectAssessmentCycle(
    assessmentCycles,
    scope.assessmentCycleId,
  );
  const [assignments, invitationStatuses] = await Promise.all([
    getCompanyAssignments(project.company_id, requestOptions, {
      projectId: project.id,
      assessmentCycleId: selectedCycle?.id,
    }),
    getCompanyInvitationStatuses(project.company_id, requestOptions, {
      projectId: project.id,
      assessmentCycleId: selectedCycle?.id,
    }),
  ]);

  return {
    project,
    participants,
    assignments,
    invitationStatuses,
    teams,
    assessmentCycles,
    selectedAssessmentCycleId: selectedCycle?.id ?? null,
  };
}

export async function getProjectReportAggregateData(
  projectId: string,
  requestOptions: ApiRequestOptions,
  scope: ProjectScopeOptions = {},
) {
  const project = await getRequiredProject(projectId, requestOptions);

  const aggregate = await getCompanyReportAggregate(
    project.company_id,
    requestOptions,
    {
      projectId: project.id,
      assessmentCycleId: scope.assessmentCycleId,
    },
  );

  const assessmentCycles = await getAssessmentCycles(
    project.company_id,
    project.id,
    requestOptions,
  );

  return {
    project,
    aggregate,
    assessmentCycles,
  };
}

export async function getProjectAssessmentCyclesData(
  projectId: string,
  requestOptions: ApiRequestOptions,
) {
  const project = await getRequiredProject(projectId, requestOptions);
  const assessmentCycles = await getAssessmentCycles(
    project.company_id,
    project.id,
    requestOptions,
  );
  return { project, assessmentCycles };
}

export async function getProjectReportWorkspaceData(
  projectId: string,
  requestOptions: ApiRequestOptions,
  scope: ProjectScopeOptions = {},
) {
  const project = await getRequiredProject(projectId, requestOptions);

  const [participants, assignments, aggregate, assessmentCycles] = await Promise.all([
    getProjectParticipants(project.company_id, project.id, requestOptions),
    getCompanyAssignments(project.company_id, requestOptions, {
      projectId: project.id,
      assessmentCycleId: scope.assessmentCycleId,
    }),
    getCompanyReportAggregate(project.company_id, requestOptions, {
      projectId: project.id,
      assessmentCycleId: scope.assessmentCycleId,
    }),
    getAssessmentCycles(project.company_id, project.id, requestOptions),
  ]);

  return {
    project,
    participants,
    assignments,
    aggregate,
    assessmentCycles,
  };
}
