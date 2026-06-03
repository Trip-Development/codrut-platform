import { getTrainerOperationsSummary } from "@/api/trainer";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";

export default async function TrainerParticipantsPage() {
  const summary = await getTrainerOperationsSummary();

  return (
    <AppShell
      audience="trainer"
      eyebrow="Participanti"
      title="Roster si conturi"
      description="Suprafata pentru import, verificare profil PCM optional, invitatii si asociere cu compania corecta."
      navItems={trainerNavItems}
      activeHref="/trainer/participants"
    >
      <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
        <div className="border-b border-[var(--border)] px-5 py-4">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Roster import</p>
          <h2 className="mt-1 text-xl font-semibold text-foreground">Participanti si status acces</h2>
          <p className="mt-2 text-sm leading-6 text-foreground/62">
            Coloane asteptate: Name, Reports To, Position, Location, email, Profil PCM. PCM poate lipsi.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-surface-muted text-xs font-semibold uppercase tracking-[0.1em] text-foreground/50">
              <tr>
                <th className="px-5 py-3">Nume</th>
                <th className="px-5 py-3">Reports To</th>
                <th className="px-5 py-3">Pozitie</th>
                <th className="px-5 py-3">Locatie</th>
                <th className="px-5 py-3">PCM</th>
                <th className="px-5 py-3">Acces</th>
                <th className="px-5 py-3">Completare</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border)]">
              {summary.roster.map((member) => (
                <tr key={member.id} className="align-top">
                  <td className="px-5 py-4">
                    <p className="font-semibold text-foreground">{member.name}</p>
                    <p className="mt-1 text-xs text-foreground/50">{member.email}</p>
                  </td>
                  <td className="px-5 py-4 text-foreground/62">{member.reportsTo ?? "Radacina"}</td>
                  <td className="px-5 py-4 text-foreground/62">{member.position}</td>
                  <td className="px-5 py-4 text-foreground/62">{member.location}</td>
                  <td className="px-5 py-4 text-foreground/62">{member.pcmProfile ?? "Necompletat"}</td>
                  <td className="px-5 py-4">
                    <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-semibold text-foreground/60">
                      {member.inviteStatus}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-2">
                      <div className="h-2 w-24 overflow-hidden rounded-full bg-surface-muted">
                        <div className="h-full rounded-full bg-burgundy" style={{ width: `${member.completion}%` }} />
                      </div>
                      <span className="text-xs font-semibold text-foreground/60">{member.completion}%</span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  );
}
