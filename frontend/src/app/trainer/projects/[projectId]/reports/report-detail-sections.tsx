import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowLeftIcon } from "lucide-react";

import type { CompanyAssignment, CompanyParticipant } from "@/api/companies";
import type { ScoringResultRecord } from "@/api/trainer";
import type {
  ReportAverage,
  TeamLens,
} from "@/app/trainer/companies/[companyId]/reports/report-aggregation";
import { ScaledBar } from "@/components/reports/native-charts";
import { formatRomanianDate } from "@/utils/date-format";

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
    <section id="lencioni-pe-echipe" className="flex flex-col gap-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <h2 className="text-xl font-semibold text-foreground">Lencioni pe echipe</h2>
        <BackLink href={overviewHref} />
      </div>

      {teamsWithData.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">Nu există încă rezultate Lencioni pe echipe.</p>
      ) : (
        <div className="grid gap-4 xl:grid-cols-2">
          {teamsWithData.map((team) => (
            <ReportSurface key={team.id}>
              <ReportHeader action={<ReportBadge>{team.completionRate}%</ReportBadge>}>
                <ReportTitle>{team.name}</ReportTitle>
                <ReportDescription>
                  {team.memberCount} membri / {formatResponseCount(team.lencioniCount)} Lencioni
                </ReportDescription>
              </ReportHeader>
              <ReportContent>
                <TeamAverages
                  title="Lencioni"
                  count={team.lencioniCount}
                  items={team.lencioniAverages}
                  max={10}
                  valueLabel="0-10"
                />
              </ReportContent>
            </ReportSurface>
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
    <section id="driveri-detaliu" className="flex flex-col gap-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <h2 className="text-xl font-semibold text-foreground">Driveri de distres</h2>
        <BackLink href={overviewHref} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(24rem,0.9fr)]">
        <div>
          <div className="mb-3">
            <h3 className="text-sm font-semibold text-foreground">Pe echipe</h3>
          </div>
          {teamsWithDriverData.length === 0 ? (
            <ReportSurface as="p" className="px-4 py-6 text-center text-sm text-muted-foreground">
              Nu există încă rezultate de driveri asociate echipelor proiectului.
            </ReportSurface>
          ) : (
            <div className="flex flex-col gap-4">
              {teamsWithDriverData.map((team) => (
                <ReportSurface key={team.id}>
                  <ReportHeader action={<ReportBadge>{team.completionRate}%</ReportBadge>}>
                    <ReportTitle>{team.name}</ReportTitle>
                    <ReportDescription>
                      {team.memberCount} membri / {formatResponseCount(team.driverCount)} driveri
                    </ReportDescription>
                  </ReportHeader>
                  <ReportContent>
                    <TeamAverages
                      title="Driveri de distres"
                      count={team.driverCount}
                      items={team.driverAverages}
                      max={100}
                      suffix="%"
                    />
                  </ReportContent>
                </ReportSurface>
              ))}
            </div>
          )}
        </div>

        <div>
          <div className="mb-3">
            <h3 className="text-sm font-semibold text-foreground">Pe persoane</h3>
          </div>
          {individuals.length === 0 ? (
            <ReportSurface as="p" className="px-4 py-6 text-center text-sm text-muted-foreground">
              Nu există încă autoevaluări de driveri scorate.
            </ReportSurface>
          ) : (
            <div className="flex flex-col gap-4">
              {individuals.map((item) => (
                <ReportSurface key={item.assignmentId}>
                  <ReportHeader>
                    <ReportTitle>{item.participantName}</ReportTitle>
                    <ReportDescription>{item.participantEmail}</ReportDescription>
                    <ReportDescription className="font-semibold">
                      {item.targetLabel} / {formatDate(item.submittedAt)}
                    </ReportDescription>
                  </ReportHeader>
                  <ReportContent className="flex flex-col gap-3">
                    {item.scores.map((score) => (
                      <div key={score.id}>
                        <div className="flex justify-between gap-3 text-xs font-semibold text-muted-foreground">
                          <span>{score.label}</span>
                          <span className="shrink-0">{score.avg}%</span>
                        </div>
                        {score.interpretation ? (
                          <p className="mt-1 text-xs leading-5 text-muted-foreground">
                            {score.range_label ? `${score.range_label}: ` : ""}
                            {score.interpretation}
                          </p>
                        ) : null}
                        <ScaledBar value={score.avg} max={100} />
                      </div>
                    ))}
                  </ReportContent>
                </ReportSurface>
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
      const scores = Object.entries(result.scores)
        .flatMap(([id, value]) => {
          const score = extractNumericScore(value);
          if (score === null) return [];
          return [{
            id,
            label: extractScoreLabel(id, value),
            avg: score,
            interpretation: extractScoreInterpretation(value),
            range_label: null,
          }];
        })
        .sort((first, second) => second.avg - first.avg);

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

function extractScoreLabel(id: string, value: unknown): string {
  if (typeof value === "object" && value !== null && "label" in value) {
    const label = (value as { label?: unknown }).label;
    if (typeof label === "string" && label.trim()) return label.trim();
  }
  return id
    .replace(/_/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toLocaleUpperCase("ro-RO") + part.slice(1))
    .join(" ");
}

function extractScoreInterpretation(value: unknown): string | null {
  if (typeof value !== "object" || value === null || !("interpretation" in value)) {
    return null;
  }
  const interpretation = (value as { interpretation?: unknown }).interpretation;
  return typeof interpretation === "string" && interpretation.trim()
    ? interpretation.trim()
    : null;
}

function TeamAverages({
  title,
  count,
  items,
  max,
  suffix = "",
  valueLabel,
}: {
  title: string;
  count: number;
  items: ReportAverage[];
  max: number;
  suffix?: string;
  valueLabel?: string;
}) {
  return (
    <div>
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">{title}</p>
        <span className="text-xs font-semibold text-muted-foreground">{formatResponseCount(count)}</span>
      </div>
      {items.length === 0 ? (
        <p className="mt-4 text-sm text-muted-foreground">Nu există încă rezultate scorate pentru echipă.</p>
      ) : (
        <div className="mt-3 flex flex-col gap-3">
          {items.map((item) => (
            <div key={item.id}>
              <div className="flex justify-between gap-3 text-xs font-semibold text-muted-foreground">
                <span>{item.label}</span>
                <span className="shrink-0">
                  {item.avg}
                  {suffix}
                  {valueLabel ? ` / ${valueLabel}` : ""}
                </span>
              </div>
              {item.interpretation ? (
                <p className="mt-1 text-xs leading-5 text-muted-foreground">
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

function BackLink({ href }: { href: string }) {
  return (
    <Link
      href={href}
      className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-md px-2 text-sm font-semibold text-muted-foreground outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/45"
    >
      <ArrowLeftIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
      Înapoi la sumar
    </Link>
  );
}

function ReportSurface({
  as: Component = "article",
  children,
  className,
}: {
  as?: "article" | "p";
  children: ReactNode;
  className?: string;
}) {
  return (
    <Component
      className={cx(
        "flex flex-col gap-3 overflow-hidden rounded-lg border bg-surface py-3 text-sm text-card-foreground",
        className,
      )}
    >
      {children}
    </Component>
  );
}

function ReportHeader({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className={cx("grid auto-rows-min items-start gap-1 rounded-t-lg px-3", action ? "grid-cols-[1fr_auto]" : null)}>
      <div>{children}</div>
      {action ? <div className="col-start-2 row-span-2 row-start-1 self-start justify-self-end">{action}</div> : null}
    </div>
  );
}

function ReportTitle({ children }: { children: ReactNode }) {
  return <div className="font-heading text-sm leading-snug font-medium">{children}</div>;
}

function ReportDescription({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx("text-sm text-muted-foreground", className)}>{children}</div>;
}

function ReportContent({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx("px-3", className)}>{children}</div>;
}

function ReportBadge({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex h-5 w-fit shrink-0 items-center justify-center overflow-hidden whitespace-nowrap rounded-full border border-transparent bg-secondary px-2 py-0.5 text-xs font-semibold text-secondary-foreground">
      {children}
    </span>
  );
}

function cx(...classes: Array<string | null | undefined | false>): string {
  return classes.filter(Boolean).join(" ");
}

function formatDate(value: string | null | undefined): string {
  return formatRomanianDate(value);
}

function formatResponseCount(count: number): string {
  return count === 1 ? "1 răspuns" : `${count} răspunsuri`;
}

function extractNumericScore(value: unknown): number | null {
  const raw = typeof value === "object" && value !== null && "score" in value ? (value as { score?: unknown }).score : value;
  if (typeof raw === "number" && Number.isFinite(raw)) return Number(raw.toFixed(1));
  if (typeof raw === "string" && raw.trim() !== "") {
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? Number(parsed.toFixed(1)) : null;
  }
  return null;
}
