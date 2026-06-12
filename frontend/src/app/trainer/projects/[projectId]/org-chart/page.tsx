import { getServerApiRequestOptions } from "@/api/server-request";
import { normalizeReportsToName } from "@/api/roster-format";
import type { CompanyParticipant } from "@/api/companies";
import { getProjectWorkspaceData } from "../project-data";

export default async function ProjectOrgChartPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const { projectId } = await params;
  const { participants } = await getProjectWorkspaceData(projectId, await getServerApiRequestOptions());
  const nameMap = new Map(participants.map((participant) => [participant.full_name.trim().toLowerCase(), participant]));
  const roots = participants.filter((participant) => {
    const managerName = normalizeReportsToName(participant.reports_to_name);
    return !managerName || !nameMap.has(managerName.toLowerCase());
  });

  return (
    <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <p className="text-xs font-semibold text-burgundy/75">Organigramă proiect</p>
      <h2 className="mt-1 text-xl font-semibold text-foreground">Structura rosterului din proiect</h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/62">
        Managerii și raportările provin din importul acestui proiect, nu din rosterul global al companiei.
      </p>

      {participants.length === 0 ? (
        <p className="mt-5 rounded-xl border border-dashed border-[var(--border)] bg-background/70 p-5 text-sm text-foreground/58">
          Importă rosterul proiectului pentru a vedea organigrama.
        </p>
      ) : (
        <div className="mt-5 space-y-3 overflow-x-auto">
          {roots.map((participant) => (
            <OrgNode
              key={participant.id}
              participant={participant}
              participants={participants}
              depth={0}
              visitedIds={new Set([participant.id])}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function OrgNode({
  participant,
  participants,
  depth,
  visitedIds,
}: {
  participant: CompanyParticipant;
  participants: CompanyParticipant[];
  depth: number;
  visitedIds: Set<string>;
}) {
  const children = participants.filter((child) => {
    const managerName = normalizeReportsToName(child.reports_to_name);
    return managerName.toLowerCase() === participant.full_name.trim().toLowerCase();
  });

  return (
    <div style={{ marginLeft: `${depth * 1.5}rem` }}>
      <div className="rounded-xl border border-[var(--border)] bg-background px-4 py-3">
        <p className="font-semibold text-foreground">{participant.full_name}</p>
        <p className="mt-1 text-xs font-semibold text-foreground/48">
          {participant.position ?? "Rol necompletat"} · {participant.location ?? "Locație necompletată"}
        </p>
      </div>
      {children.length > 0 ? (
        <div className="mt-2 space-y-2 border-l border-[var(--border)] pl-3">
          {children.map((child) => {
            if (visitedIds.has(child.id)) return null;
            const nextVisited = new Set(visitedIds);
            nextVisited.add(child.id);
            return (
              <OrgNode
                key={child.id}
                participant={child}
                participants={participants}
                depth={depth + 1}
                visitedIds={nextVisited}
              />
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
