import { getCompanyReportAggregate } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { getProjectWorkspaceData } from "../project-data";

export default async function ProjectReportsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const requestOptions = await getServerApiRequestOptions();
  const { project, assignments } = await getProjectWorkspaceData(projectId, requestOptions);
  const aggregate = await getCompanyReportAggregate(project.company_id, requestOptions, { projectId: project.id });
  const pending = Math.max(aggregate.total_assigned - aggregate.total_completed, 0);
  const reportableParticipantCount = Math.max(
    aggregate.lencioni_count,
    aggregate.driver_count,
    aggregate.boss_360_count,
  );
  const canShowAggregates = reportableParticipantCount >= 3;

  return (
    <div className="space-y-5">
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <ReportMetric label="Rata completare" value={`${aggregate.completion_rate}%`} />
        <ReportMetric label="Asignări" value={aggregate.total_assigned} />
        <ReportMetric label="Răspunsuri" value={aggregate.total_completed} tone="success" />
        <ReportMetric label="În așteptare" value={pending} tone="warning" />
      </section>

      {canShowAggregates ? (
        <section className="grid gap-5 xl:grid-cols-3">
          <ReportPanel title="Lencioni" count={aggregate.lencioni_count} items={aggregate.lencioni_averages} />
          <ReportPanel title="Feedback 360 iCARE" count={aggregate.boss_360_count} items={aggregate.boss_360_averages} suffix="%" />
          <ReportPanel title="Driveri de distres" count={aggregate.driver_count} items={aggregate.driver_averages} suffix="%" />
        </section>
      ) : (
        <section className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-900 shadow-sm">
          <p className="text-sm font-semibold">
            Rezultatele agregate vor fi afișate după ce minim 3 participanți completează chestionarul (în prezent: {reportableParticipantCount})
          </p>
          <p className="mt-2 text-sm leading-6 text-amber-800/80">
            Pragul protejează confidențialitatea răspunsurilor în cohortele mici.
          </p>
        </section>
      )}

      <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
        <div className="border-b border-[var(--border)] px-5 py-4">
          <p className="text-xs font-semibold text-burgundy/75">Asignări raportabile</p>
          <h2 className="mt-1 text-xl font-semibold text-foreground">Status răspunsuri proiect</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-surface-muted text-xs font-semibold text-foreground/50">
              <tr>
                <th className="px-5 py-3">Chestionar</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Trimis</th>
                <th className="px-5 py-3">Scorat</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {assignments.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-5 py-6 text-center text-foreground/62">
                    Nu există încă asignări în proiect.
                  </td>
                </tr>
              ) : (
                assignments.map((assignment) => (
                  <tr key={assignment.id}>
                    <td className="px-5 py-4 font-semibold text-foreground">{assignment.questionnaire_key}</td>
                    <td className="px-5 py-4 text-foreground/62">{assignment.status}</td>
                    <td className="px-5 py-4 text-foreground/62">{formatDate(assignment.submitted_at)}</td>
                    <td className="px-5 py-4 text-foreground/62">{formatDate(assignment.scored_at)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

function ReportMetric({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string | number;
  tone?: "neutral" | "success" | "warning";
}) {
  const color = tone === "success" ? "text-emerald-600" : tone === "warning" ? "text-amber-600" : "text-burgundy";
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.1em] text-foreground/48">{label}</p>
      <p className={`mt-2 text-3xl font-semibold ${color}`}>{value}</p>
    </div>
  );
}

function ReportPanel({
  title,
  count,
  items,
  suffix = "",
}: {
  title: string;
  count: number;
  items: Array<{ id: string; label: string; avg: number }>;
  suffix?: string;
}) {
  return (
    <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3 border-b border-[var(--border)] pb-3">
        <h3 className="font-semibold text-foreground">{title}</h3>
        <span className="rounded-full bg-burgundy/10 px-2.5 py-1 text-xs font-bold text-burgundy">
          {count} răspunsuri
        </span>
      </div>
      {items.length === 0 ? (
        <p className="py-10 text-center text-sm text-foreground/52">Rezultatele apar după completare și scorare.</p>
      ) : (
        <div className="mt-4 space-y-3">
          {items.map((item) => (
            <div key={item.id}>
              <div className="flex justify-between text-xs font-semibold text-foreground/68">
                <span>{item.label}</span>
                <span>
                  {item.avg}
                  {suffix}
                </span>
              </div>
              <div className="mt-1.5 h-2 rounded-full bg-surface-muted">
                <div
                  className="h-full rounded-full bg-burgundy"
                  style={{ width: `${Math.min(Math.max(item.avg, 0), 100)}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString("ro-RO");
}
