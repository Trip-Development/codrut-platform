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
      eyebrow="Chestionare"
      title="Formele asignate ție"
      description="Aici vezi doar chestionarele care ți-au fost alocate pentru proiectul curent."
      navItems={participantNavItems}
      activeHref="/participant/questionnaires"
    >
      {taskGroups.length > 0 ? (
        <ParticipantTaskList
          groups={taskGroups}
          returnTo="/participant/questionnaires"
          emptyTitle={summary.emptyState.title}
          emptyDescription={summary.emptyState.description}
        />
      ) : (
        <section className="rounded-xl border border-[var(--border)] bg-surface p-6 shadow-sm">
          <h2 className="text-base font-semibold text-foreground">{summary.emptyState.title}</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/62">
            {summary.emptyState.description}
          </p>
        </section>
      )}
    </AppShell>
  );
}
