import Link from "next/link";
import { notFound } from "next/navigation";

import {
  getCompanyProjectById,
  getCompanyTeamMemberships,
  getCompanyTeams,
  getProjectParticipants,
} from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { Badge } from "@/components/ui/badge";
import { buildProjectTeamRows } from "./project-team-model";

export default async function ProjectTeamsPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const [{ projectId }, requestOptions] = await Promise.all([
    params,
    getServerApiRequestOptions(),
  ]);
  const project = await getCompanyProjectById(projectId, requestOptions);

  if (!project) {
    notFound();
  }

  const [participants, teams] = await Promise.all([
    getProjectParticipants(project.company_id, project.id, requestOptions),
    getCompanyTeams(project.company_id, requestOptions),
  ]);
  const membershipEntries = await Promise.all(
    teams.map(async (team) => [
      team.id,
      await getCompanyTeamMemberships(project.company_id, team.id, requestOptions),
    ] as const),
  );
  const rows = buildProjectTeamRows(
    teams,
    Object.fromEntries(membershipEntries),
    participants,
  );
  const includedMemberCount = rows.reduce((total, row) => total + row.members.length, 0);

  return (
    <section className="flex flex-col gap-6">
      <div className="flex flex-col gap-5 border-b border-border pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-foreground">Echipe proiect</h2>
          <dl className="mt-4 flex flex-wrap gap-x-8 gap-y-3">
            <ProjectTeamSummary label="Echipe" value={rows.length} />
            <ProjectTeamSummary label="Membri în proiect" value={includedMemberCount} />
            <ProjectTeamSummary label="Participanți" value={participants.length} />
          </dl>
        </div>
        <Link
          href={`/trainer/companies/${project.company_id}/teams`}
          className="inline-flex h-9 w-fit items-center rounded-md border border-border bg-surface px-3 text-sm font-semibold text-foreground transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45"
        >
          Gestionează echipele
        </Link>
      </div>

      {rows.length === 0 ? (
        <div className="border-y border-border py-10 text-center">
          <h3 className="text-base font-semibold text-foreground">Nu există echipe salvate.</h3>
          <Link
            href={`/trainer/companies/${project.company_id}/teams`}
            className="mt-3 inline-flex text-sm font-semibold text-primary underline-offset-4 hover:underline"
          >
            Creează o echipă
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {rows.map((row) => (
            <article key={row.team.id} className="overflow-hidden rounded-lg border border-border bg-surface">
              <header className="flex items-start justify-between gap-4 border-b border-border px-4 py-3">
                <div className="min-w-0">
                  <h3 className="truncate text-base font-semibold text-foreground">{row.team.name}</h3>
                  <p className="mt-1 text-sm text-muted-foreground">
                    {row.members.length} {row.members.length === 1 ? "membru în proiect" : "membri în proiect"}
                  </p>
                </div>
                <Badge variant={row.team.type === "leadership" ? "default" : "outline"}>
                  {row.team.type === "leadership" ? "Leadership" : "Funcțională"}
                </Badge>
              </header>

              {row.members.length === 0 ? (
                <p className="px-4 py-8 text-center text-sm text-muted-foreground">Niciun membru al echipei nu este în acest proiect.</p>
              ) : (
                <ul className="max-h-72 divide-y divide-border overflow-y-auto">
                  {row.members.map(({ membership, participant }) => (
                    <li key={membership.id} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 px-4 py-3">
                      <span className="min-w-0">
                        <span className="block truncate text-sm font-semibold text-foreground">{participant.full_name}</span>
                        <span className="mt-0.5 block truncate text-xs text-muted-foreground">{participant.position ?? "Rol necompletat"}</span>
                      </span>
                      <Badge variant={membership.role === "leader" ? "secondary" : "outline"}>
                        {membership.role === "leader" ? "Lider" : "Membru"}
                      </Badge>
                    </li>
                  ))}
                </ul>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function ProjectTeamSummary({ label, value }: { label: string; value: number }) {
  return (
    <div className="min-w-24">
      <dt className="text-xs font-semibold text-muted-foreground">{label}</dt>
      <dd className="mt-1 text-2xl font-semibold tabular-nums text-foreground">{value}</dd>
    </div>
  );
}
