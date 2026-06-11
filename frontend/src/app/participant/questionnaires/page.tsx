import Link from "next/link";

import { inviteStatusLabel } from "@/api/invites";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";

export default async function ParticipantQuestionnairesPage() {
  const requestOptions = await getServerApiRequestOptions();
  const summary = await getParticipantWorkspaceSummary(requestOptions);

  return (
    <AppShell
      audience="participant"
      eyebrow="Chestionare"
      title="Formele asignate ție"
      description="Aici vezi doar chestionarele care ți-au fost alocate pentru proiectul curent."
      navItems={participantNavItems}
      activeHref="/participant/questionnaires"
    >
      {summary.tasks.length > 0 ? (
        <div className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
          {summary.tasks.map((task) => (
            <article
              key={task.assignmentId}
              className="grid gap-4 border-b border-[var(--border)] px-5 py-4 last:border-b-0 md:grid-cols-[1fr_auto] md:items-center"
            >
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-base font-semibold text-foreground">{task.title}</h2>
                  <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-semibold text-foreground/55">
                    {inviteStatusLabel(task.status)}
                  </span>
                </div>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/62">
                  {task.detail}
                </p>
                <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs font-semibold text-foreground/45">
                  <span>{task.targetLabel}</span>
                  <span>{task.estimatedMinutes} min</span>
                  <span>{summary.projectName}</span>
                </div>
              </div>
              <Link
                href={task.href}
                className="tap-soft inline-flex justify-center rounded-xl bg-foreground px-4 py-2.5 text-sm font-semibold text-background hover:bg-burgundy hover:text-white"
              >
                {task.status === "completed" ? "Revizuiește" : "Deschide"}
              </Link>
            </article>
          ))}
        </div>
      ) : (
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-6 shadow-sm">
          <h2 className="text-base font-semibold text-foreground">{summary.emptyState.title}</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/62">
            {summary.emptyState.description}
          </p>
        </section>
      )}
    </AppShell>
  );
}
