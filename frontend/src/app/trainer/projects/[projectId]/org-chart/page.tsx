import { getServerApiRequestOptions } from "@/api/server-request";
import { getProjectWorkspaceData } from "../project-data";
import { buildOrgChartModel } from "./org-chart-model";
import { OrgChartTree } from "./OrgChartTree";

export default async function ProjectOrgChartPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const { participants } = await getProjectWorkspaceData(projectId, await getServerApiRequestOptions());
  const orgChart = buildOrgChartModel(participants);

  return (
    <section className="surface-panel p-5">
      <p className="text-xs font-semibold text-burgundy/75">Organigramă proiect</p>
      <h2 className="mt-1 text-xl font-semibold text-foreground">Structura rosterului din proiect</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/62">
        Managerii și raportările provin din importul acestui proiect, nu din rosterul global al companiei.
      </p>

      {participants.length === 0 ? (
        <p className="mt-5 rounded-xl border border-dashed border-[var(--border)] bg-surface-muted p-5 text-sm text-foreground/58">
          Importă rosterul proiectului pentru a vedea organigrama.
        </p>
      ) : (
        <OrgChartTree model={orgChart} />
      )}
    </section>
  );
}
