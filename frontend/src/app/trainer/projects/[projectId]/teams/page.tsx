import { redirect } from "next/navigation";

export default async function ProjectTeamsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  redirect(`/trainer/projects/${projectId}/reports/lencioni`);
}
