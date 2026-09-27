import { redirect } from "next/navigation";

import { getParticipantSession } from "@/api/auth-server";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { ParticipantContextSelector } from "../ParticipantContextSelector";
import {
  participantActiveProjectType,
  participantCanViewResults,
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
  if (!participantHasWelcomePage(summary.contexts)) {
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
        contexts: summary.contexts,
      })}
      activeHref={participantScopedHref(PARTICIPANT_WELCOME_PATH, scopeParams)}
      session={participant}
      sidebarTop={
        <ParticipantContextSelector
          contexts={summary.contexts}
          selectedProfileId={summary.participantProfileId}
          selectedProjectId={summary.projectId}
        />
      }
    >
      <PaginaDeBunVenit contexts={summary.contexts} />
    </AppShell>
  );
}
