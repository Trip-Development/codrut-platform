import type {
  ParticipantWorkspaceContext,
  ParticipantWorkspaceSummary,
} from "@/api/participants";
import {
  participantNavItemsForType,
  TRAINING_PROJECT_TYPE,
  type ShellNavItem,
} from "@/components/shell/nav";

export type ParticipantRouteSearchParams = {
  profile?: string | string[];
  project?: string | string[];
  cycle?: string | string[];
  baseline?: string | string[];
  compare?: string | string[];
};

export function participantWorkspaceRequestOptions(
  headers: HeadersInit | undefined,
  searchParams: ParticipantRouteSearchParams,
) {
  return {
    headers,
    participantProfileId: firstValue(searchParams.profile),
    projectId: firstValue(searchParams.project),
    cycleId: firstValue(searchParams.cycle),
  };
}

export function participantScopeParams(
  summary: Pick<ParticipantWorkspaceSummary, "participantProfileId" | "projectId" | "assessmentCycleId">,
): URLSearchParams {
  const params = new URLSearchParams();
  if (summary.participantProfileId) params.set("profile", summary.participantProfileId);
  if (summary.projectId) params.set("project", summary.projectId);
  if (summary.assessmentCycleId) params.set("cycle", summary.assessmentCycleId);
  return params;
}

export function participantScopedHref(pathname: string, params: URLSearchParams): string {
  const query = params.toString();
  return query ? `${pathname}?${query}` : pathname;
}

export function participantResultsHref(params: URLSearchParams): string {
  const comparisonParams = new URLSearchParams(params);
  comparisonParams.delete("cycle");
  comparisonParams.delete("baseline");
  comparisonParams.delete("compare");
  return participantScopedHref("/participant/results", comparisonParams);
}

export function participantCanViewResults(summary: {
  showParticipantResults?: boolean;
  projectId?: string | null;
  projects?: Array<{ id: string; showParticipantResults?: boolean }>;
  contexts?: Array<{ projects?: Array<{ id: string; showParticipantResults?: boolean }> }>;
}): boolean {
  const allProjects = [
    ...(summary.projects ?? []),
    ...(summary.contexts ?? []).flatMap((c) => c.projects ?? []),
  ];
  if (allProjects.length > 0) {
    if (summary.projectId) {
      const target = allProjects.find((p) => p.id === summary.projectId);
      if (target?.showParticipantResults !== undefined) {
        return Boolean(target.showParticipantResults);
      }
    } else {
      return allProjects.some((p) => p.showParticipantResults);
    }
  }
  if (summary.showParticipantResults !== undefined) {
    return Boolean(summary.showParticipantResults);
  }
  return false;
}

/**
 * Meniul participantului, din DOUĂ reguli care nu se calcă una pe alta — plicul 131.
 *
 * - `projectType` alege LISTA: un proiect de training primește meniul de exersare
 *   (plicul 113, ramura lui Cody).
 * - `showResults` scoate „Rezultate" din lista aleasă, DACĂ lista îl are — când trainerul n-a
 *   publicat rezultatele (partea chatului Aplicației).
 *
 * Meniul de training n-are „Rezultate", deci a doua regulă n-are ce scoate acolo. Pentru orice
 * alt proiect, lista e cea de dinainte și regula rezultatelor lucrează exact ca înainte.
 * Niciuna dintre purtări nu s-a schimbat; s-au pus doar amândouă în aceeași funcție.
 */
export function participantScopedNavItems(
  params: URLSearchParams,
  {
    projectType,
    showResults = true,
  }: { projectType?: string | null; showResults?: boolean } = {},
): ShellNavItem[] {
  const lista = participantNavItemsForType(projectType);
  const items = showResults
    ? lista
    : lista.filter((item) => item.href !== "/participant/results");
  return items.map((item) => ({
    ...item,
    href: item.href === "/participant/results"
      ? participantResultsHref(params)
      : participantScopedHref(item.href, params),
  }));
}

export function participantActiveHref(pathname: string, params: URLSearchParams): string {
  return pathname === "/participant/results"
    ? participantResultsHref(params)
    : participantScopedHref(pathname, params);
}

export function firstValue(value: string | string[] | undefined): string | undefined {
  return Array.isArray(value) ? value[0] : value;
}

export function participantDefaultContext(contexts: ParticipantWorkspaceContext[]) {
  const candidates = contexts.flatMap((context) => context.projects.map((project) => {
    const orderedCycles = [...(project.cycles ?? [])].sort((left, right) => right.sequence - left.sequence);
    const cycle = orderedCycles.find((item) => item.status === "active") ?? orderedCycles[0];
    const recency = Date.parse(
      cycle?.dueAt
      ?? cycle?.closedAt
      ?? project.deadlineAt
      ?? cycle?.startsAt
      ?? "",
    );
    return {
      participantProfileId: context.participantProfileId,
      projectId: project.id,
      cycleId: cycle?.id,
      current: project.historyBucket !== "history",
      recency: Number.isNaN(recency) ? 0 : recency,
    };
  }));
  return candidates.sort((left, right) => (
    Number(right.current) - Number(left.current)
    || right.recency - left.recency
  ))[0] ?? null;
}

type ProiectDinSumar = {
  id: string;
  projectType?: string | null;
  status?: string | null;
  historyBucket?: string | null;
};

/**
 * Tipul proiectului în care se află acum participantul, din sumarul lui.
 *
 * `summary.projects` e construită din structurile de coaching — cicluri și
 * chestionare. Un proiect de training n-are așa ceva, deci lista aia rămâne
 * **goală** chiar dacă proiectul există. Până la plicul 34 funcția întorcea `null`,
 * iar `participantNavItemsForType(null)` dădea meniul de coaching: omul de la
 * training vedea „Chestionare" și „Rezultate" pe pagina de exersare.
 *
 * Proiectul e totuși acolo, complet, în `summary.contexts[].projects`. Când lista
 * de sus e goală, se caută acolo — întâi după `projectId`, altfel primul proiect
 * curent. Nimic nu se schimbă pe server și nimic nu se atinge la coaching, unde
 * `summary.projects` e plină și prima ramură răspunde ca înainte.
 */
export function participantActiveProjectType(
  summary: {
    projectId?: string | null;
    projects?: ProiectDinSumar[];
    contexts?: { projects?: ProiectDinSumar[] }[];
  },
): string | null {
  const alege = (proiecte: ProiectDinSumar[]): ProiectDinSumar | undefined => {
    if (proiecte.length === 0) return undefined;
    const dupaId = summary.projectId
      ? proiecte.find((p) => p.id === summary.projectId)
      : undefined;
    if (dupaId) return dupaId;
    return proiecte.find((p) => p.historyBucket === "current") ?? proiecte[0];
  };

  const dinLista = alege(summary.projects ?? []);
  if (dinLista) return dinLista.projectType ?? null;

  const dinContexte = alege((summary.contexts ?? []).flatMap((c) => c.projects ?? []));
  return dinContexte?.projectType ?? null;
}

/** Un meniu ascuns nu e o regulă, e o sugestie: paginile de coaching se închid. */
export function participantIsTraining(projectType?: string | null): boolean {
  return projectType === TRAINING_PROJECT_TYPE;
}
