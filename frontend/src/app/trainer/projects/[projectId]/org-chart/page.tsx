import { notFound } from "next/navigation";

import { getCompanyProjectById, getProjectParticipants } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { buildOrgChartModel } from "./org-chart-model";
import { OrgChartTree } from "./OrgChartTree";

export default async function ProjectOrgChartPage({
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

  const participants = await getProjectParticipants(project.company_id, project.id, requestOptions);
  const orgChart = buildOrgChartModel(participants);

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-col gap-5 border-b border-border pb-5 lg:flex-row lg:items-end lg:justify-between">
        <h2 className="text-2xl font-semibold text-foreground">Organigramă</h2>
        <dl className="flex flex-wrap gap-x-8 gap-y-3">
          <OrgStat label="Participanți" value={orgChart.participantCount} />
          <OrgStat label="Rădăcini" value={orgChart.roots.length} />
          <OrgStat label="Atenționări" value={orgChart.warnings.length} warning={orgChart.warnings.length > 0} />
        </dl>
      </div>

      {participants.length === 0 ? (
        <p className="border-y border-border py-8 text-center text-sm font-medium text-muted-foreground">
          Importă rosterul proiectului pentru a vedea organigrama.
        </p>
      ) : (
        <OrgChartTree model={orgChart} />
      )}
    </section>
  );
}

function OrgStat({
  label,
  value,
  warning = false,
}: {
  label: string;
  value: number;
  warning?: boolean;
}) {
  return (
    <div className="min-w-20">
      <dt className="text-xs font-semibold text-muted-foreground">{label}</dt>
      <dd className={warning ? "mt-1 text-2xl font-semibold tabular-nums text-warning-ink" : "mt-1 text-2xl font-semibold tabular-nums text-foreground"}>{value}</dd>
    </div>
  );
}
