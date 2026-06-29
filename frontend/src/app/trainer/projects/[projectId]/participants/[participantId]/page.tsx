import Link from "next/link";
import { notFound } from "next/navigation";

import { getCompanyDetail, getCompanyReportAggregate } from "@/api/companies";
import { formatPcmLabel, getPcmProfile } from "@/api/pcm";
import { getServerApiRequestOptions } from "@/api/server-request";
import { getProjectWorkspaceData } from "../../project-data";
import {
  buildParticipantProjectHistory,
  buildParticipantResultSummaries,
  countPrivateFeedbackGiven,
  countPrivateFeedbackReceived,
} from "./participant-profile-data";

type TrainerParticipantReportPageProps = {
  params: Promise<{ projectId: string; participantId: string }>;
};

export default async function TrainerParticipantReportPage({ params }: TrainerParticipantReportPageProps) {
  const { projectId, participantId } = await params;
  const requestOptions = await getServerApiRequestOptions();
  const { project, participants, assignments: projectAssignments } = await getProjectWorkspaceData(projectId, requestOptions);
  const participant = participants.find((item) => item.id === participantId);

  if (!participant) {
    notFound();
  }

  const [companyDetail, aggregate] = await Promise.all([
    getCompanyDetail(project.company_id, requestOptions),
    getCompanyReportAggregate(project.company_id, requestOptions),
  ]);

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
    <div className="space-y-5">
      <Link href={`/trainer/projects/${project.id}/participants`} className="btn-secondary inline-flex !h-10 !px-4 !py-0 text-sm">
        Înapoi la participanți
      </Link>

      <section className="surface-panel p-5 md:p-6">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-burgundy/75">Profil participant</p>
            <h2 className="mt-2 font-display text-3xl font-semibold text-foreground">{participant.full_name}</h2>
            <p className="mt-2 break-words text-sm font-semibold text-foreground/62">{participant.email}</p>
          </div>
          <div className="grid gap-2 text-sm sm:grid-cols-2 lg:min-w-96">
            <ProfileFact label="Poziție" value={participant.position ?? "Necompletată"} />
            <ProfileFact label="Manager" value={participant.reports_to_name ?? "Fără manager"} />
            <ProfileFact label="Bază PCM" value={formatPcmLabel(participant.pcm_base ?? participant.pcm_profile)} color={pcmBase?.color} />
            <ProfileFact label="Fază PCM" value={formatPcmLabel(participant.pcm_phase)} color={pcmPhase?.color} />
          </div>
        </div>
      </section>

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Asignări proiect" value={currentAssignments.length} detail={`${completedCount} completate`} />
        <MetricCard label="Scorate" value={scoredCount} detail="Chestionare cu rezultat calculat" />
        <MetricCard label="Feedback oferit" value={feedbackGivenCount} detail="360 către alte persoane, fără scoruri brute" />
        <MetricCard label="Feedback primit" value={feedbackReceivedCount} detail="Evaluări 360 primite, agregate în rezultate" />
      </section>

      <section className="surface-panel overflow-hidden">
        <div className="border-b border-[var(--border)] px-5 py-4">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-burgundy/75">Istoric proiecte</p>
          <h2 className="mt-1 text-xl font-semibold text-foreground">Unde apare participantul</h2>
          <p className="mt-2 text-sm leading-6 text-foreground/62">
            Istoricul este calculat din asignările companiei. Identitățile similare din alte companii vor avea nevoie de conectare explicită ulterior.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="data-table min-w-full text-left text-sm">
            <thead>
              <tr>
                <th>Proiect</th>
                <th>Asignări</th>
                <th>Completate</th>
                <th>Scorate</th>
                <th>360 oferit/primit</th>
                <th>Ultima activitate</th>
              </tr>
            </thead>
            <tbody>
              {historyRows.length > 0 ? (
                historyRows.map((row) => (
                  <tr key={row.projectId}>
                    <td className="font-semibold text-foreground">{row.projectName}</td>
                    <td>{row.assignedCount}</td>
                    <td>{row.completedCount}</td>
                    <td>{row.scoredCount}</td>
                    <td>{row.feedbackGivenCount}/{row.feedbackReceivedCount}</td>
                    <td>{formatDate(row.lastActivityAt)}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="px-5 py-6 text-center text-foreground/62">
                    Nu există încă istoric de proiect pentru acest participant.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="surface-panel p-5 md:p-6">
        <div className="max-w-3xl">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-burgundy/75">Rezultate sumarizate</p>
          <h2 className="mt-1 text-xl font-semibold text-foreground">Rezultate de chestionar, fără răspunsuri brute</h2>
          <p className="mt-2 text-sm leading-6 text-foreground/62">
            Afișăm doar scoruri calculate la nivel de chestionar. Feedbackul 360 oferit altor persoane rămâne ascuns aici ca să nu expună răspunsuri individuale.
          </p>
        </div>
        {resultSummaries.length > 0 ? (
          <div className="mt-5 grid gap-3 lg:grid-cols-2">
            {resultSummaries.map((result) => (
              <article key={result.assignmentId} className="rounded-xl border border-[var(--border)] bg-surface-muted p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h3 className="text-sm font-bold text-foreground">{result.questionnaireLabel}</h3>
                    <p className="mt-1 text-xs font-semibold text-foreground/52">{result.targetLabel}</p>
                  </div>
                  <span className="status-pill">{formatDate(result.completedAt)}</span>
                </div>
                <div className="mt-4 grid gap-2 sm:grid-cols-3">
                  <MiniStat label="Dimensiuni" value={String(result.dimensionCount)} />
                  <MiniStat label="Scor mediu" value={result.averageScore === null ? "N/A" : formatScore(result.averageScore)} />
                  <MiniStat label="Principal" value={result.primaryResultLabel ?? "N/A"} />
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="mt-5 rounded-xl border border-[var(--border)] bg-surface-muted px-4 py-3 text-sm text-foreground/62">
            Nu există rezultate calculate care pot fi afișate sumarizat pentru acest participant.
          </p>
        )}
      </section>
    </div>
  );
}

function ProfileFact({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-surface-muted px-4 py-3">
      <p className="text-[10px] font-bold uppercase tracking-wider text-foreground/45">{label}</p>
      <div className="mt-1 flex min-w-0 items-center gap-2">
        {color ? <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ backgroundColor: color }} /> : null}
        <p className="truncate text-sm font-semibold text-foreground">{value}</p>
      </div>
    </div>
  );
}

function MetricCard({ label, value, detail }: { label: string; value: number; detail: string }) {
  return (
    <article className="surface-panel p-5">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-foreground/45">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-burgundy">{value}</p>
      <p className="mt-2 text-sm leading-6 text-foreground/58">{detail}</p>
    </article>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-surface px-3 py-2">
      <p className="text-[10px] font-bold uppercase tracking-wider text-foreground/45">{label}</p>
      <p className="mt-1 truncate text-sm font-semibold text-foreground">{value}</p>
    </div>
  );
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  return new Intl.DateTimeFormat("ro-RO", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function formatScore(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}
