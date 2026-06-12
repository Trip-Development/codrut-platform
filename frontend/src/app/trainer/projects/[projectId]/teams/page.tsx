import { getServerApiRequestOptions } from "@/api/server-request";
import { normalizeReportsToName } from "@/api/roster-format";
import type { CompanyParticipant } from "@/api/companies";
import { getProjectWorkspaceData } from "../project-data";

export default async function ProjectTeamsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const { participants } = await getProjectWorkspaceData(projectId, await getServerApiRequestOptions());
  const teams = buildProjectTeams(participants);

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
        <p className="text-xs font-semibold text-burgundy/75">Echipe proiect</p>
        <h2 className="mt-1 text-xl font-semibold text-foreground">Leadership și echipe manageriale</h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/62">
          Echipele sunt detectate automat din managerii și subalternii importați în acest proiect.
        </p>
      </section>

      {teams.length === 0 ? (
        <section className="rounded-2xl border border-dashed border-[var(--border)] bg-surface/70 p-6 text-sm text-foreground/58">
          Nu există încă suficiente date de raportare pentru echipe.
        </section>
      ) : (
        <section className="grid gap-4 lg:grid-cols-2">
          {teams.map((team) => (
            <article key={team.name} className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs font-semibold text-burgundy/75">{team.type}</p>
                  <h3 className="mt-1 text-lg font-semibold text-foreground">{team.name}</h3>
                </div>
                <span className="rounded-full bg-surface-muted px-3 py-1 text-xs font-bold text-foreground/58">
                  {team.members.length} membri
                </span>
              </div>
              <div className="mt-4 space-y-2">
                {team.members.map((member) => (
                  <div key={member.id} className="rounded-xl border border-[var(--border)] bg-background px-3 py-2">
                    <p className="text-sm font-semibold text-foreground">{member.full_name}</p>
                    <p className="mt-1 text-xs text-foreground/50">{member.position ?? "Rol necompletat"}</p>
                  </div>
                ))}
              </div>
            </article>
          ))}
        </section>
      )}
    </div>
  );
}

function buildProjectTeams(participants: CompanyParticipant[]) {
  const participantByName = new Map(
    participants.map((participant) => [participant.full_name.trim().toLowerCase(), participant]),
  );
  const directReports = new Map<string, CompanyParticipant[]>();
  const topLevel: CompanyParticipant[] = [];

  for (const participant of participants) {
    const managerName = normalizeReportsToName(participant.reports_to_name);
    const manager = managerName ? participantByName.get(managerName.toLowerCase()) : null;
    if (!manager) {
      topLevel.push(participant);
      continue;
    }
    const current = directReports.get(manager.id) ?? [];
    current.push(participant);
    directReports.set(manager.id, current);
  }

  const teams: Array<{ name: string; type: string; members: CompanyParticipant[] }> = [];
  if (topLevel.length > 1) {
    teams.push({ name: "Leadership", type: "Echipă leadership", members: topLevel });
  }
  for (const [managerId, reports] of directReports) {
    const manager = participants.find((participant) => participant.id === managerId);
    if (!manager || reports.length === 0) continue;
    teams.push({
      name: `Echipa ${manager.full_name}`,
      type: "Echipă manager",
      members: [manager, ...reports],
    });
  }
  return teams;
}
