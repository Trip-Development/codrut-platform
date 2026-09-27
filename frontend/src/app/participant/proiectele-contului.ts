import {
  getParticipantWorkspaceSummary,
  type ParticipantWorkspaceContext,
} from "@/api/participants";
import { firstValue, type ParticipantRouteSearchParams } from "./participant-context";

/**
 * Proiectele omului, pe TOT contul — plicul 162.
 *
 * Cu `?profile=` în adresă, sumarul serverului se restrânge la profilul acela. La omul cu profiluri
 * în mai multe firme, pagina de bun venit număra atunci 1 proiect și îl trimitea înapoi, „Acasă” nu
 * mai ducea la bun venit, iar schimbătorul arăta numai proiectele acelui profil.
 *
 * Numai atunci se mai cere o dată sumarul, fără profil, proiect sau ciclu — deci o cerere în plus
 * pe pagină, și numai cu `?profile=` în adresă. Fără el, sumarul paginii e deja al întregului cont.
 * Omul cu un singur profil (cei 19 de la Michelin) primește aceeași listă ca înainte.
 * Dacă cererea în plus nu merge, rămâne lista paginii — adică purtarea de dinainte.
 */
export async function participantAccountContexts(
  headers: HeadersInit | undefined,
  routeParams: ParticipantRouteSearchParams,
  contexts: ParticipantWorkspaceContext[] | null | undefined,
): Promise<ParticipantWorkspaceContext[]> {
  const dinPagina = contexts ?? [];
  if (!firstValue(routeParams.profile)) return dinPagina;
  try {
    const cont = await getParticipantWorkspaceSummary({ headers });
    return cont.contexts?.length ? cont.contexts : dinPagina;
  } catch {
    return dinPagina;
  }
}
