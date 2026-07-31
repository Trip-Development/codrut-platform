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

export async function getProjectReportHistoryData(
  projectId: string,
  requestOptions: ApiRequestOptions,
  requestedCycleId?: string | null,
) {
  const project = await getRequiredProject(projectId, requestOptions);
  const [participants, assessmentCycles] = await Promise.all([
    getProjectParticipants(project.company_id, project.id, requestOptions),
    getAssessmentCycles(project.company_id, project.id, requestOptions),
  ]);
  const reportCycles = [...assessmentCycles]
    .filter((cycle) => cycle.status !== "draft")
    .sort((left, right) => left.sequence - right.sequence);
  const selectedCycle = reportCycles.find((cycle) => cycle.id === requestedCycleId) ?? null;
  const reportScopes = selectedCycle
    ? [selectedCycle]
    : reportCycles.length > 0
      ? reportCycles
      : [null];
  const aggregates = await Promise.all(
    reportScopes.map((cycle) =>
      getCompanyReportAggregate(project.company_id, requestOptions, {
        projectId: project.id,
        assessmentCycleId: cycle?.id,
      }),
    ),
  );

  return {
    project,
    participants,
    assessmentCycles,
    cycleReports: aggregates.map((aggregate, index) => ({
      cycle: reportScopes[index],
      aggregate,
    })),
  };
}
