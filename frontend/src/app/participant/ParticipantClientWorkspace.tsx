"use client";

import Link from "next/link";

import type { SessionState } from "@/api/auth";
import type { InviteTask } from "@/api/invites";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";

type ParticipantClientWorkspaceProps = {
  session: SessionState;
  summaryData: {
    projectName: string;
    companyName?: string;
    participantFullName?: string;
    anonymousName?: string | null;
    participantEmail: string;
    deadlineLabel: string;
    pcmBase?: string | null;
    pcmPhase?: string | null;
    tasks: InviteTask[];
  };
};

const statusCopy: Record<InviteTask["status"], { label: string; helper: string }> = {
  not_started: {
    label: "De început",
    helper: "Alege un moment liniștit pentru completare.",
  },
  in_progress: {
    label: "În lucru",
    helper: "Continuă de unde ai rămas.",
  },
  completed: {
    label: "Finalizat",
    helper: "Răspunsurile au fost salvate.",
  },
};

export function ParticipantClientWorkspace({ session, summaryData }: ParticipantClientWorkspaceProps) {
  const realIdentity = summaryData.participantFullName || session.user.name || summaryData.participantEmail;
  const anonymousIdentity = summaryData.anonymousName || "Profil anonim";
  const displayIdentity = `${anonymousIdentity}${realIdentity ? ` (${realIdentity})` : ""}`;
  const pendingTasks = summaryData.tasks.filter((task) => task.status !== "completed");
  const completedTasksCount = summaryData.tasks.length - pendingTasks.length;
  const tasksProgressPct =
    summaryData.tasks.length > 0 ? Math.round((completedTasksCount / summaryData.tasks.length) * 100) : 100;
  const nextTask = pendingTasks[0];

  return (
    <AppShell
      audience="participant"
      eyebrow={summaryData.projectName}
      title={`Bună, ${anonymousIdentity}`}
      description="Lucrezi sub identitate anonimă. Completează chestionarele active, iar progresul se actualizează din baza de date."
      navItems={participantNavItems}
      activeHref="/participant"
      userLabel={anonymousIdentity}
    >
      <div className="space-y-7">
        <section className="rounded-[1.75rem] border border-burgundy/16 bg-surface/94 p-5 shadow-[0_22px_60px_rgba(137,5,5,0.10)] backdrop-blur md:p-7">
          <div className="grid gap-6 xl:grid-cols-[1.35fr_0.85fr]">
            <div className="min-w-0">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-burgundy/82">
                    Prioritatea ta acum
                  </p>
                  <h2 className="mt-2 font-display text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
                    {pendingTasks.length > 0 ? "Chestionare active" : "Ești la zi"}
                  </h2>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/62">
                    Fiecare sarcină vine din invitațiile pregătite de trainer. Identitatea afișată pentru acest proiect este <strong className="text-foreground">{displayIdentity}</strong>.
                  </p>
                </div>
                <div className="w-fit rounded-2xl bg-burgundy px-4 py-3 text-white shadow-brand">
                  <span className="block text-2xl font-semibold leading-none">{pendingTasks.length}</span>
                  <span className="mt-1 block text-xs font-semibold text-white/78">
                    {pendingTasks.length === 1 ? "sarcină activă" : "sarcini active"}
                  </span>
                </div>
              </div>

              {pendingTasks.length > 0 ? (
                <div className="mt-6 grid gap-3">
                  {pendingTasks.map((task, index) => (
                    <TaskCard key={task.assignmentId ?? task.id} task={task} index={index} />
                  ))}
                </div>
              ) : (
                <div className="mt-6 rounded-2xl border border-success/24 bg-success/10 p-5">
                  <h3 className="text-base font-semibold text-foreground">Nu ai sarcini active</h3>
                  <p className="mt-1 text-sm leading-6 text-foreground/62">
                    Când trainerul îți trimite o invitație nouă, o vei vedea aici și în pagina de chestionare.
                  </p>
                </div>
              )}
            </div>

            <aside className="rounded-2xl border border-[var(--border)] bg-surface-muted/55 p-5">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.16em] text-foreground/48">Următorul pas</p>
                  <h3 className="mt-2 text-xl font-semibold text-foreground">
                    {nextTask ? nextTask.title : "Așteaptă următoarea invitație"}
                  </h3>
                </div>
                <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-success/20 text-success-ink">
                  <CheckIcon />
                </span>
              </div>
              <p className="mt-4 text-sm leading-6 text-foreground/62">
                {nextTask
                  ? "Deschide chestionarul, completează răspunsurile și revino aici pentru restul pașilor."
                  : "Progresul tău rămâne salvat. Când apare o sarcină nouă, o vei vedea aici."}
              </p>
              <div className="mt-6 rounded-2xl bg-surface p-4 shadow-sm">
                <div className="mb-2 flex items-center justify-between text-xs font-bold text-foreground/55">
                  <span>Completare proiect</span>
                  <span>{tasksProgressPct}%</span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-burgundy/10">
                  <div className="h-full rounded-full bg-burgundy transition-all duration-700" style={{ width: `${tasksProgressPct}%` }} />
                </div>
              </div>
              <div className="mt-4 grid gap-3 text-sm">
                <ContextRow label="Companie" value={summaryData.companyName || "Companie neasociată"} />
                <ContextRow label="Identitate anonimă" value={displayIdentity} />
                <ContextRow label="Email" value={summaryData.participantEmail || "Email indisponibil"} />
              </div>
            </aside>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          <StatusCard label="Progres" value={`${tasksProgressPct}%`} detail={`${completedTasksCount}/${summaryData.tasks.length} sarcini finalizate`} tone="burgundy" />
          <StatusCard label="Proiect" value={summaryData.projectName} detail="Programul activ pentru invitațiile tale." tone="gray" />
          <StatusCard label="Confidențial" value="Da" detail="Răspunsurile 360 sunt folosite în rapoarte agregate." tone="green" />
        </section>

        <section className="rounded-[1.75rem] border border-[var(--border)] bg-surface/90 p-5 shadow-sm backdrop-blur md:p-6">
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-start">
            <div>
              <p className="text-xs font-bold uppercase tracking-[0.16em] text-burgundy/75">Profil PCM</p>
              <h2 className="mt-2 font-display text-2xl font-semibold text-foreground">Baza și faza ta</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/62">
                Aceste valori vin din chestionarul PCM salvat pe profilul tău. Dacă lipsesc, platforma îți va cere formularul la intrarea în dashboard.
              </p>
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <ProfileFact label="Bază PCM" value={formatPcmValue(summaryData.pcmBase)} />
                <ProfileFact label="Fază PCM" value={formatPcmValue(summaryData.pcmPhase)} />
              </div>
            </div>
            <Link
              href="/participant/questionnaires"
              className="tap-soft inline-flex justify-center rounded-2xl border border-burgundy/20 bg-burgundy/8 px-4 py-3 text-sm font-bold text-burgundy hover:bg-burgundy hover:text-white"
            >
              Vezi toate chestionarele
            </Link>
          </div>
        </section>
      </div>
    </AppShell>
  );
}

function TaskCard({ task, index }: { task: InviteTask; index: number }) {
  const copy = statusCopy[task.status];

  return (
    <article
      className="group/task rounded-2xl border border-burgundy/12 bg-gradient-to-br from-white to-[rgba(137,5,5,0.035)] p-4 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:border-burgundy/24 hover:shadow-[0_16px_36px_rgba(137,5,5,0.11)] dark:from-[rgba(255,255,255,0.035)] dark:to-[rgba(227,95,95,0.09)]"
      style={{ animationDelay: `${index * 70}ms` }}
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-burgundy/10 px-2.5 py-1 text-[11px] font-bold uppercase tracking-[0.12em] text-burgundy">
              {copy.label}
            </span>
            <span className="text-xs font-semibold text-foreground/45">{task.estimatedMinutes} min</span>
          </div>
          <h3 className="mt-3 text-lg font-semibold tracking-tight text-foreground">{task.title}</h3>
          <p className="mt-1.5 max-w-2xl text-sm leading-6 text-foreground/62">{task.detail}</p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-foreground/48">
            <span>{task.targetLabel}</span>
            <span aria-hidden="true">·</span>
            <span>{copy.helper}</span>
          </div>
        </div>
        <Link
          href={task.href}
          className="tap-soft inline-flex items-center justify-center gap-2 rounded-2xl bg-burgundy px-5 py-3 text-sm font-bold text-white shadow-md shadow-burgundy/15 hover:bg-burgundy-dark"
        >
          Continuă
          <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.4" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14m-6-6 6 6-6 6" />
          </svg>
        </Link>
      </div>
    </article>
  );
}

function StatusCard({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone: "burgundy" | "green" | "gray";
}) {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-surface/86 p-5 shadow-sm backdrop-blur">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-foreground/45">{label}</p>
      <p
        className={[
          "mt-2 line-clamp-2 text-2xl font-semibold tracking-tight",
          tone === "green" ? "text-success-ink" : tone === "burgundy" ? "text-burgundy" : "text-foreground",
        ].join(" ")}
      >
        {value}
      </p>
      <p className="mt-2 text-sm leading-6 text-foreground/58">{detail}</p>
    </div>
  );
}

function ContextRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-surface px-4 py-3">
      <span className="block text-xs font-semibold text-foreground/45">{label}</span>
      <span className="mt-1 block break-words text-sm font-bold text-foreground">{value}</span>
    </div>
  );
}

function ProfileFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-surface-muted/40 px-4 py-3">
      <span className="block text-[10px] font-bold uppercase tracking-wider text-foreground/45">{label}</span>
      <span className="mt-1 block text-sm font-semibold capitalize text-foreground">{value}</span>
    </div>
  );
}

function formatPcmValue(value?: string | null): string {
  if (!value) return "Necompletată";
  return value.replace(/_/g, " ");
}

function CheckIcon() {
  return (
    <svg className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2.4" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="m5 13 4 4L19 7" />
    </svg>
  );
}
