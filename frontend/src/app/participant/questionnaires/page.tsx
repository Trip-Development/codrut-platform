import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";
import { ParticipantTaskList } from "../ParticipantTaskList";
import { groupParticipantTasks } from "../task-display";

export default async function ParticipantQuestionnairesPage() {
  const requestOptions = await getServerApiRequestOptions();
  const summary = await getParticipantWorkspaceSummary(requestOptions);
  const taskGroups = groupParticipantTasks(summary.tasks);

  return (
    <AppShell
      audience="participant"
      eyebrow=""
      title="Chestionare"
      description=""
      navItems={participantNavItems}
      activeHref="/participant/questionnaires"
      userLabel={summary.participantFullName.split(/\s+/)[0] || "Participant"}
    >
      {taskGroups.length > 0 ? (
        <ParticipantTaskList
          groups={taskGroups}
          returnTo="/participant/questionnaires"
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
