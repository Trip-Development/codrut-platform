import Link from "next/link";

import { getCompanyDetail } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { StatCard } from "@/components/presentation/stat-card";

export default async function CompanyOverviewPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const { companyId } = await params;
  const company = await getCompanyDetail(companyId, await getServerApiRequestOptions());

  if (!company) {
    return (
      <section className="rounded-2xl border border-[var(--border)] bg-surface p-8 text-center shadow-sm">
        <p className="text-sm text-foreground/62">Compania nu a fost gasita.</p>
      </section>
    );
  }

  const recentAssignments = company.assignments
    .filter((a) => a.submitted_at)
    .sort((a, b) => (b.submitted_at ?? "").localeCompare(a.submitted_at ?? ""))
    .slice(0, 5);

  const participantMap = new Map(company.participants.map((p) => [p.id, p.full_name]));
  const basePath = `/trainer/companies/${companyId}`;

  return (
    <>
      {company.stats.totalParticipants === 0 && (
        <div className="mb-5 rounded-2xl border border-dashed border-burgundy/30 bg-burgundy/5 p-5">
          <h3 className="text-lg font-semibold text-burgundy">Ghid configurare companie nouă</h3>
          <p className="mt-2 text-sm leading-relaxed text-foreground/70">
            Această companie este configurată în sistem, dar nu are încă participanți adăugați. Urmează acești pași pentru a lansa evaluările:
          </p>
          <div className="mt-4 grid gap-4 md:grid-cols-3">
            <div className="rounded-xl border border-[var(--border)] bg-surface p-4 transition-all hover:border-burgundy/20 hover:shadow-sm">
              <span className="text-xs font-semibold text-burgundy/70">Pasul 1</span>
              <h4 className="mt-1 font-semibold text-foreground">Încarcă rosterul</h4>
              <p className="mt-1 text-xs leading-relaxed text-foreground/56">
                Adaugă participanții prin fișierul Excel/CSV în ecranul de import pentru a asocia oameni cu această companie.
              </p>
              <Link
                href={`${basePath}/participants`}
                className="mt-3 inline-block text-xs font-semibold text-burgundy hover:text-burgundy/80"
              >
                Mergi la import roster
              </Link>
            </div>
            <div className="rounded-xl border border-[var(--border)] bg-surface p-4 transition-all hover:border-burgundy/20 hover:shadow-sm">
              <span className="text-xs font-semibold text-burgundy/70">Pasul 2</span>
              <h4 className="mt-1 font-semibold text-foreground">Configurează echipe</h4>
              <p className="mt-1 text-xs leading-relaxed text-foreground/56">
                Definește echipele de leadership sau funcționale pentru a pregăti structurile de raportare și analiză.
              </p>
              <Link
                href={`${basePath}/teams`}
                className="mt-3 inline-block text-xs font-semibold text-burgundy hover:text-burgundy/80"
              >
                Gestionează echipe
              </Link>
            </div>
            <div className="rounded-xl border border-[var(--border)] bg-surface p-4 transition-all hover:border-burgundy/20 hover:shadow-sm">
              <span className="text-xs font-semibold text-burgundy/70">Pasul 3</span>
              <h4 className="mt-1 font-semibold text-foreground">Trimite invitații</h4>
              <p className="mt-1 text-xs leading-relaxed text-foreground/56">
                După popularea rosterului, folosește catalogul de șabloane pentru a expedia invitațiile și a monitoriza livrarea.
              </p>
              <Link
                href="/trainer/email"
                className="mt-3 inline-block text-xs font-semibold text-burgundy hover:text-burgundy/80"
              >
                Gestionează emailuri
              </Link>
            </div>
          </div>
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Participanți"
          value={company.stats.totalParticipants}
          detail="Persoane înregistrate în roster."
        />
        <StatCard
          label="Asignări"
          value={company.stats.totalAssignments}
          detail="Chestionare asignate în total."
        />
        <StatCard
          label="Rata completare"
          value={company.stats.completionRate}
          suffix="%"
          detail="Proporția asignărilor finalizate."
          tone="success"
        />
        <StatCard
          label="Evaluate"
          value={company.stats.scoredCount}
          detail="Asignări cu scoring finalizat."
        />
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
        {/* Recent assignments */}
        <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
          <div className="border-b border-[var(--border)] px-5 py-4">
            <p className="text-xs font-semibold text-burgundy/75">Activitate recentă</p>
            <h2 className="mt-1 text-xl font-semibold text-foreground">Ultimele asignări</h2>
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
                {recentAssignments.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="px-5 py-6 text-center text-foreground/62">
                      Nicio asignare trimisa inca.
                    </td>
                  </tr>
                ) : (
                  recentAssignments.map((a) => (
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

        {/* Quick actions */}
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
          <p className="text-xs font-semibold text-burgundy/75">Acțiuni rapide</p>
          <div className="mt-4 space-y-3">
            <QuickLink href={`${basePath}/participants`} label="Participanți" detail="Vezi și gestionează rostere." />
            <QuickLink href={`${basePath}/org-chart`} label="Organigramă" detail="Validează ierarhia clientului." />
            <QuickLink href={`${basePath}/reports`} label="Rapoarte" detail="Asignări trimise și evaluate." />
            <QuickLink href={`${basePath}/teams`} label="Echipe" detail="Echipe de leadership și funcționale." />
          </div>
        </section>
      </div>
    </>
  );
}

function QuickLink({ href, label, detail }: { href: string; label: string; detail: string }) {
  return (
    <Link
      href={href}
      className="tap-soft block rounded-xl border border-[var(--border)] bg-background px-3 py-3 hover:border-burgundy/45"
    >
      <p className="text-sm font-semibold text-foreground">{label}</p>
      <p className="mt-1 text-xs leading-5 text-foreground/56">{detail}</p>
    </Link>
  );
}
