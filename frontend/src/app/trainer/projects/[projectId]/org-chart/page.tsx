import { notFound } from "next/navigation";

import { getCompanyProjectById, getProjectParticipants } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { Card } from "@/components/ui/card";
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
      <div className="flex flex-col gap-5 border-b border-border pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">Organigramă</h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-muted-foreground">
            Structura de raportare folosită pentru echipe și rezultatele de leadership.
          </p>
        </div>
        <Card asChild className="gap-0 p-0 shadow-none">
          <dl className="grid grid-cols-3 divide-x divide-border">
            <OrgStat label="Participanți" value={orgChart.participantCount} />
            <OrgStat label="Rădăcini" value={orgChart.roots.length} />
            <OrgStat label="Atenționări" value={orgChart.warnings.length} warning={orgChart.warnings.length > 0} />
          </dl>
        </Card>
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
    <div className="min-w-20 px-4 py-3 text-center sm:min-w-24">
      <dt className="text-xs font-semibold text-muted-foreground">{label}</dt>
      <dd className={warning ? "mt-1 text-2xl font-semibold tabular-nums text-warning-ink" : "mt-1 text-2xl font-semibold tabular-nums text-foreground"}>{value}</dd>
    </div>
  );
}
