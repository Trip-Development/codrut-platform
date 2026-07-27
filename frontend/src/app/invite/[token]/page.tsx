import Link from "next/link";
import {
  AlertTriangleIcon,
  ArrowRightIcon,
  CheckIcon,
} from "lucide-react";

import {
  inviteStatusLabel,
  inviteTaskProgress,
  participantTaskTypeLabel,
  resolveInviteBundle,
  type InviteBundle,
  type InviteTask,
} from "@/api/invites";
import {
  groupParticipantTasks,
  participantTaskGroupHref,
} from "@/app/participant/task-display";
import { CURRENT_TERMS_VERSION } from "@/api/terms";
import { BrandMark } from "@/components/brand/brand-mark";
import { serverLinkButtonClassName } from "@/components/ui/server-link-button";
import { cn } from "@/utils/cn";
import {
  InviteConsentGate,
  InviteRegisterPrimaryAction,
  InviteRegistrationLink,
  InviteSessionExchange,
} from "./InviteClientActions";

type ValidInviteBundle = Extract<InviteBundle, { state: "valid" }>;

type InvitePageProps = {
  params: Promise<{ token: string }>;
};

function hasServerConsent(bundle: ValidInviteBundle): boolean {
  return bundle.termsVersion === CURRENT_TERMS_VERSION && Boolean(bundle.termsAcceptedAt);
}

async function resolveInviteSafely(token: string): Promise<InviteBundle> {
  try {
    return await resolveInviteBundle(token);
  } catch (error) {
    return {
      state: "not_found",
      token,
      message: error instanceof Error ? error.message : "A apărut o eroare la verificarea invitației.",
    };
  }
}

export default async function InvitePage({ params }: InvitePageProps) {
  const { token } = await params;
  const data = await resolveInviteSafely(token);

  if (data.state !== "valid") {
    return <InvalidInviteState message={data.message} />;
  }

  if (data.isLeadership && !data.alreadyRegistered) {
    return <LeadershipRegistrationState token={token} data={data} />;
  }

  const tasksView = <InviteTasksView token={token} data={data} />;

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

function LeadershipRegistrationState({
  token,
  data,
}: {
  token: string;
  data: ValidInviteBundle;
}) {
  return (
    <InviteFrame width="sm">
      <InvitePanel>
        <span className="mx-auto inline-flex h-5 w-fit items-center rounded-full bg-secondary px-2 py-0.5 text-xs font-semibold text-secondary-foreground">
          Cont Leadership
        </span>
        <h1 className="mt-6 text-center text-3xl font-semibold leading-tight tracking-normal">
          Activează contul înainte de chestionare
        </h1>
        <p className="mt-3 text-center text-sm leading-6 text-muted-foreground">
          Invitația pentru <strong className="text-foreground">{data.participantEmail}</strong> este pregătită.
          Creează contul ca să vezi spațiul tău de participant și sarcinile proiectului.
        </p>
        <div className="mt-8 flex flex-col gap-3">
          <InviteRegistrationLink token={token} bundle={data}>
            Înregistrează cont Leadership
            <ArrowRightIcon data-icon="inline-end" aria-hidden="true" />
          </InviteRegistrationLink>
          <Link href="/" className={serverLinkButtonClassName({ variant: "outline", size: "lg" })}>
            Pagina principală
          </Link>
        </div>
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
            <p className="text-sm font-semibold text-burgundy">{data.projectName}</p>
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
              <div className="h-full rounded-full bg-burgundy" style={{ width: `${progress.percent}%` }} />
            </div>
          </div>
        </div>

        <InviteTaskQueue tasks={data.tasks} returnTo={returnTo} inviteToken={token} />

        <div className="mt-7 flex flex-col gap-3 border-t border-border pt-5 sm:flex-row">
          {data.isLeadership && !data.alreadyRegistered ? (
            <InviteRegisterPrimaryAction token={token} bundle={data} />
          ) : null}
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
  returnTo,
  inviteToken,
}: {
  tasks: InviteTask[];
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

  const groups = groupParticipantTasks(tasks);

  return (
    <section className="divide-y divide-border" aria-label="Chestionare disponibile">
      {groups.map((group) => {
        const isComplete = group.status === "completed";
        const task = group.actionTask ?? group.tasks[0];
        const href = participantTaskGroupHref(group, { returnTo, inviteToken });
        const targetLabel =
          group.kind === "review360"
            ? group.targetSummary
            : safeInviteTarget(task);

        return (
          <article key={group.id} className="grid gap-4 py-5 md:grid-cols-[minmax(0,1fr)_auto] md:items-center">
            <div className="flex min-w-0 items-start gap-3">
              <span
                aria-hidden="true"
                className={isComplete ? "mt-1.5 size-2.5 shrink-0 rounded-full bg-success" : "mt-1.5 size-2.5 shrink-0 rounded-full bg-burgundy"}
              />
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <h2 className="text-base font-semibold text-foreground">{group.title}</h2>
                  <span className={isComplete ? "text-xs font-semibold text-success" : "text-xs font-semibold text-burgundy"}>
                    {inviteStatusLabel(group.status)}
                  </span>
                </div>
                <p className="mt-1.5 text-sm text-muted-foreground">
                  {targetLabel || participantTaskTypeLabel(task.questionnaireKey)} · {group.estimatedMinutes} min
                </p>
                {group.kind === "review360" ? (
                  <p className="mt-1 text-xs font-semibold text-muted-foreground">
                    {group.completedCount}/{group.totalCount} review-uri finalizate
                  </p>
                ) : null}
              </div>
            </div>
            {isComplete ? (
              <span className="inline-flex items-center gap-2 text-sm font-semibold text-success">
                <CheckIcon aria-hidden="true" className="size-4" strokeWidth={2.2} />
                Finalizat
              </span>
            ) : href ? (
              <Link href={href} className={serverLinkButtonClassName({ variant: "outline", className: "w-fit" })}>
                {group.kind === "review360" && group.status === "in_progress" ? "Continuă" : "Deschide"}
                <ArrowRightIcon data-icon="inline-end" aria-hidden="true" />
              </Link>
            ) : null}
          </article>
        );
      })}
    </section>
  );
}

function safeInviteTarget(task: InviteTask): string {
  if (task.questionnaireKey === "lencioni" || task.questionnaireKey === "lencioni_en") {
    return "Echipa ta";
  }
  const isReview = task.questionnaireKey === "boss_360" || task.questionnaireKey === "boss_360_en" || task.questionnaireKey === "icare";
  if (!isReview) return task.targetLabel;

  const cleaned = task.targetLabel.trim().replace(/\s+/g, " ");
  if (!cleaned || cleaned.includes("@")) return "Persoana indicată";
  if (/[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}/i.test(cleaned)) {
    return "Persoana indicată";
  }
  return cleaned;
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
    <section className="rounded-lg border bg-surface p-6 shadow-sm md:p-8">
      {children}
    </section>
  );
}
