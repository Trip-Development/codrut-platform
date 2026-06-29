import ProjectReportsPage from "../reports/page";

export default function ProjectTeamsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  return ProjectReportsPage({
    params,
    searchParams: Promise.resolve({ view: "lencioni-teams" }),
  });
}
