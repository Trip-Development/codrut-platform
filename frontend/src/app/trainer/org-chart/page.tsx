import { getTrainerOperationsSummary, type TrainerRosterMember } from "@/api/trainer";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";

export default async function TrainerOrgChartPage() {
  const summary = await getTrainerOperationsSummary();
  const rootMembers = summary.roster.filter((member) => !member.reportsTo);

  return (
    <AppShell
      audience="trainer"
      eyebrow="Organigrama"
      title="Harta ierarhiei clientului"
      description="Validare vizuala pentru coloanele Name, Reports To, Position, Location, email si Profil PCM optional."
      navItems={trainerNavItems}
      activeHref="/trainer/org-chart"
    >
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Org chart</p>
          <div className="mt-5 space-y-4">
            {rootMembers.map((member) => (
              <OrgNode key={member.id} member={member} members={summary.roster} depth={0} />
            ))}
          </div>
        </section>

        <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Validari roster</p>
          <div className="mt-4 space-y-3">
            {summary.validations.map((validation) => (
              <article key={validation.label} className="rounded-xl border border-[var(--border)] bg-background px-3 py-3">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="text-sm font-semibold text-foreground">{validation.label}</h2>
                  <span className="rounded-full bg-surface-muted px-2 py-1 text-xs font-semibold text-foreground/55">
                    {validation.severity}
                  </span>
                </div>
                <p className="mt-1 text-xs leading-5 text-foreground/56">{validation.detail}</p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}

function OrgNode({
  member,
  members,
  depth,
}: {
  member: TrainerRosterMember;
  members: TrainerRosterMember[];
  depth: number;
}) {
  const reports = members.filter((candidate) => candidate.reportsTo === member.name);

  return (
    <div className={depth > 0 ? "ml-5 border-l border-[var(--border)] pl-4" : ""}>
      <article className="rounded-xl border border-[var(--border)] bg-background px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-semibold text-foreground">{member.name}</h2>
            <p className="mt-1 text-xs font-semibold text-burgundy">{member.position}</p>
          </div>
          <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-semibold text-foreground/55">
            {member.role}
          </span>
        </div>
        <p className="mt-2 text-xs leading-5 text-foreground/55">
          {member.location} · {member.email}
          {member.pcmProfile ? ` · PCM ${member.pcmProfile}` : ""}
        </p>
      </article>
      {reports.length > 0 ? (
        <div className="mt-3 space-y-3">
          {reports.map((report) => (
            <OrgNode key={report.id} member={report} members={members} depth={depth + 1} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
