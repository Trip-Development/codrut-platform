import { redirect } from "next/navigation";

import { getParticipantSession } from "@/api/auth-server";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { ParticipantContextSelector } from "../ParticipantContextSelector";
import {
  participantActiveProjectType,
  participantCanViewResults,
  participantDisplayName,
  participantHasWelcomePage,
  participantScopeParams,
  participantScopedHref,
  participantScopedNavItems,
  participantWorkspaceRequestOptions,
  PARTICIPANT_WELCOME_PATH,
  type ParticipantRouteSearchParams,
} from "../participant-context";
import { PaginaDeBunVenit } from "./PaginaDeBunVenit";
import { BUN_VENIT } from "./texte";
import { participantAccountContexts } from "../proiectele-contului";

/**
 * „Acasă" pentru omul cu 2+ proiecte — plicul 160, partea B (hotărârea lui Andrei, 27 sept).
 *
 * Omul cu un singur proiect nu are ce căuta aici: e trimis înapoi la `/participant`, cu tot ce
 * avea în adresă, și vede exact ce vedea înainte. Memoria proiectului (plicul 129) doar
 * preselectează proiectul în schimbător; nu mută omul de pe pagina asta.
 */
export default async function ParticipantWelcomePage({
  searchParams,
}: {
  searchParams: Promise<ParticipantRouteSearchParams>;
}) {
  const routeParams = await searchParams;
  const requestOptions = await getServerApiRequestOptions();
  const [participant, summary] = await Promise.all([
    getParticipantSession(),
    getParticipantWorkspaceSummary(participantWorkspaceRequestOptions(requestOptions.headers, routeParams)),
  ]);
  const contexteCont = await participantAccountContexts(requestOptions.headers, routeParams, summary.contexts);
  if (!participantHasWelcomePage(contexteCont)) {
    const inapoi = new URLSearchParams();
    for (const [cheie, valoare] of Object.entries(routeParams)) {
      for (const v of Array.isArray(valoare) ? valoare : valoare ? [valoare] : []) inapoi.append(cheie, v);
    }
    redirect(participantScopedHref("/participant", inapoi));
  }

  const scopeParams = participantScopeParams(summary);
  const projectType = participantActiveProjectType(summary);

  return (
    <AppShell
      audience="participant"
      eyebrow=""
      title={BUN_VENIT.titlu}
      description=""
      navItems={participantScopedNavItems(scopeParams, {
        projectType,
        showResults: participantCanViewResults(summary),
        contexts: contexteCont,
      })}
      activeHref={participantScopedHref(PARTICIPANT_WELCOME_PATH, scopeParams)}
      userLabel={participantDisplayName({ ...summary, contexts: contexteCont })}
      session={participant}
      sidebarTop={
        <ParticipantContextSelector
          contexts={contexteCont}
          selectedProfileId={summary.participantProfileId}
          selectedProjectId={summary.projectId}
        />
      }
    >
      <PaginaDeBunVenit contexts={contexteCont} />
    </AppShell>
  );
}
