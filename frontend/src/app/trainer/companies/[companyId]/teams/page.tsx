import { getCompanyTeams, type CompanyTeam } from "@/api/companies";

export default async function CompanyTeamsPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const { companyId } = await params;
  const teams = await getCompanyTeams(companyId);

  return (
    <>
      {teams.length === 0 ? (
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-8 text-center shadow-sm">
          <p className="text-sm text-foreground/62">Nicio echipa configurata inca.</p>
        </section>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {teams.map((team) => (
            <TeamCard key={team.id} team={team} />
          ))}
        </div>
      )}
    </>
  );
}

function TeamCard({ team }: { team: CompanyTeam }) {
  return (
    <article className="flex flex-col rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-base font-semibold text-foreground">{team.name}</h2>
        <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-semibold text-foreground/55">
          {team.type}
        </span>
      </div>
      <p className="mt-3 text-sm text-foreground/62">Membri echipa</p>
    </article>
  );
}
