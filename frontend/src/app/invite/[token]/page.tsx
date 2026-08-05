import Link from "next/link";
import {
  AlertTriangleIcon,
  ArrowRightIcon,
} from "lucide-react";

import {
  inviteTaskProgress,
  resolveInviteBundle,
  type InviteBundle,
  type InviteTask,
} from "@/api/invites";
import {
  groupParticipantTasksByProject,
} from "@/app/participant/task-display";
import { ParticipantTaskList } from "@/app/participant/ParticipantTaskList";
import { BrandMark } from "@/components/brand/brand-mark";
import { serverLinkButtonClassName } from "@/components/ui/server-link-button";
import { cn } from "@/utils/cn";
import {
  InviteConsentGate,
  InviteSessionExchange,
} from "./InviteClientActions";

type ValidInviteBundle = Extract<InviteBundle, { state: "valid" }>;

type InvitePageProps = {
  params: Promise<{ token: string }>;
};

function hasServerConsent(bundle: ValidInviteBundle): boolean {
  return bundle.consentCurrent;
}

async function resolveInviteSafely(token: string): Promise<InviteBundle> {
  try {
    return await resolveInviteBundle(token);
  } catch {
    return {
      state: "not_found",
      token,
      message: "Nu am putut verifica invitația. Reîncearcă sau cere un link nou de la trainer.",
    };
  }
}

export default async function InvitePage({ params }: InvitePageProps) {
  const { token } = await params;
  const data = await resolveInviteSafely(token);

  if (data.state !== "valid") {
    return <InvalidInviteState message={data.message} />;
  }

  const tasksView = <InviteTasksView token={token} data={data} />;

  if (data.alreadyRegistered) {
    return (
      <InviteSessionExchange token={token} bundle={data}>
        {tasksView}
      </InviteSessionExchange>
    );
  }

  if (!hasServerConsent(data)) {
    return (
      <InviteConsentGate token={token} bundle={data}>
        {tasksView}
      </InviteConsentGate>
    );
  }

  return (
    <InviteSessionExchange token={token} bundle={data}>
      {tasksView}
    </InviteSessionExchange>
  );
}

function InvalidInviteState({ message }: { message: string }) {
  return (
    <InviteFrame width="sm">
      <InvitePanel>
        <AlertTriangleIcon className="mx-auto size-10 text-primary" aria-hidden="true" />
        <h1 className="mt-6 text-center text-3xl font-semibold leading-tight tracking-normal">
          Invitație nevalidă
        </h1>
        <p className="mt-3 text-center text-sm leading-6 text-muted-foreground">
          {message || "Nu am putut valida această invitație. Cere un link nou de la trainer."}
        </p>
        <Link href="/" className={serverLinkButtonClassName({ size: "lg", className: "mt-8 w-full" })}>
          Mergi la Cody
          <ArrowRightIcon data-icon="inline-end" aria-hidden="true" />
        </Link>
      </InvitePanel>
    </InviteFrame>
  );
}

function InviteTasksView({
  token,
  data,
}: {
  token: string;
  data: ValidInviteBundle;
}) {
  const progress = inviteTaskProgress(data.tasks);
  const returnTo = `/invite/${token}`;

  return (
    <InviteFrame width="lg">
      <section>
        <Link href="/" className="inline-flex rounded-lg px-2 py-1 transition-colors hover:bg-muted">
          <BrandMark />
        </Link>

        <div className="mt-10 grid gap-7 border-b border-border pb-7 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold text-primary">{data.projectName}</p>
            <h1 className="mt-3 text-4xl font-semibold leading-tight tracking-tight text-foreground md:text-5xl">
              Chestionarele tale
            </h1>
            <p className="mt-3 text-sm text-muted-foreground">
              Profil: <strong className="text-foreground">{data.anonymousName ?? "participant anonim"}</strong>
            </p>
          </div>
          <div className="min-w-40">
            <div className="flex items-baseline justify-between gap-4">
              <span className="text-sm font-semibold text-muted-foreground">Progres</span>
              <span className="font-mono text-sm font-semibold tabular-nums text-foreground">{progress.completed}/{progress.total}</span>
            </div>
            <div
              className="mt-2 h-1.5 overflow-hidden rounded-full bg-muted"
              role="progressbar"
              aria-label="Progresul chestionarelor"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progress.percent}
            >
              <div className="h-full rounded-full bg-primary" style={{ width: `${progress.percent}%` }} />
            </div>
          </div>
        </div>

        <InviteTaskQueue
          tasks={data.tasks}
          projectName={data.projectName}
          deadlineLabel={data.deadlineLabel}
          returnTo={returnTo}
          inviteToken={token}
        />

        <div className="mt-7 flex flex-col gap-3 border-t border-border pt-5 sm:flex-row">
          <Link href="/" className={serverLinkButtonClassName({ variant: "ghost", className: "sm:ml-auto" })}>
            Pagina principală
          </Link>
        </div>
      </section>
    </InviteFrame>
  );
}

function InviteTaskQueue({
  tasks,
  projectName,
  deadlineLabel,
  returnTo,
  inviteToken,
}: {
  tasks: InviteTask[];
  projectName: string;
  deadlineLabel: string;
  returnTo: string;
  inviteToken: string;
}) {
  if (tasks.length === 0) {
    return (
      <section className="border-b border-border py-8">
        <h2 className="text-base font-semibold text-foreground">Nu ai chestionare disponibile</h2>
        <p className="mt-2 text-sm leading-6 text-muted-foreground">Cere trainerului să verifice invitația dacă te așteptai la o sarcină.</p>
      </section>
    );
  }

  const projectId =
    tasks.find((task) => task.projectId)?.projectId ??
    `secure:${tasks.map((task) => task.assignmentId).sort().join(":")}`;
  const scopedTasks = tasks.map((task) => ({
    ...task,
    projectId: task.projectId ?? projectId,
    projectName: task.projectName ?? projectName,
    deadlineLabel: task.deadlineLabel ?? deadlineLabel,
  }));
  const projects = groupParticipantTasksByProject(scopedTasks, [
    {
      id: projectId,
      name: projectName,
      deadlineLabel,
    },
  ]);

  return (
    <ParticipantTaskList
      projects={projects}
      persistenceIdentityKey={`secure:${tasks
        .map((task) => task.assignmentId)
        .sort()
        .join(":")}`}
      returnTo={returnTo}
      inviteToken={inviteToken}
      emptyTitle="Nu ai chestionare disponibile"
      emptyDescription="Cere trainerului să verifice invitația."
    />
  );
}

function InviteFrame({
  children,
  width,
}: {
  children: React.ReactNode;
  width: "sm" | "md" | "lg";
}) {
  const maxWidth = {
    sm: "max-w-md",
    md: "max-w-xl",
    lg: "max-w-5xl",
  }[width];

  return (
    <main className="flex min-h-[100dvh] items-center justify-center bg-background px-4 py-10 text-foreground md:px-6">
      <div className={cn("w-full", maxWidth)}>{children}</div>
    </main>
  );
}

function InvitePanel({ children }: { children: React.ReactNode }) {
  return (
    <section className="rounded-lg border bg-surface p-6 md:p-8">
      {children}
    </section>
  );
}
