import { getCompanyReportAggregate } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { adaptReportTeamLenses } from "@/app/trainer/companies/[companyId]/reports/report-aggregation";
import { EmptyState } from "@/components/presentation/empty-state";
import { getProjectReportData } from "../../project-data";
import { LencioniTeamBreakdown } from "../report-detail-sections";

export default async function ProjectLencioniReportPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const requestOptions = await getServerApiRequestOptions();
  const { project } = await getProjectReportData(projectId, requestOptions);
  const aggregate = await getCompanyReportAggregate(project.company_id, requestOptions, { projectId: project.id });
  const overviewHref = `/trainer/projects/${projectId}/reports`;

  if (aggregate.hierarchy_ambiguous) {
    return (
      <EmptyState
        title="Structura echipelor are nume ambigue."
        description={aggregate.hierarchy_ambiguity_message ?? "Există nume duplicate în relațiile de raportare."}
      />
    );
  }

  return <LencioniTeamBreakdown teams={adaptReportTeamLenses(aggregate.team_lenses)} overviewHref={overviewHref} />;
}
