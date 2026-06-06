import { getCompanyParticipants, type CompanyParticipant } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";

type OrgValidationError = {
  type: "self" | "invalid_manager" | "cycle" | "orphan";
  message: string;
  participant: CompanyParticipant;
};

function analyzeHierarchy(participants: CompanyParticipant[]) {
  const nameToParticipant = new Map(
    participants.map((p) => [p.full_name.trim().toLowerCase(), p])
  );

  const errors: OrgValidationError[] = [];
  const cycleParticipantIds = new Set<string>();

  // 1. Detect self-reports and invalid managers
  participants.forEach((p) => {
    if (!p.reports_to_name) return;
    const reportsTo = p.reports_to_name.trim().toLowerCase();
    const selfName = p.full_name.trim().toLowerCase();

    if (reportsTo === selfName) {
      errors.push({
        type: "self",
        message: `Participantul "${p.full_name}" se raportează la el însuși (auto-raportare).`,
        participant: p,
      });
    } else {
      const manager = nameToParticipant.get(reportsTo);
      if (!manager) {
        errors.push({
          type: "invalid_manager",
          message: `Managerul "${p.reports_to_name}" specificat pentru "${p.full_name}" nu există în listă.`,
          participant: p,
        });
      }
    }
  });

  // 2. Cycle detection using DFS
  const visited = new Set<string>();
  const recStack = new Set<string>();
  const path: CompanyParticipant[] = [];

  function dfs(p: CompanyParticipant) {
    visited.add(p.id);
    recStack.add(p.id);
    path.push(p);

    if (p.reports_to_name) {
      const mgr = nameToParticipant.get(p.reports_to_name.trim().toLowerCase());
      if (mgr) {
        if (recStack.has(mgr.id)) {
          const cycleStartIdx = path.findIndex((x) => x.id === mgr.id);
          const cycle = path.slice(cycleStartIdx);
          
          errors.push({
            type: "cycle",
            message: `Ciclu detectat: ${cycle.map((c) => c.full_name).join(" -> ")} -> ${mgr.full_name}`,
            participant: p,
          });

          cycle.forEach((cNode) => cycleParticipantIds.add(cNode.id));
        } else if (!visited.has(mgr.id)) {
          dfs(mgr);
        }
      }
    }

    recStack.delete(p.id);
    path.pop();
  }

  participants.forEach((p) => {
    if (!visited.has(p.id)) {
      dfs(p);
    }
  });

  // 3. Traversal to find rendered nodes
  const rootMembers = participants.filter((p) => {
    if (!p.reports_to_name) return true;
    const mgr = nameToParticipant.get(p.reports_to_name.trim().toLowerCase());
    return !mgr; // treat invalid managers as root for rendering
  });

  const renderedIds = new Set<string>();

  function traverse(member: CompanyParticipant, currentVisited: Set<string>) {
    renderedIds.add(member.id);
    const reports = participants.filter(
      (c) =>
        c.reports_to_name?.trim().toLowerCase() ===
        member.full_name.trim().toLowerCase()
    );
    reports.forEach((child) => {
      if (!currentVisited.has(child.id)) {
        const nextVisited = new Set(currentVisited);
        nextVisited.add(child.id);
        traverse(child, nextVisited);
      }
    });
  }

  rootMembers.forEach((r) => traverse(r, new Set([r.id])));

  // All participants not in renderedIds are orphans
  const orphans = participants.filter((p) => !renderedIds.has(p.id));

  // Determine orphan roots to render them as pseudo-roots
  const orphanRoots = orphans.filter((o) => {
    if (!o.reports_to_name) return true;
    const mgr = nameToParticipant.get(o.reports_to_name.trim().toLowerCase());
    return !mgr || !orphans.some((other) => other.id === mgr.id);
  });

  // Filter out duplicate errors
  const uniqueErrors: OrgValidationError[] = [];
  const errorKeys = new Set<string>();
  errors.forEach((err) => {
    const key = `${err.type}-${err.participant.id}`;
    if (!errorKeys.has(key)) {
      errorKeys.add(key);
      uniqueErrors.push(err);
    }
  });

  // Add orphan warning if they aren't already flagged in a cycle or self-reports
  orphans.forEach((o) => {
    if (
      !cycleParticipantIds.has(o.id) &&
      !uniqueErrors.some((e) => e.participant.id === o.id && e.type === "self")
    ) {
      uniqueErrors.push({
        type: "orphan",
        message: `Participantul "${o.full_name}" nu este conectat la ierarhia principală (posibil din cauza unui ciclu).`,
        participant: o,
      });
    }
  });

  return {
    errors: uniqueErrors,
    displayRoots: [...rootMembers, ...orphanRoots],
    cycleParticipantIds,
  };
}

export default async function CompanyOrgChartPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const { companyId } = await params;
  const participants = await getCompanyParticipants(companyId, await getServerApiRequestOptions());
  
  const { errors, displayRoots, cycleParticipantIds } = analyzeHierarchy(participants);

  const criticalErrors = errors.filter((e) => e.type === "cycle" || e.type === "self");
  const warnings = errors.filter((e) => e.type === "invalid_manager" || e.type === "orphan");

  return (
    <div className="space-y-6">
      {/* Validation Warnings/Errors Panel */}
      {errors.length > 0 && (
        <div className="space-y-4">
          {criticalErrors.length > 0 && (
            <div className="rounded-2xl border border-red-200 bg-red-50/50 p-5 shadow-sm space-y-3">
              <div className="flex items-center gap-2 text-red-800">
                <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <h3 className="text-sm font-bold uppercase tracking-wider">Erori Critice de Structură ({criticalErrors.length})</h3>
              </div>
              <p className="text-xs text-red-700">
                Următoarele probleme blochează generarea corectă a organigramei. Corectați managerul în fișierul de roster și re-importați:
              </p>
              <div className="max-h-36 overflow-y-auto space-y-2 pr-1">
                {criticalErrors.map((err, i) => (
                  <div key={i} className="text-xs font-semibold text-red-700 bg-red-100/40 rounded-lg px-3 py-2 border border-red-200/50">
                    · {err.message}
                  </div>
                ))}
              </div>
            </div>
          )}

          {warnings.length > 0 && (
            <div className="rounded-2xl border border-amber-200 bg-amber-50/50 p-5 shadow-sm space-y-3">
              <div className="flex items-center gap-2 text-amber-800">
                <svg className="w-5 h-5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <h3 className="text-sm font-bold uppercase tracking-wider">Atenționări de Structură ({warnings.length})</h3>
              </div>
              <p className="text-xs text-amber-700">
                Următoarele probleme nu blochează afișarea, dar indică manageri neidentificați sau noduri izolate:
              </p>
              <div className="max-h-36 overflow-y-auto space-y-2 pr-1">
                {warnings.map((err, i) => (
                  <div key={i} className="text-xs font-semibold text-amber-700 bg-amber-100/40 rounded-lg px-3 py-2 border border-amber-200/50">
                    · {err.message}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Main Org Chart */}
      <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-burgundy/75">Organigrama Ierarhică</p>

        {participants.length === 0 ? (
          <p className="mt-4 text-sm text-foreground/62">Niciun participant importat încă.</p>
        ) : (
          <div className="mt-5 space-y-6 overflow-x-auto pb-4">
            {displayRoots.map((member) => (
              <OrgNode
                key={member.id}
                member={member}
                members={participants}
                depth={0}
                visitedIds={new Set([member.id])}
                cycleParticipantIds={cycleParticipantIds}
              />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function OrgNode({
  member,
  members,
  depth,
  visitedIds,
  cycleParticipantIds,
}: {
  member: CompanyParticipant;
  members: CompanyParticipant[];
  depth: number;
  visitedIds: Set<string>;
  cycleParticipantIds: Set<string>;
}) {
  const reports = members.filter(
    (c) => c.reports_to_name?.trim().toLowerCase() === member.full_name.trim().toLowerCase()
  );

  const hasSelfReport = member.reports_to_name?.trim().toLowerCase() === member.full_name.trim().toLowerCase();
  const hasInvalidManager =
    member.reports_to_name &&
    !members.some((m) => m.full_name.trim().toLowerCase() === member.reports_to_name?.trim().toLowerCase());
  const isInCycle = cycleParticipantIds.has(member.id);

  // Border/background styles based on status
  let cardStyles = "border-[var(--border)] bg-background";
  let labelBadge = null;

  if (hasSelfReport) {
    cardStyles = "border-red-300 bg-red-50/20";
    labelBadge = (
      <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-bold text-red-700 border border-red-200">
        Auto-raportare
      </span>
    );
  } else if (isInCycle) {
    cardStyles = "border-red-300 bg-red-50/20";
    labelBadge = (
      <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-bold text-red-700 border border-red-200">
        Circuit Închis (Ciclu)
      </span>
    );
  } else if (hasInvalidManager) {
    cardStyles = "border-amber-300 bg-amber-50/20";
    labelBadge = (
      <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-bold text-amber-700 border border-amber-200">
        Manager inexistent: {member.reports_to_name}
      </span>
    );
  }

  return (
    <div className={depth > 0 ? "ml-6 border-l border-[var(--border)] pl-5 mt-4" : "mt-6 first:mt-0"}>
      <article className={`rounded-xl border p-4 shadow-sm transition-all hover:shadow-md ${cardStyles}`}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h2 className="text-sm font-bold text-foreground truncate">{member.full_name}</h2>
              {labelBadge}
            </div>
            <p className="mt-1 text-xs font-bold text-burgundy">{member.position ?? "Fără poziție specificată"}</p>
          </div>
          {member.role_group ? (
            <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-semibold text-foreground/55 border border-[var(--border)]">
              {member.role_group}
            </span>
          ) : null}
        </div>
        <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-foreground/55 border-t border-[var(--border)]/40 pt-2">
          <span>{member.location ?? "Fără locație"}</span>
          <span>•</span>
          <span className="truncate">{member.email}</span>
          {member.pcm_profile ? (
            <>
              <span>•</span>
              <span className="font-semibold text-burgundy/80">PCM: {member.pcm_profile}</span>
            </>
          ) : null}
        </div>
      </article>

      {reports.length > 0 ? (
        <div className="space-y-1">
          {reports.map((report) => {
            const isVisited = visitedIds.has(report.id);
            if (isVisited) {
              return (
                <div key={report.id} className="ml-6 border-l border-red-300 pl-5 mt-4">
                  <article className="rounded-xl border border-red-200 bg-red-50/50 p-3 text-xs font-semibold text-red-700">
                    Recursivitate oprită: {report.full_name} se raportează în cerc înapoi la {member.full_name}.
                  </article>
                </div>
              );
            }
            
            const nextVisited = new Set(visitedIds);
            nextVisited.add(report.id);

            return (
              <OrgNode
                key={report.id}
                member={report}
                members={members}
                depth={depth + 1}
                visitedIds={nextVisited}
                cycleParticipantIds={cycleParticipantIds}
              />
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
