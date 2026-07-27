import { notFound } from "next/navigation";

import { getCompanyProjectById, getProjectLifecycleEvents } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { LazyProjectSettingsForm } from "./LazyProjectSettingsForm";

export default async function ProjectSettingsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const [{ projectId }, requestOptions] = await Promise.all([
    params,
    getServerApiRequestOptions(),
  ]);
  const project = await getCompanyProjectById(projectId, requestOptions);

  if (!project) {
    notFound();
  }

  const lifecycleEvents = await getProjectLifecycleEvents(
    project.company_id,
    project.id,
    requestOptions,
  );

  return <LazyProjectSettingsForm project={project} lifecycleEvents={lifecycleEvents} />;
}
