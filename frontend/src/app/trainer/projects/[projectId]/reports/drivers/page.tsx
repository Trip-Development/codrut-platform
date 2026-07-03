import { getCompanyReportAggregate } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import type { ScoringResultRecord } from "@/api/trainer";
import {
  buildReportAggregation,
  findReportAggregationMismatches,
} from "@/app/trainer/companies/[companyId]/reports/report-aggregation";
import { EmptyState } from "@/components/presentation/empty-state";
import { getProjectReportData } from "../../project-data";
import { buildDriverIndividualResults, DriverDetailBreakdown } from "../page";

export default async function ProjectDriversReportPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const requestOptions = await getServerApiRequestOptions();
  const { project, participants, assignments } = await getProjectReportData(projectId, requestOptions);
  const aggregate = await getCompanyReportAggregate(project.company_id, requestOptions, { projectId: project.id });
  const resultMap = new Map(
    aggregate.results.map((result) => [result.assignment_id, result as ScoringResultRecord]),
  );
  const report = buildReportAggregation(assignments, resultMap, participants);
  const mismatches = findReportAggregationMismatches(aggregate, report);
  const overviewHref = `/trainer/projects/${projectId}/reports`;

  if (mismatches.length > 0) {
    return (
      <EmptyState
        title="Rezultatele proiectului nu sunt gata pentru afișare."
        description="Totalurile și agregatele de scor nu se aliniază între sursele disponibile."
      />
    );
  }

  if (report.hierarchyAmbiguous) {
    return (
      <EmptyState
        title="Structura echipelor are nume ambigue."
        description={report.hierarchyAmbiguityMessage ?? "Există nume duplicate în relațiile de raportare."}
      />
    );
  }

  return (
    <DriverDetailBreakdown
      teams={report.teamLenses}
      individuals={buildDriverIndividualResults(assignments, resultMap, participants)}
      overviewHref={overviewHref}
    />
  );
}
