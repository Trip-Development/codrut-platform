import { getCompanyDetail } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { RosterImporter } from "@/app/trainer/roster/roster-importer";

export default async function CompanyParticipantsPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const { companyId } = await params;
  const company = await getCompanyDetail(companyId, await getServerApiRequestOptions());
  const participants = company?.participants ?? [];
  const companyName = company?.name ?? "Compania curentă";

  return (
    <div className="space-y-5">
      <RosterImporter companies={[{ id: companyId, name: companyName }]} defaultCompanyId={companyId} lockCompany />

      <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
        <div className="border-b border-[var(--border)] px-5 py-4">
          <p className="text-xs font-semibold text-burgundy/75">Roster</p>
          <h2 className="mt-1 text-xl font-semibold text-foreground">Persoane și status acces</h2>
          <p className="mt-2 text-sm leading-6 text-foreground/62">
            Coloane: nume, manager, poziție, locație, PCM, email.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-surface-muted text-xs font-semibold text-foreground/50">
              <tr>
                <th className="px-5 py-3">Nume</th>
                <th className="px-5 py-3">Manager</th>
                <th className="px-5 py-3">Poziție</th>
                <th className="px-5 py-3">Locație</th>
                <th className="px-5 py-3">PCM</th>
                <th className="px-5 py-3">Email</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {participants.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-5 py-6 text-center text-foreground/62">
                    Nicio persoană importată încă.
                  </td>
                </tr>
              ) : (
                participants.map((member) => (
                  <tr key={member.id} className="align-top transition-colors hover:bg-surface-muted/40">
                    <td className="px-5 py-4">
                      <p className="font-semibold text-foreground">{member.full_name}</p>
                    </td>
                    <td className="px-5 py-4 text-foreground/62">{member.reports_to_name ?? "—"}</td>
                    <td className="px-5 py-4 text-foreground/62">{member.position ?? "—"}</td>
                    <td className="px-5 py-4 text-foreground/62">{member.location ?? "—"}</td>
                    <td className="px-5 py-4 text-foreground/62">{member.pcm_profile ?? "Necompletat"}</td>
                    <td className="px-5 py-4 text-foreground/62">{member.email}</td>
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
