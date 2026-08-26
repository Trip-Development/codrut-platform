import Link from "next/link";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import {
  ArrowLeftIcon,
  EyeIcon,
  ShieldCheckIcon,
} from "lucide-react";

import {
  getCompanyAssignments,
  getCompanyDetail,
  getCompanyProjectById,
  getCompanyReportAggregate,
  getParticipantAccountLinkStatus,
  getProjectParticipants,
} from "@/api/companies";
import { formatPcmLabel, getPcmProfile } from "@/api/pcm";
import { getServerApiRequestOptions } from "@/api/server-request";
import { IdentityMark } from "@/components/presentation/identity-mark";
import { Separator } from "@/components/ui/separator";
import { cn } from "@/utils/cn";
import { formatRomanianDate } from "@/utils/date-format";
import {
  buildParticipantProjectHistory,
  buildParticipantResultSummaries,
  countPrivateFeedbackGiven,
  countPrivateFeedbackReceived,
} from "./participant-profile-data";
import { AccountLinkRepairPanel } from "./AccountLinkRepairPanel";

type TrainerParticipantReportPageProps = {
  params: Promise<{ projectId: string; participantId: string }>;
};

const tableHeaderClass = "px-4 py-3 text-left text-xs font-semibold text-muted-foreground";

export default async function TrainerParticipantReportPage({ params }: TrainerParticipantReportPageProps) {
  const [{ projectId, participantId }, requestOptions] = await Promise.all([
    params,
    getServerApiRequestOptions(),
  ]);
  const project = await getCompanyProjectById(projectId, requestOptions);

  if (!project) {
    notFound();
  }

  const [participants, projectAssignments, companyDetail, aggregate, accountLinkStatus] = await Promise.all([
    getProjectParticipants(project.company_id, project.id, requestOptions),
    getCompanyAssignments(project.company_id, requestOptions, { projectId: project.id }),
    getCompanyDetail(project.company_id, requestOptions),
    getCompanyReportAggregate(project.company_id, requestOptions),
    getParticipantAccountLinkStatus(project.company_id, participantId, requestOptions).catch(() => null),
  ]);
  const participant = participants.find((item) => item.id === participantId);

  if (!participant) {
    notFound();
  }

  const allProjects = companyDetail?.projects ?? [project];
  const allAssignments = companyDetail?.assignments ?? projectAssignments;
  const currentAssignments = projectAssignments.filter(
    (assignment) => assignment.respondent_profile_id === participant.id || assignment.target_person_id === participant.id,
  );
  const resultSummaries = buildParticipantResultSummaries({
    participantId: participant.id,
    assignments: allAssignments,
    results: aggregate.results,
  });
  const historyRows = buildParticipantProjectHistory({
    participantId: participant.id,
    assignments: allAssignments,
    projects: allProjects,
  });
  const completedCount = currentAssignments.filter((assignment) =>
    assignment.status === "submitted" || assignment.status === "validated" || assignment.status === "scored",
  ).length;
  const scoredCount = currentAssignments.filter((assignment) => assignment.status === "scored" || assignment.scored_at).length;
  const feedbackGivenCount = countPrivateFeedbackGiven(allAssignments, participant.id);
  const feedbackReceivedCount = countPrivateFeedbackReceived(allAssignments, participant.id);
  const pcmBase = getPcmProfile(participant.pcm_base ?? participant.pcm_profile);
  const pcmPhase = getPcmProfile(participant.pcm_phase);

  return (
    <div className="flex flex-col gap-6">
      <BackLink href={`/trainer/projects/${project.id}/participants`} />

      <section className="grid gap-6 border-b border-border pb-6 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <div>
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div className="flex min-w-0 items-start gap-5">
              <IdentityMark
                kind="person"
                label={participant.full_name}
                seed={`participant:${participant.id}`}
                paletteKey={participant.avatar_palette_key}
                size="lg"
              />
              <div className="min-w-0">
                <h2 className="text-3xl font-semibold leading-tight text-foreground">{participant.full_name}</h2>
                <p className="mt-2 break-words text-sm text-muted-foreground">{participant.email ?? "Email lipsă"}</p>
              </div>
            </div>

            <div className="flex flex-col items-start sm:items-end gap-1.5 shrink-0">
              <Link
                href={`/trainer/companies/${project.company_id}/participants/${participant.id}/preview?projectId=${project.id}`}
                className="inline-flex items-center gap-2 rounded-md bg-secondary px-3.5 py-2 text-sm font-semibold text-secondary-foreground shadow-xs transition-colors hover:bg-secondary/80 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
                title="Se deschide în mod citire și se înregistrează în jurnalul de acces"
              >
                <EyeIcon className="size-4" aria-hidden="true" />
                <span>Vezi ca participant</span>
              </Link>
              <span className="text-xs text-muted-foreground">
                Mod citire · Se înregistrează în jurnalul de acces
              </span>
            </div>
          </div>

          <dl className="mt-6 grid gap-x-8 gap-y-4 sm:grid-cols-2 xl:grid-cols-4">
            <ProfileFact label="Poziție" value={participant.position ?? "Necompletată"} />
            <ProfileFact label="Manager" value={participant.reports_to_name ?? "Fără manager"} />
            <ProfileFact label="Bază PCM" value={formatPcmLabel(participant.pcm_base ?? participant.pcm_profile)} color={pcmBase?.color} />
            <ProfileFact label="Fază PCM" value={formatPcmLabel(participant.pcm_phase)} color={pcmPhase?.color} />
          </dl>
        </div>

        <aside className="border-l border-border pl-5">
          <div className="flex items-start gap-3">
            <ShieldCheckIcon aria-hidden="true" className="size-5 shrink-0 text-success-ink" strokeWidth={1.8} />
            <div>
              <h3 className="text-sm font-semibold text-foreground">Vizibilitate protejată</h3>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Sunt afișate doar scoruri calculate. Răspunsurile brute și feedbackul 360 oferit altora rămân private.
              </p>
            </div>
          </div>
        </aside>
      </section>

      <AccountLinkRepairPanel
        companyId={project.company_id}
        participantId={participant.id}
        initialStatus={accountLinkStatus}
      />

      <section className="flex flex-wrap gap-x-10 gap-y-4 border-b border-border pb-5">
        <SummaryMetric label="Asignări" value={currentAssignments.length} detail={`${completedCount} completate`} />
        <SummaryMetric label="Scorate" value={scoredCount} />
        <SummaryMetric label="Feedback oferit" value={feedbackGivenCount} />
        <SummaryMetric label="Feedback primit" value={feedbackReceivedCount} />
      </section>

      <section className="border-y border-border">
        <PanelHeader className="py-4">
          <PanelTitle className="text-xl">Istoric proiecte</PanelTitle>
        </PanelHeader>
        <Separator />
        <PanelContent className="px-0">
          <div className="md:overflow-x-auto">
            <table className="block w-full border-collapse text-left text-sm md:table md:min-w-[62rem] xl:min-w-0 xl:table-fixed">
              <colgroup>
                <col className="w-[28%]" />
                <col className="w-[12%]" />
                <col className="w-[12%]" />
                <col className="w-[12%]" />
                <col className="w-[18%]" />
                <col className="w-[18%]" />
              </colgroup>
              <thead className="hidden bg-muted/45 md:table-header-group">
                <tr className="border-b">
                  <th className={tableHeaderClass}>Proiect</th>
                  <th className={tableHeaderClass}>Asignări</th>
                  <th className={tableHeaderClass}>Completate</th>
                  <th className={tableHeaderClass}>Scorate</th>
                  <th className={tableHeaderClass}>360 oferit/primit</th>
                  <th className={tableHeaderClass}>Ultima activitate</th>
                </tr>
              </thead>
              <tbody className="block divide-y divide-border md:table-row-group md:divide-y-0">
                {historyRows.length > 0 ? (
                  historyRows.map((row) => (
                    <tr key={row.projectId} className="grid grid-cols-3 gap-x-3 gap-y-3 px-4 py-4 hover:bg-muted/35 md:table-row md:px-0 md:py-0">
                      <td className="col-span-3 row-start-1 font-semibold text-foreground md:px-4 md:py-3">{row.projectName}</td>
                      <td className="col-start-1 row-start-2 md:px-4 md:py-3">
                        <span className="mb-1 block text-xs font-medium text-muted-foreground md:hidden">Asignări</span>
                        <CountPill value={row.assignedCount} />
                      </td>
                      <td className="col-start-2 row-start-2 md:px-4 md:py-3">
                        <span className="mb-1 block text-xs font-medium text-muted-foreground md:hidden">Completate</span>
                        <CountPill value={row.completedCount} tone="success" />
                      </td>
                      <td className="col-start-3 row-start-2 md:px-4 md:py-3">
                        <span className="mb-1 block text-xs font-medium text-muted-foreground md:hidden">Scorate</span>
                        <CountPill value={row.scoredCount} tone="primary" />
                      </td>
                      <td className="col-span-2 row-start-3 md:px-4 md:py-3">
                        <span className="mr-2 text-xs font-medium text-muted-foreground md:hidden">360 oferit/primit</span>
                        <span className="font-semibold text-foreground">{row.feedbackGivenCount}/{row.feedbackReceivedCount}</span>
                      </td>
                      <td className="col-start-3 row-start-3 text-right text-muted-foreground md:px-4 md:py-3 md:text-left">
                        <span className="mb-1 block text-xs font-medium md:hidden">Activitate</span>
                        {formatDate(row.lastActivityAt)}
                      </td>
                    </tr>
                  ))
                ) : (
                  <tr className="block md:table-row">
                    <td colSpan={6} className="block px-5 py-8 text-center text-sm font-medium text-muted-foreground md:table-cell">
                      Nu există încă istoric de proiect pentru acest participant.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </PanelContent>
      </section>

      <section className="flex flex-col gap-5">
        <div>
          <h2 className="text-xl font-semibold text-foreground">Rezultate calculate</h2>
        </div>
        {resultSummaries.length > 0 ? (
          <div className="grid gap-3 xl:grid-cols-2">
            {resultSummaries.map((result) => (
              <ProfilePanel key={result.assignmentId} className="py-3">
                <PanelHeader action={<ProfilePill>{formatDate(result.completedAt)}</ProfilePill>}>
                  <PanelTitle>{result.questionnaireLabel}</PanelTitle>
                  <PanelDescription className="font-semibold">{result.targetLabel}</PanelDescription>
                </PanelHeader>
                <PanelContent className="grid gap-2 sm:grid-cols-3">
                  <MiniStat label="Dimensiuni" value={String(result.dimensionCount)} />
                  <MiniStat label="Scor mediu" value={result.averageScore === null ? "Indisponibil" : formatScore(result.averageScore)} />
                  <MiniStat label="Principal" value={result.primaryResultLabel ?? "Indisponibil"} />
                </PanelContent>
              </ProfilePanel>
            ))}
          </div>
        ) : (
          <p className="border-y border-border px-4 py-8 text-center text-sm font-medium text-muted-foreground">
            Nu există rezultate calculate care pot fi afișate sumarizat pentru acest participant.
          </p>
        )}
      </section>
    </div>
  );
}

function BackLink({ href }: { href: string }) {
  return (
    <Link
      href={href}
      className="inline-flex h-9 w-fit shrink-0 items-center justify-center gap-2 rounded-md px-2 text-sm font-semibold text-muted-foreground outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/45"
    >
      <ArrowLeftIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
      Înapoi la participanți
    </Link>
  );
}

function ProfilePanel({
  as: Component = "article",
  children,
  className,
}: {
  as?: "article" | "aside" | "section";
  children: ReactNode;
  className?: string;
}) {
  return (
    <Component
      className={cn(
        "overflow-hidden rounded-lg border bg-surface text-sm text-card-foreground",
        className,
      )}
    >
      {children}
    </Component>
  );
}

function PanelHeader({
  children,
  action,
  className,
}: {
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("grid auto-rows-min items-start gap-1 rounded-t-lg px-4", action ? "grid-cols-[1fr_auto]" : null, className)}>
      <div>{children}</div>
      {action ? <div className="col-start-2 row-span-2 row-start-1 self-start justify-self-end">{action}</div> : null}
    </div>
  );
}

function PanelTitle({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("font-heading text-sm leading-snug font-medium", className)}>{children}</div>;
}

function PanelDescription({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("text-sm text-muted-foreground", className)}>{children}</div>;
}

function PanelContent({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("px-4", className)}>{children}</div>;
}

function ProfileFact({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div>
      <dt className="text-xs font-semibold text-muted-foreground">{label}</dt>
      <dd className="mt-1 flex min-w-0 items-center gap-2 truncate text-sm font-semibold text-foreground">
        {color ? <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: color }} /> : null}
        <span className="truncate">{value}</span>
      </dd>
    </div>
  );
}

function SummaryMetric({
  label,
  value,
  detail,
}: {
  label: string;
  value: number;
  detail?: string;
}) {
  return (
    <div className="min-w-28">
      <p className="text-xs font-semibold text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-foreground">{value}</p>
      {detail ? <p className="mt-1 text-xs text-muted-foreground">{detail}</p> : null}
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-l border-border pl-3">
      <p className="text-[0.68rem] font-semibold uppercase tracking-[0.12em] text-muted-foreground">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

function CountPill({
  value,
  tone = "default",
}: {
  value: number;
  tone?: "default" | "primary" | "success";
}) {
  return (
    <ProfilePill className={cn("h-auto min-w-9 px-2 py-1 text-sm tabular-nums", countToneClass(tone))}>
      {value}
    </ProfilePill>
  );
}

function ProfilePill({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-5 w-fit shrink-0 items-center justify-center overflow-hidden whitespace-nowrap rounded-full border border-border px-2 py-0.5 text-xs font-semibold text-foreground",
        className,
      )}
    >
      {children}
    </span>
  );
}

function countToneClass(tone: "default" | "primary" | "success"): string {
  switch (tone) {
    case "primary":
      return "bg-info-ink/10 text-info-ink";
    case "success":
      return "status-success-soft";
    default:
      return "bg-muted text-foreground";
  }
}

function formatDate(value: string | null | undefined): string {
  return formatRomanianDate(value);
}

function formatScore(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}
