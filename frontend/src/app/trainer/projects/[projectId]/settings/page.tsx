import { notFound } from "next/navigation";

import { getCompanyProjectById } from "@/api/companies";
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

  return <LazyProjectSettingsForm project={project} />;
}
