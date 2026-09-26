import { AppShell } from "@/components/shell/app-shell";
import { getParticipantSession } from "@/api/auth-server";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { PracticeParticipantDashboard } from "../dashboard/PracticeParticipantDashboard";
import {
  participantActiveHref,
  participantActiveProjectType,
  participantScopeParams,
  participantScopedNavItems,
  participantWorkspaceRequestOptions,
  type ParticipantRouteSearchParams,
} from "../participant-context";
import { TRAINING_PROJECT_TYPE } from "@/components/shell/nav";

/**
 * Tabloul, pe proiectul ALES de om — plicul 143.
 *
 * Până la 143 pagina nu citea deloc contextul: tabloul se cerea fără proiect, deci serverul nu
 * avea de unde să știe competențele alese de trainer și arăta lista fixă din aplicația veche.
 * Acum proiectul vine din același loc ca la ecranul de exersare (rezumatul spațiului omului).
 */
export default async function TablouParticipantPage({
  searchParams,
}: {
  searchParams?: Promise<ParticipantRouteSearchParams>;
}) {
  const routeParams = (await searchParams) ?? {};
  const requestOptions = await getServerApiRequestOptions();
  const [participant, summary] = await Promise.all([
    getParticipantSession(),
    getParticipantWorkspaceSummary(
      participantWorkspaceRequestOptions(requestOptions.headers, routeParams),
    ).catch(() => null),
  ]);
  const participantFirstName =
    participant?.user?.name?.split(/\s+/)[0] || "Participant";
  const scopeParams = summary ? participantScopeParams(summary) : new URLSearchParams();
  const projectType =
    (summary ? participantActiveProjectType(summary) : null) ?? TRAINING_PROJECT_TYPE;

  return (
    <AppShell
      audience="participant"
      eyebrow="Antrenament & Competențe"
      title={`Tabloul tău, ${participantFirstName}`}
      description="Evoluția deprinderilor dobândite în simulările de conversație cu Cody."
      navItems={participantScopedNavItems(scopeParams, { projectType })}
      activeHref={participantActiveHref("/participant/tablou", scopeParams)}
      userLabel={participantFirstName}
      session={participant}
    >
      <div className="max-w-5xl mx-auto w-full">
        <PracticeParticipantDashboard projectId={summary?.projectId ?? null} />
      </div>
    </AppShell>
  );
}
