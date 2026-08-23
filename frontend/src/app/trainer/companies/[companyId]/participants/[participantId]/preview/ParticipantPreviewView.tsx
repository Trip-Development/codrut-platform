"use client";

import Link from "next/link";
import { ArrowLeftIcon, EyeIcon, InfoIcon } from "lucide-react";

import type { SessionState } from "@/api/auth";
import type { ParticipantWorkspaceSummary } from "@/api/participants";
import { ParticipantClientWorkspace } from "@/app/participant/ParticipantClientWorkspace";

type ParticipantPreviewViewProps = {
  companyId: string;
  projectId?: string | null;
  summaryData: ParticipantWorkspaceSummary;
};

export function ParticipantPreviewView({
  companyId,
  projectId,
  summaryData,
}: ParticipantPreviewViewProps) {
  const participantIdentity =
    summaryData.participantFullName?.trim() ||
    summaryData.anonymousName?.trim() ||
    "Participant";

  const exitHref = projectId
    ? `/trainer/projects/${projectId}/participants`
    : `/trainer/companies/${companyId}`;

  const previewSession: SessionState = {
    state: "authenticated",
    user: {
      id: summaryData.participantProfileId ?? "preview-participant",
      name: participantIdentity,
      email: summaryData.participantEmail ?? "",
      role: "participant",
    },
  };

  return (
    <div className="min-h-screen bg-background text-foreground pb-16">
      {/* S4 — Permanent sticky banner across the top */}
      <aside
        aria-label="Notificare mod vizualizare participant"
        className="sticky top-0 z-50 w-full border-b border-amber-500/30 bg-amber-50/95 px-4 py-3 text-amber-950 backdrop-blur-md dark:border-amber-500/20 dark:bg-amber-950/90 dark:text-amber-100 shadow-sm"
      >
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-amber-500/20 text-amber-800 dark:text-amber-200">
              <EyeIcon className="h-4 w-4" aria-hidden="true" />
            </div>
            <div className="text-sm">
              <span className="font-semibold">{participantIdentity}</span>
              <span className="mx-1.5 opacity-60">·</span>
              <span className="font-medium text-amber-800 dark:text-amber-300 uppercase text-xs tracking-wider">
                Mod STRICT READ-ONLY
              </span>
              <span className="hidden sm:inline opacity-80 ml-2 text-xs">
                (Nicio acțiune nu poate fi efectuată în numele participantului)
              </span>
            </div>
          </div>
          {/* S5 — Clear exit button */}
          <Link
            href={exitHref}
            className="inline-flex items-center gap-1.5 rounded-md bg-amber-900/10 hover:bg-amber-900/20 dark:bg-amber-100/10 dark:hover:bg-amber-100/20 px-3 py-1.5 text-xs font-semibold transition-colors shrink-0"
          >
            <ArrowLeftIcon className="h-3.5 w-3.5" aria-hidden="true" />
            Înapoi la participanți
          </Link>
        </div>
      </aside>

      <div className="mx-auto max-w-7xl px-4 pt-4">
        {/* C2 — Prominent row explaining what is excluded and why */}
        <section
          aria-label="Informații de confidențialitate și excluderi"
          className="rounded-lg border border-border/80 bg-muted/30 p-4 shadow-sm"
        >
          <div className="flex items-start gap-3">
            <InfoIcon className="h-5 w-5 text-muted-foreground shrink-0 mt-0.5" aria-hidden="true" />
            <div className="space-y-1 text-sm leading-relaxed text-muted-foreground">
              <p className="font-medium text-foreground">
                Completarea chestionarelor este indisponibilă în acest mod
              </p>
              <p>
                Ecranele de completare a chestionarelor, consimțământul și setările de cont NU sunt disponibile în această vedere, pentru că ar expune răspunsurile pe care participantul le-a dat despre alți oameni, respectiv date personale de cont.
              </p>
            </div>
          </div>
        </section>
      </div>

      {/* C1 — Render the actual participant workspace component directly! */}
      <ParticipantClientWorkspace
        session={previewSession}
        summaryData={summaryData}
        readOnly={true}
      />
    </div>
  );
}
