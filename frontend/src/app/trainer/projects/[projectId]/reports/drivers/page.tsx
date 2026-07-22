import { getServerApiRequestOptions } from "@/api/server-request";
import type { ScoringResultRecord } from "@/api/trainer";
import { adaptReportTeamLenses } from "@/app/trainer/companies/[companyId]/reports/report-aggregation";
import { EmptyState } from "@/components/presentation/empty-state";
import { getProjectReportWorkspaceData } from "../../project-data";
import { buildDriverIndividualResults, DriverDetailBreakdown } from "../report-detail-sections";
import { buildProjectReportQuery, type ProjectReportSearchParams } from "../report-cycle";

export default async function ProjectDriversReportPage({
  params,
  searchParams,
}: {
  params: Promise<{ projectId: string }>;
  searchParams: Promise<ProjectReportSearchParams>;
}) {
  const [{ projectId }, query, requestOptions] = await Promise.all([
    params,
    searchParams,
    getServerApiRequestOptions(),
  ]);
  const { participants, assignments, aggregate } = await getProjectReportWorkspaceData(
    projectId,
    requestOptions,
    { assessmentCycleId: query.cycle },
  );
  const resultMap = new Map(
    aggregate.results.map((result) => [result.assignment_id, result as ScoringResultRecord]),
  );
  const overviewHref = `/trainer/projects/${projectId}/reports${buildProjectReportQuery(query)}`;

  if (aggregate.hierarchy_ambiguous) {
    return (
      <EmptyState
        title="Structura echipelor are nume ambigue."
        description={aggregate.hierarchy_ambiguity_message ?? "Există nume duplicate în relațiile de raportare."}
      />
    );
  }

  return (
    <DriverDetailBreakdown
      teams={adaptReportTeamLenses(aggregate.team_lenses)}
      individuals={buildDriverIndividualResults(assignments, resultMap, participants)}
      overviewHref={overviewHref}
    />
  );
}
