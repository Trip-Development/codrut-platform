import { notFound } from "next/navigation";

import {
  getAllCompanyProjects,
  getCompanyAssignments,
  getCompanyInvitationStatuses,
  getCompanyTeams,
  getProjectParticipants,
} from "@/api/companies";
import type { ApiRequestOptions } from "@/api/companies";

export async function getProjectWorkspaceData(
  projectId: string,
  requestOptions: ApiRequestOptions,
) {
  const projects = await getAllCompanyProjects(requestOptions);
  const project = projects.find((item) => item.id === projectId);

  if (!project) {
    notFound();
  }

  const companyProjects = projects.filter((item) => item.company_id === project.company_id);
  const [participants, assignments, invitationStatuses, teams] = await Promise.all([
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
