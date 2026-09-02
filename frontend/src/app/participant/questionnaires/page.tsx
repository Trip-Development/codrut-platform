import { getParticipantSession } from "@/api/auth-server";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { ParticipantCompletionState } from "../ParticipantCompletionState";
import { ParticipantTaskList } from "../ParticipantTaskList";
import {
  participantActiveHref,
  participantCanViewResults,
  participantScopeParams,
  participantScopedHref,
  participantScopedNavItems,
  participantWorkspaceRequestOptions,
  type ParticipantRouteSearchParams,
} from "../participant-context";
import { countAvailableParticipantResults } from "../result-state";
import {
  groupParticipantTasksByProject,
  participantTaskProjectsFromCatalog,
} from "../task-display";

export default async function ParticipantQuestionnairesPage({
  searchParams,
}: {
  searchParams: Promise<ParticipantRouteSearchParams>;
}) {
  const routeParams = await searchParams;
  const requestOptions = await getServerApiRequestOptions();
  const [participant, summary] = await Promise.all([
    getParticipantSession(),
    getParticipantWorkspaceSummary(
      participantWorkspaceRequestOptions(requestOptions.headers, routeParams),
    ),
  ]);
  const scopeParams = participantScopeParams(summary);
  const questionnairesHref = participantScopedHref("/participant/questionnaires", scopeParams);
  const resultsHref = participantScopedHref("/participant/results", scopeParams);
  const questionnaireProjects =
    (summary.questionnaireProjects?.length ?? 0) > 0
      ? participantTaskProjectsFromCatalog(summary.questionnaireProjects ?? [])
      : groupParticipantTasksByProject(summary.tasks, summary.projects);
  const allQuestionnaires = questionnaireProjects.flatMap((project) =>
    project.groups.flatMap((group) => group.tasks),
  );
  const hasTasks = allQuestionnaires.length > 0;
  const allTasksComplete =
    hasTasks &&
    allQuestionnaires.every((task) => task.status === "completed");
  const resultCount = countAvailableParticipantResults(summary);
  const showResults = participantCanViewResults(summary);

  return (
    <AppShell
      audience="participant"
      eyebrow=""
      title="Chestionare"
      description=""
      navItems={participantScopedNavItems(scopeParams, showResults)}
      activeHref={participantActiveHref("/participant/questionnaires", scopeParams)}
      userLabel={summary.participantFullName.split(/\s+/)[0] || "Participant"}
      session={participant}
    >
      {allTasksComplete ? (
        <div className="mb-8">
          <ParticipantCompletionState resultCount={resultCount} resultsHref={resultsHref} />
        </div>
      ) : null}
      {questionnaireProjects.length > 0 ? (
        <ParticipantTaskList
          projects={questionnaireProjects}
          persistenceIdentityKey={`${participant.user.id}:${summary.participantProfileId ?? "all"}`}
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
