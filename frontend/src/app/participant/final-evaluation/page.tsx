import Link from "next/link";

import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { serverLinkButtonClassName } from "@/components/ui/server-link-button";
import { ParticipantContextSelector } from "../ParticipantContextSelector";
import {
  participantActiveHref,
  participantScopeParams,
  participantScopedHref,
  participantScopedNavItems,
  participantWorkspaceRequestOptions,
  type ParticipantRouteSearchParams,
} from "../participant-context";

export default async function ParticipantFinalEvaluationPage({
  searchParams,
}: {
  searchParams: Promise<ParticipantRouteSearchParams>;
}) {
  const routeParams = await searchParams;
  const requestOptions = await getServerApiRequestOptions();
  const summary = await getParticipantWorkspaceSummary(
    participantWorkspaceRequestOptions(requestOptions.headers, routeParams),
  );
  const scopeParams = participantScopeParams(summary);
  const questionnairesHref = participantScopedHref("/participant/questionnaires", scopeParams);
  const resultsHref = participantScopedHref("/participant/results", scopeParams);
  const completed = summary.tasks.filter((task) => task.status === "completed").length;
  const total = summary.tasks.length;
  const openTasks = summary.tasks.filter((task) => task.status !== "completed");
  const hasOpenTasks = openTasks.length > 0;

  return (
    <AppShell
      audience="participant"
      eyebrow=""
      title={hasOpenTasks ? "Mai ai sarcini de completat" : "Ai finalizat partea ta"}
      description=""
      navItems={participantScopedNavItems(scopeParams)}
      activeHref={participantActiveHref("/participant", scopeParams)}
      userLabel={summary.participantFullName.split(/\s+/)[0] || "Participant"}
    >
      <ParticipantContextSelector
        contexts={summary.contexts}
        selectedProfileId={summary.participantProfileId}
        selectedProjectId={summary.projectId}
      />
      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_17rem] lg:gap-12">
        <section>
          {hasOpenTasks ? (
            <>
              <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-4">
                <h2 className="text-xl font-semibold text-foreground">Sarcini rămase</h2>
                <Link href={questionnairesHref} className={serverLinkButtonClassName()}>Continuă</Link>
              </div>
              <div className="divide-y divide-border">
                {openTasks.map((task) => (
                  <div key={task.id} className="grid gap-2 py-4 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
                    <div className="min-w-0">
                      <p className="text-base font-semibold text-foreground">{task.title}</p>
                      <p className="mt-1 text-sm text-muted-foreground">{task.targetLabel}</p>
                    </div>
                    <span className="text-sm font-semibold text-burgundy">{task.estimatedMinutes} min</span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div className="border-y border-border py-8">
              <h2 className="text-xl font-semibold text-foreground">Răspunsurile au fost trimise</h2>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">Rezultatele apar după procesarea chestionarelor eligibile.</p>
              <Link href={resultsHref} className={serverLinkButtonClassName({ className: "mt-5" })}>Vezi rezultatele</Link>
            </div>
          )}
        </section>

        <aside className="border-t border-border pt-6 lg:border-l lg:border-t-0 lg:pl-8 lg:pt-0">
          <p className="text-sm font-semibold text-foreground">Progres</p>
          <p className="mt-3 font-mono text-5xl font-semibold tabular-nums text-burgundy">{completed}/{total}</p>
          <p className="mt-2 text-sm text-muted-foreground">{hasOpenTasks ? `${openTasks.length} rămase` : "Complet"}</p>
          <p className="mt-7 border-t border-border pt-5 text-sm leading-6 text-muted-foreground">Răspunsurile individuale nu sunt afișate participanților.</p>
        </aside>
      </div>
    </AppShell>
  );
}
