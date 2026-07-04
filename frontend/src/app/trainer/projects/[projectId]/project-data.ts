import { notFound } from "next/navigation";

import {
  getCompanyAssignments,
  getCompanyInvitationStatuses,
  getCompanyProjectById,
  getCompanyProjects,
  getCompanyTeams,
  getProjectParticipants,
} from "@/api/companies";
import type { ApiRequestOptions } from "@/api/companies";

export async function getProjectWorkspaceData(
  projectId: string,
  requestOptions: ApiRequestOptions,
) {
  const project = await getCompanyProjectById(projectId, requestOptions);

  if (!project) {
    notFound();
  }

  const [companyProjects, participants, assignments, invitationStatuses, teams] = await Promise.all([
    getCompanyProjects(project.company_id, requestOptions),
    getProjectParticipants(project.company_id, project.id, requestOptions),
    getCompanyAssignments(project.company_id, requestOptions, { projectId: project.id }),
    getCompanyInvitationStatuses(project.company_id, requestOptions, { projectId: project.id }),
    getCompanyTeams(project.company_id, requestOptions),
  ]);

  return {
    project,
    companyProjects,
    participants,
    assignments,
    invitationStatuses,
    teams,
  };
}

export async function getProjectReportData(
  projectId: string,
  requestOptions: ApiRequestOptions,
) {
  const project = await getCompanyProjectById(projectId, requestOptions);

  if (!project) {
    notFound();
  }

  const [participants, assignments] = await Promise.all([
    getProjectParticipants(project.company_id, project.id, requestOptions),
    getCompanyAssignments(project.company_id, requestOptions, { projectId: project.id }),
  ]);

  return {
    project,
    participants,
    assignments,
  };
}
