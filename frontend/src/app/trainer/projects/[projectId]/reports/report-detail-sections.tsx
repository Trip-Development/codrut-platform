import Link from "next/link";
import { ArrowLeftIcon } from "lucide-react";

import type { TeamLens } from "@/app/trainer/companies/[companyId]/reports/report-aggregation";
import { ScaledBar } from "@/components/reports/native-charts";

export function LencioniTeamBreakdown({
  teams,
  overviewHref,
}: {
  teams: TeamLens[];
  overviewHref: string;
}) {
  const teamsWithData = teams.filter((team) => team.lencioniCount > 0);

  return (
    <section id="lencioni-pe-echipe" className="flex flex-col gap-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-sm font-semibold text-burgundy">Lencioni</p>
          <h2 className="mt-1 text-2xl font-semibold tracking-tight text-foreground">Rezultate pe echipe</h2>
        </div>
        <Link
          href={overviewHref}
          className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-md px-2 text-sm font-semibold text-muted-foreground outline-none transition-colors hover:bg-muted hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring/45"
        >
          <ArrowLeftIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
          Înapoi la rezultatele proiectului
        </Link>
      </div>

      {teamsWithData.length === 0 ? (
        <p className="border-y border-border py-8 text-center text-sm text-muted-foreground">
          Nu există încă rezultate Lencioni pe echipe.
        </p>
      ) : (
        <div className="grid gap-5 xl:grid-cols-2">
          {teamsWithData.map((team) => (
            <article key={team.id} className="border-y border-border bg-surface px-5 py-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <h3 className="text-lg font-semibold text-foreground">{team.name}</h3>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {team.memberCount} membri · {formatResponseCount(team.lencioniCount)}
                  </p>
                </div>
                <span className="text-xs font-semibold text-muted-foreground">{team.completionRate}% completat</span>
              </div>
              <div className="mt-5 grid gap-4">
                {team.lencioniAverages.length > 0 ? (
                  team.lencioniAverages.map((item) => (
                    <div key={item.id}>
                      <div className="flex items-baseline justify-between gap-3 text-sm">
                        <span className="font-semibold text-foreground">{item.label}</span>
                        <span className="font-mono font-semibold tabular-nums text-foreground">{item.avg} / 10</span>
                      </div>
                      <ScaledBar value={item.avg} max={10} />
                      {item.interpretation ? (
                        <p className="mt-2 text-xs leading-5 text-muted-foreground">
                          {item.range_label ? `${item.range_label}: ` : ""}{item.interpretation}
                        </p>
                      ) : null}
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-muted-foreground">Nu există încă rezultate scorate pentru echipă.</p>
                )}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function formatResponseCount(count: number): string {
  return count === 1 ? "1 răspuns" : `${count} răspunsuri`;
}
