import Link from "next/link";

import { getCompanyDetail } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { StatCard } from "@/components/presentation/stat-card";
import { CompanyProjectsPanel } from "./CompanyProjectsPanel";

export default async function CompanyOverviewPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const { companyId } = await params;
  const company = await getCompanyDetail(companyId, await getServerApiRequestOptions());

  if (!company) {
    return (
      <section className="rounded-2xl border border-dashed border-[var(--border)] bg-surface/70 p-8 text-center">
        <p className="text-base font-semibold text-foreground">Compania nu a fost găsită.</p>
      </section>
    );
  }

  const recentAssignments = company.assignments
    .filter((a) => a.submitted_at)
    .sort((a, b) => (b.submitted_at ?? "").localeCompare(a.submitted_at ?? ""))
    .slice(0, 5);

  const participantMap = new Map(company.participants.map((p) => [p.id, p.full_name]));
  const projectMap = new Map(company.projects.map((project) => [project.id, project.name]));
  const basePath = `/trainer/companies/${companyId}`;

  return (
    <>
      {company.stats.totalParticipants === 0 && (
        <section className="mb-5 rounded-2xl border border-burgundy/20 bg-burgundy/5 p-5 shadow-sm">
          <h3 className="text-lg font-semibold text-burgundy">Configurează compania</h3>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/68">
            Clientul există deja. Următorul pas este să adaugi lista de participanți, apoi echipele și invitațiile.
          </p>
          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <SetupStep
              step="1"
              title="Încarcă participanții"
              detail="Adaugă oamenii prin Excel sau CSV și leagă-i de companie."
              href={`${basePath}/participants`}
              action="Import participanți"
            />
            <SetupStep
              step="2"
              title="Configurează echipe"
              detail="Grupează participanții în echipe de leadership sau funcționale."
              href={`${basePath}/teams`}
              action="Gestionează echipe"
            />
            <SetupStep
              step="3"
              title="Trimite invitații"
              detail="Expediază invitațiile și urmărește livrarea."
              href={`${basePath}/invitations`}
              action="Deschide invitații"
            />
          </div>
        </section>
      )}
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Participanți"
          value={company.stats.totalParticipants}
          detail="Persoane active în companie."
        />
        <StatCard
          label="Proiecte"
          value={company.projects.length}
          detail="Inițiative salvate pentru companie."
        />
        <StatCard
          label="Asignări"
          value={company.stats.totalAssignments}
          detail="Total pe proiecte și asignări istorice fără proiect."
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

      <div className="mt-5">
        <CompanyProjectsPanel
          companyId={companyId}
          initialProjects={company.projects}
          assignments={company.assignments}
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
                  <th className="px-5 py-3">Proiect</th>
                  <th className="px-5 py-3">Chestionar</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Data</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--border)]">
                {recentAssignments.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-5 py-6 text-center text-foreground/62">
                      Nicio asignare trimisă încă.
                    </td>
                  </tr>
                ) : (
                  recentAssignments.map((a) => (
                    <tr key={a.id} className="align-top">
                      <td className="px-5 py-4 font-semibold text-foreground">
                        {participantMap.get(a.respondent_profile_id) ?? "Necunoscut"}
                      </td>
                      <td className="px-5 py-4 text-foreground/62">
                        {a.project_id ? projectMap.get(a.project_id) ?? "Proiect necunoscut" : "Fără proiect"}
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
            <QuickLink href={`${basePath}/participants`} label="Participanți" detail="Import, verificare și acces participanți." />
            <QuickLink href={`${basePath}/org-chart`} label="Organigramă" detail="Validează ierarhia clientului." />
            <QuickLink href={`${basePath}/teams`} label="Echipe" detail="Echipe de leadership și funcționale." />
            <QuickLink href={`${basePath}/reports`} label="Rapoarte" detail="Asignări trimise și evaluate." />
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
      className="tap-soft block rounded-xl border border-[var(--border)] bg-background px-3 py-3 hover:border-burgundy/45 hover:bg-surface-muted/55"
    >
      <p className="text-sm font-semibold text-foreground">{label}</p>
      <p className="mt-1 text-xs leading-5 text-foreground/56">{detail}</p>
    </Link>
  );
}

function SetupStep({
  step,
  title,
  detail,
  href,
  action,
}: {
  step: string;
  title: string;
  detail: string;
  href: string;
  action: string;
}) {
  return (
    <Link
      href={href}
      className="tap-soft group rounded-xl border border-[var(--border)] bg-surface p-4 hover:-translate-y-0.5 hover:border-burgundy/30 hover:shadow-sm"
    >
      <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-burgundy/10 text-xs font-bold text-burgundy">
        {step}
      </span>
      <h4 className="mt-3 font-semibold text-foreground">{title}</h4>
      <p className="mt-1 text-xs leading-5 text-foreground/56">{detail}</p>
      <p className="mt-3 text-xs font-semibold text-burgundy group-hover:text-burgundy-700">{action}</p>
    </Link>
  );
}
