import type {
  ParticipantWorkspaceContext,
  ParticipantWorkspaceSummary,
} from "@/api/participants";
import { participantNavItems, type ShellNavItem } from "@/components/shell/nav";

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

export function participantScopedNavItems(params: URLSearchParams): ShellNavItem[] {
  return participantNavItems.map((item) => ({
    ...item,
    href: participantScopedHref(item.href, params),
  }));
}

export function participantActiveHref(pathname: string, params: URLSearchParams): string {
  return participantScopedHref(pathname, params);
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
