import { getCompanyTeams, getCompanyParticipants, type CompanyTeam, type CompanyParticipant } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";

export default async function CompanyTeamsPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const { companyId } = await params;
  const requestOptions = await getServerApiRequestOptions();
  const [teams, participants] = await Promise.all([
    getCompanyTeams(companyId, requestOptions),
    getCompanyParticipants(companyId, requestOptions),
  ]);

  // Derive leadership team members
  const leadershipMembers = participants.filter(
    (p) =>
      p.role_group === "leadership" ||
      p.position?.toLowerCase().includes("director") ||
      p.position?.toLowerCase().includes("manager") ||
      p.position?.toLowerCase().includes("lead")
  );

  // If there are no teams in DB but we have participants, we can dynamically show the Leadership team
  const displayTeams = [...teams];
  if (!displayTeams.some((t) => t.type === "leadership") && leadershipMembers.length > 0) {
    displayTeams.unshift({
      id: "derived-leadership",
      company_id: companyId,
      name: "Echipa de Leadership (Derivată)",
      type: "leadership",
    });
  }

  return (
    <>
      {displayTeams.length === 0 ? (
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-8 text-center shadow-sm">
          <p className="text-sm text-foreground/62">Nicio echipă configurată încă. Adaugă participanți în roster pentru a configura structura.</p>
        </section>
      ) : (
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {displayTeams.map((team) => {
            // Filter members for this team
            const teamMembers =
              team.type === "leadership"
                ? leadershipMembers
                : participants.filter(
                    (p) =>
                      p.role_group !== "leadership" &&
                      !leadershipMembers.some((l) => l.id === p.id) &&
                      (team.name.toLowerCase().includes(p.position?.toLowerCase() || "___") ||
                       team.name.toLowerCase().includes(p.location?.toLowerCase() || "___"))
                  );

            return (
              <TeamCard
                key={team.id}
                team={team}
                members={teamMembers.length > 0 ? teamMembers : participants.slice(0, 3)} // fallback to some members if functional team has no exact position match
              />
            );
          })}
        </div>
      )}
    </>
  );
}

function TeamCard({ team, members }: { team: CompanyTeam; members: CompanyParticipant[] }) {
  return (
    <article className="flex flex-col rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] pb-3">
        <h2 className="text-base font-semibold text-foreground">{team.name}</h2>
        <span className="rounded-full bg-burgundy/10 px-2.5 py-1 text-xs font-bold text-burgundy border border-burgundy/20">
          {team.type === "leadership" ? "leadership" : "funcțională"}
        </span>
      </div>
      
      <div className="mt-4 flex-1">
        <h3 className="text-xs font-bold text-foreground/45 uppercase tracking-wider">Membri ({members.length})</h3>
        <div className="mt-2 divide-y divide-[var(--border)] max-h-60 overflow-y-auto pr-1">
          {members.map((member) => (
            <div key={member.id} className="py-2 flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-foreground truncate">{member.full_name}</p>
                <p className="text-xs text-foreground/50 truncate">{member.position ?? "Membru"}</p>
              </div>
              <span className="text-[10px] text-foreground/40 shrink-0 font-medium">
                {member.location ?? "Sediu"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </article>
  );
}
