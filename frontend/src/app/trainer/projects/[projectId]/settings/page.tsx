import { getServerApiRequestOptions } from "@/api/server-request";
import { getProjectWorkspaceData } from "../project-data";
import { ProjectSettingsForm } from "./ProjectSettingsForm";

export default async function ProjectSettingsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const { project } = await getProjectWorkspaceData(projectId, await getServerApiRequestOptions());

  return <ProjectSettingsForm project={project} />;
}
