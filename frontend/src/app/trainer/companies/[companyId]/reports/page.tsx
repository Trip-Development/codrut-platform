import { getCompanyAssignments, getCompanyParticipants } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";

export default async function CompanyReportsPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const { companyId } = await params;
  const requestOptions = await getServerApiRequestOptions();
  const [assignments, participants] = await Promise.all([
    getCompanyAssignments(companyId, requestOptions),
    getCompanyParticipants(companyId, requestOptions),
  ]);

  const participantMap = new Map(participants.map((p) => [p.id, p.full_name]));

  const reportableAssignments = assignments
    .filter((a) => a.status === "submitted" || a.status === "validated" || a.status === "scored")
    .sort((a, b) => (b.submitted_at ?? "").localeCompare(a.submitted_at ?? ""));

  return (
    <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
      <div className="border-b border-[var(--border)] px-5 py-4">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Rapoarte</p>
        <h2 className="mt-1 text-xl font-semibold text-foreground">Asignari finalizate</h2>
        <p className="mt-2 text-sm leading-6 text-foreground/62">
          Chestionare trimise, validate sau evaluate.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="min-w-full text-left text-sm">
          <thead className="bg-surface-muted text-xs font-semibold uppercase tracking-[0.1em] text-foreground/50">
            <tr>
              <th className="px-5 py-3">Participant</th>
              <th className="px-5 py-3">Chestionar</th>
              <th className="px-5 py-3">Status</th>
              <th className="px-5 py-3">Data</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--border)]">
            {reportableAssignments.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-5 py-6 text-center text-foreground/62">
                  Niciun raport disponibil inca.
                </td>
              </tr>
            ) : (
              reportableAssignments.map((a) => (
                <tr key={a.id} className="align-top">
                  <td className="px-5 py-4 font-semibold text-foreground">
                    {participantMap.get(a.respondent_profile_id) ?? "Necunoscut"}
                  </td>
                  <td className="px-5 py-4 text-foreground/62">{a.questionnaire_key}</td>
                  <td className="px-5 py-4">
                    <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-semibold text-foreground/60">
                      {a.status}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-foreground/62">
                    {a.submitted_at
                      ? new Date(a.submitted_at).toLocaleDateString("ro-RO")
                      : "—"}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
