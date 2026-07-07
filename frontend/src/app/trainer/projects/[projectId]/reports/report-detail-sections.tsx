import Link from "next/link";

import type { CompanyAssignment, CompanyParticipant } from "@/api/companies";
import type { ScoringResultRecord } from "@/api/trainer";
import {
  driverLabels,
  type ReportAverage,
  type TeamLens,
} from "@/app/trainer/companies/[companyId]/reports/report-aggregation";
import { ScaledBar } from "@/components/reports/native-charts";

export const MIN_REPORT_COHORT_SIZE = 3;

const distressDriverKeys = new Set(["distress_drivers", "distress_drivers_en"]);
const completedStatusesForReports = new Set(["submitted", "validated", "scored"]);

type DriverIndividualResult = {
  assignmentId: string;
  participantName: string;
  participantEmail: string;
  targetLabel: string;
  submittedAt: string | null;
  scores: ReportAverage[];
};

export function LencioniTeamBreakdown({ teams, overviewHref }: { teams: TeamLens[]; overviewHref: string }) {
  const teamsWithData = teams.filter((team) => team.lencioniCount > 0);

  return (
    <section id="lencioni-pe-echipe" className="rounded-xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <div className="flex flex-col gap-3 border-b border-[var(--border)] pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold text-burgundy/75">Lencioni pe echipe</p>
          <h2 className="mt-1 text-xl font-semibold text-foreground">Detaliu pe structura proiectului</h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/58">
            Afișăm scorurile pe echipe doar când există cel puțin {MIN_REPORT_COHORT_SIZE} răspunsuri pentru instrument.
          </p>
        </div>
        <Link
          href={overviewHref}
          className="tap-soft inline-flex justify-center rounded-full border border-[var(--border)] bg-surface-muted px-4 py-2 text-sm font-bold text-foreground/70 hover:bg-surface"
        >
          Înapoi la sumar
        </Link>
      </div>

      {teamsWithData.length === 0 ? (
        <p className="py-8 text-center text-sm text-foreground/52">Nu există încă rezultate Lencioni pe echipe.</p>
      ) : (
        <div className="mt-5 grid gap-4 xl:grid-cols-2">
          {teamsWithData.map((team) => (
            <article key={team.id} className="rounded-xl border border-[var(--border)] bg-background p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="font-semibold text-foreground">{team.name}</h3>
                  <p className="mt-1 text-xs text-foreground/52">
                    {team.memberCount} membri · {formatResponseCount(team.lencioniCount)} Lencioni
                  </p>
                </div>
                <span className="rounded-full bg-burgundy/10 px-2.5 py-1 text-xs font-bold text-burgundy">
                  {team.completionRate}%
                </span>
              </div>
              <div className="mt-4">
                {team.lencioniCount >= MIN_REPORT_COHORT_SIZE ? (
                  <TeamAverages
                    title="Lencioni"
                    count={team.lencioniCount}
                    items={team.lencioniAverages}
                    max={10}
                    valueLabel="0-10"
                  />
                ) : (
                  <SuppressedTeamSection title="Lencioni" count={team.lencioniCount} />
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export function DriverDetailBreakdown({
  teams,
  individuals,
  overviewHref,
}: {
  teams: TeamLens[];
  individuals: DriverIndividualResult[];
  overviewHref: string;
}) {
  const teamsWithDriverData = teams.filter((team) => team.driverCount > 0);

  return (
    <section id="driveri-detaliu" className="rounded-xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <div className="flex flex-col gap-3 border-b border-[var(--border)] pb-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold text-burgundy/75">Driveri de distres</p>
          <h2 className="mt-1 text-xl font-semibold text-foreground">Detaliu pe echipe și persoane</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/58">
            Driverii sunt autoevaluări individuale. Pe echipe afișăm agregate doar când există cel puțin {MIN_REPORT_COHORT_SIZE} răspunsuri; pe persoane afișăm scoruri calculate, nu răspunsurile brute.
          </p>
        </div>
        <Link
          href={overviewHref}
          className="tap-soft inline-flex justify-center rounded-full border border-[var(--border)] bg-surface-muted px-4 py-2 text-sm font-bold text-foreground/70 hover:bg-surface"
        >
          Înapoi la sumar
        </Link>
      </div>

      <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(24rem,0.9fr)]">
        <div>
          <div className="mb-3">
            <p className="text-xs font-semibold uppercase tracking-[0.1em] text-foreground/48">Pe echipe</p>
            <p className="mt-1 text-sm text-foreground/58">Agregate utile pentru comparații între structurile proiectului.</p>
          </div>
          {teamsWithDriverData.length === 0 ? (
            <p className="rounded-xl border border-[var(--border)] bg-surface-muted px-4 py-6 text-center text-sm text-foreground/52">
              Nu există încă rezultate de driveri asociate echipelor proiectului.
            </p>
          ) : (
            <div className="space-y-4">
              {teamsWithDriverData.map((team) => (
                <article key={team.id} className="rounded-xl border border-[var(--border)] bg-background p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <h3 className="font-semibold text-foreground">{team.name}</h3>
                      <p className="mt-1 text-xs text-foreground/52">
                        {team.memberCount} membri · {formatResponseCount(team.driverCount)} driveri
                      </p>
                    </div>
                    <span className="rounded-full bg-burgundy/10 px-2.5 py-1 text-xs font-bold text-burgundy">
                      {team.completionRate}%
                    </span>
                  </div>
                  <div className="mt-4">
                    {team.driverCount >= MIN_REPORT_COHORT_SIZE ? (
                      <TeamAverages
                        title="Driveri de distres"
                        count={team.driverCount}
                        items={team.driverAverages}
                        max={100}
                        suffix="%"
                        description="Toți driverii sunt afișați; interpretarea apare doar pentru valorile peste 50%."
                      />
                    ) : (
                      <SuppressedTeamSection title="Driveri de distres" count={team.driverCount} />
                    )}
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>

        <div>
          <div className="mb-3">
            <p className="text-xs font-semibold uppercase tracking-[0.1em] text-foreground/48">Pe persoane</p>
            <p className="mt-1 text-sm text-foreground/58">Scoruri individuale calculate pentru debrief, fără răspunsuri brute.</p>
          </div>
          {individuals.length === 0 ? (
            <p className="rounded-xl border border-[var(--border)] bg-surface-muted px-4 py-6 text-center text-sm text-foreground/52">
              Nu există încă autoevaluări de driveri scorate.
            </p>
          ) : (
            <div className="space-y-4">
              {individuals.map((item) => (
                <article key={item.assignmentId} className="rounded-xl border border-[var(--border)] bg-background p-4">
                  <div className="flex flex-col gap-1 border-b border-[var(--border)] pb-3">
                    <h3 className="font-semibold text-foreground">{item.participantName}</h3>
                    <p className="text-xs text-foreground/52">{item.participantEmail}</p>
                    <p className="text-xs font-semibold text-foreground/48">
                      {item.targetLabel} · {formatDate(item.submittedAt)}
                    </p>
                  </div>
                  <div className="mt-3 space-y-3">
                    {item.scores.map((score) => (
                      <div key={score.id}>
                        <div className="flex justify-between gap-3 text-xs font-semibold text-foreground/68">
                          <span>{score.label}</span>
                          <span className="shrink-0">{score.avg}%</span>
                        </div>
                        {score.interpretation ? (
                          <p className="mt-1 text-xs leading-5 text-foreground/52">
                            {score.range_label ? `${score.range_label}: ` : ""}
                            {score.interpretation}
                          </p>
                        ) : null}
                        <ScaledBar value={score.avg} max={100} />
                      </div>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

export function buildDriverIndividualResults(
  assignments: CompanyAssignment[],
  resultMap: Map<string, ScoringResultRecord>,
  participants: CompanyParticipant[],
): DriverIndividualResult[] {
  const participantById = new Map(participants.map((participant) => [participant.id, participant]));

  return assignments
    .filter((assignment) => completedStatusesForReports.has(assignment.status) && distressDriverKeys.has(assignment.questionnaire_key))
    .flatMap((assignment) => {
      const result = resultMap.get(assignment.id);
      if (!result?.scores) return [];
      const participant = participantById.get(assignment.respondent_profile_id);
      const scores = Object.entries(driverLabels).map(([id, label]) => {
        const score = extractNumericScore(result.scores[id]);
        return {
          id,
          label,
          avg: score,
          ...(score > 50
            ? {
                interpretation: "Driver prezent peste pragul de atenție; merită explorat în debrief.",
                range_label: ">50",
              }
            : {
                interpretation: null,
                range_label: null,
              }),
        };
      });

      return [
        {
          assignmentId: assignment.id,
          participantName: participant?.full_name ?? "Participant necunoscut",
          participantEmail: participant?.email ?? "Email indisponibil",
          targetLabel: assignment.target_type === "self" ? "Autoevaluare" : "Evaluare individuală",
          submittedAt: assignment.submitted_at,
          scores,
        },
      ];
    })
    .sort((first, second) => (second.submittedAt ?? "").localeCompare(first.submittedAt ?? ""));
}

function TeamAverages({
  title,
  count,
  items,
  max,
  suffix = "",
  valueLabel,
  description,
}: {
  title: string;
  count: number;
  items: ReportAverage[];
  max: number;
  suffix?: string;
  valueLabel?: string;
  description?: string;
}) {
  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-foreground/48">{title}</p>
        <span className="text-xs font-semibold text-foreground/52">{formatResponseCount(count)}</span>
      </div>
      {description ? <p className="mt-2 text-xs leading-5 text-foreground/52">{description}</p> : null}
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-foreground/52">Nu există încă rezultate scorate pentru echipă.</p>
      ) : (
        <div className="mt-3 space-y-3">
          {items.map((item) => (
            <div key={item.id}>
              <div className="flex justify-between gap-3 text-xs font-semibold text-foreground/68">
                <span>{item.label}</span>
                <span className="shrink-0">
                  {item.avg}
                  {suffix}
                  {valueLabel ? ` / ${valueLabel}` : ""}
                </span>
              </div>
              {item.interpretation ? (
                <p className="mt-1 text-xs leading-5 text-foreground/52">
                  {item.range_label ? `${item.range_label}: ` : ""}
                  {item.interpretation}
                </p>
              ) : null}
              <ScaledBar value={item.avg} max={max} />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function SuppressedTeamSection({ title, count }: { title: string; count: number }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-surface-muted p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.1em] text-foreground/48">{title}</p>
        <span className="text-xs font-semibold text-foreground/52">{formatResponseCount(count)}</span>
      </div>
      <p className="mt-3 text-xs font-semibold leading-5 text-foreground/58">
        Ascuns până există cel puțin {MIN_REPORT_COHORT_SIZE} răspunsuri.
      </p>
    </div>
  );
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  return new Date(value).toLocaleDateString("ro-RO");
}

function formatResponseCount(count: number): string {
  return count === 1 ? "1 răspuns" : `${count} răspunsuri`;
}

function extractNumericScore(value: unknown): number {
  const raw = typeof value === "object" && value !== null && "score" in value ? (value as { score?: unknown }).score : value;
  if (typeof raw === "number" && Number.isFinite(raw)) return Number(raw.toFixed(1));
  if (typeof raw === "string" && raw.trim() !== "") {
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? Number(parsed.toFixed(1)) : 0;
  }
  return 0;
}
