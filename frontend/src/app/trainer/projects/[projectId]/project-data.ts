import { notFound } from "next/navigation";

import {
  getCompanyAssignments,
  getCompanyInvitationStatuses,
  getCompanyProjectById,
  getCompanyReportAggregate,
  getCompanyTeams,
  getProjectParticipants,
} from "@/api/companies";
import type { ApiRequestOptions } from "@/api/companies";

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
) {
  const project = await getRequiredProject(projectId, requestOptions);

  const [participants, assignments, teams] = await Promise.all([
    getProjectParticipants(project.company_id, project.id, requestOptions),
    getCompanyAssignments(project.company_id, requestOptions, { projectId: project.id }),
    getCompanyTeams(project.company_id, requestOptions),
  ]);

  return {
    project,
    participants,
    assignments,
    teams,
  };
}

export async function getProjectInvitationWorkspaceData(
  projectId: string,
  requestOptions: ApiRequestOptions,
) {
  const project = await getRequiredProject(projectId, requestOptions);

  const [participants, assignments, invitationStatuses, teams] = await Promise.all([
    getProjectParticipants(project.company_id, project.id, requestOptions),
    getCompanyAssignments(project.company_id, requestOptions, { projectId: project.id }),
    getCompanyInvitationStatuses(project.company_id, requestOptions, { projectId: project.id }),
    getCompanyTeams(project.company_id, requestOptions),
  ]);

  return {
    project,
    participants,
    assignments,
    invitationStatuses,
    teams,
  };
}

export async function getProjectReportAggregateData(
  projectId: string,
  requestOptions: ApiRequestOptions,
) {
  const project = await getRequiredProject(projectId, requestOptions);

  const aggregate = await getCompanyReportAggregate(
    project.company_id,
    requestOptions,
    { projectId: project.id },
  );

  return {
    project,
    aggregate,
  };
}

export async function getProjectReportWorkspaceData(
  projectId: string,
  requestOptions: ApiRequestOptions,
) {
  const project = await getRequiredProject(projectId, requestOptions);

  const [participants, assignments, aggregate] = await Promise.all([
    getProjectParticipants(project.company_id, project.id, requestOptions),
    getCompanyAssignments(project.company_id, requestOptions, { projectId: project.id }),
    getCompanyReportAggregate(project.company_id, requestOptions, { projectId: project.id }),
  ]);

  return {
    project,
    participants,
    assignments,
    aggregate,
  };
}
