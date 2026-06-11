"use client";

import Link from "next/link";

import type { InviteTask } from "@/api/invites";

type WorkspaceSummary = {
  projectName: string;
  participantFullName?: string;
  companyName?: string;
  participantEmail?: string | null;
  pcmBase?: string | null;
  pcmPhase?: string | null;
  tasks?: InviteTask[];
};

type AccountWorkspaceProps = {
  session: import("@/api/auth").SessionState;
  summary: WorkspaceSummary;
};

export function AccountWorkspace({ session, summary }: AccountWorkspaceProps) {
  const name = summary.participantFullName || session.user.name || "Participant";
  const email = summary.participantEmail || "Email indisponibil";
  const company = summary.companyName || "Companie neasociată";
  const pcmTask = summary.tasks?.find((task) => task.questionnaireKey === "pcm_base");
  const pcmHref = pcmTask?.href ?? "/participant/questionnaires";
  const pcmCtaLabel = pcmTask ? "Actualizează PCM" : "Vezi chestionarele";

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <section className="rounded-3xl border border-[var(--border)] bg-surface p-6 shadow-sm md:p-8">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-burgundy/75">Profil participant</p>
        <h2 className="mt-2 font-display text-2xl font-semibold text-foreground">{name}</h2>
        <p className="mt-2 text-sm leading-6 text-foreground/62">
          Datele afișate aici sunt citite din profilul tău de participant și din proiectul activ.
        </p>

        <div className="mt-6 grid gap-3">
          <ProfileFact label="Email corporate" value={email} />
          <ProfileFact label="Companie" value={company} />
          <ProfileFact label="Proiect curent" value={summary.projectName} />
        </div>
      </section>

      <section className="rounded-3xl border border-[var(--border)] bg-surface p-6 shadow-sm md:p-8">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-burgundy/75">Profil PCM</p>
            <h2 className="mt-2 font-display text-2xl font-semibold text-foreground">Bază și fază</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/62">
              Aceste câmpuri se actualizează doar prin chestionarul PCM salvat în baza de date. Nu folosim valori implicite locale.
            </p>
          </div>
          <Link
            href={pcmHref}
            className="tap-soft inline-flex justify-center rounded-2xl bg-burgundy px-4 py-3 text-sm font-bold text-white hover:bg-burgundy/90"
          >
            {pcmCtaLabel}
          </Link>
        </div>

        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          <ProfileFact label="Bază PCM" value={formatPcmValue(summary.pcmBase)} />
          <ProfileFact label="Fază PCM" value={formatPcmValue(summary.pcmPhase)} />
        </div>
      </section>

      <section className="rounded-3xl border border-[var(--border)] bg-surface p-6 shadow-sm md:p-8 lg:col-span-2">
        <p className="text-xs font-bold uppercase tracking-[0.16em] text-burgundy/75">Confidențialitate</p>
        <h2 className="mt-2 font-display text-2xl font-semibold text-foreground">Cum sunt folosite răspunsurile</h2>
        <div className="mt-6 grid gap-4 md:grid-cols-3">
          <PrivacyCard
            title="Feedback 360"
            text="Răspunsurile individuale sunt folosite pentru rapoarte agregate. Persoana evaluată nu vede răspunsurile brute."
          />
          <PrivacyCard
            title="Trainer"
            text="Trainerul poate urmări progresul și completările ca să gestioneze proiectul și reminderele."
          />
          <PrivacyCard
            title="Scop"
            text="Platforma susține dezvoltarea și trainingul, nu decizii administrative sau evaluări oficiale de performanță."
          />
        </div>
      </section>
    </div>
  );
}

function ProfileFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-surface-muted/35 px-4 py-3">
      <span className="block text-[10px] font-bold uppercase tracking-wider text-foreground/45">{label}</span>
      <span className="mt-1 block break-words text-sm font-semibold text-foreground">{value}</span>
    </div>
  );
}

function PrivacyCard({ title, text }: { title: string; text: string }) {
  return (
    <article className="rounded-2xl border border-[var(--border)] bg-surface-muted/30 p-5">
      <h3 className="text-sm font-bold text-foreground">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-foreground/62">{text}</p>
    </article>
  );
}

function formatPcmValue(value?: string | null): string {
  if (!value) return "Necompletată";
  return value.replace(/_/g, " ");
}
