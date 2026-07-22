import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { ParticipantCompletionState } from "../ParticipantCompletionState";
import { ParticipantContextSelector } from "../ParticipantContextSelector";
import { ParticipantTaskList } from "../ParticipantTaskList";
import {
  participantActiveHref,
  participantScopeParams,
  participantScopedHref,
  participantScopedNavItems,
  participantWorkspaceRequestOptions,
  type ParticipantRouteSearchParams,
} from "../participant-context";
import { countAvailableParticipantResults } from "../result-state";
import { groupParticipantTasks } from "../task-display";

export default async function ParticipantQuestionnairesPage({
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
  const taskGroups = groupParticipantTasks(summary.tasks);
  const hasTasks = summary.tasks.length > 0;
  const allTasksComplete = hasTasks && summary.tasks.every((task) => task.status === "completed");
  const resultCount = countAvailableParticipantResults(summary);

  return (
    <AppShell
      audience="participant"
      eyebrow=""
      title="Chestionare"
      description=""
      navItems={participantScopedNavItems(scopeParams)}
      activeHref={participantActiveHref("/participant/questionnaires", scopeParams)}
      userLabel={summary.participantFullName.split(/\s+/)[0] || "Participant"}
    >
      <ParticipantContextSelector
        contexts={summary.contexts}
        selectedProfileId={summary.participantProfileId}
        selectedProjectId={summary.projectId}
      />
      {allTasksComplete ? (
        <div className="mb-8">
          <ParticipantCompletionState resultCount={resultCount} resultsHref={resultsHref} />
        </div>
      ) : null}
      {taskGroups.length > 0 ? (
        <ParticipantTaskList
          groups={taskGroups}
          returnTo={questionnairesHref}
          emptyTitle={summary.emptyState.title}
          emptyDescription={summary.emptyState.description}
        />
      ) : (
        <section className="border-y border-border py-8">
          <h2 className="text-base font-semibold text-foreground">{summary.emptyState.title}</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">
            {summary.emptyState.description}
          </p>
        </section>
      )}
    </AppShell>
  );
}
