import { notFound } from "next/navigation";

import { getCompanyProjectById, getProjectLifecycleEvents } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { LazyProjectSettingsForm } from "./LazyProjectSettingsForm";
import { PracticeSetupSection } from "./PracticeSetupSection";

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

  return (
    <div className="flex flex-col gap-5">
      <LazyProjectSettingsForm project={project} lifecycleEvents={lifecycleEvents} />
      {project.project_type === "training" ? (
        <PracticeSetupSection projectId={project.id} />
      ) : null}
    </div>
  );
}
