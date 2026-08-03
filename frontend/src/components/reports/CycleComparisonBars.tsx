import { Card } from "@/components/ui/card";
import { InterpretationDisclosure } from "@/components/reports/InterpretationDisclosure";
import { ResultSignalBadge } from "@/components/reports/ResultSignalBadge";
import { cn } from "@/utils/cn";

export type CycleComparisonValue = {
  cycleId: string;
  cycleLabel: string;
  color: string;
  value: number;
  valueLabel?: string;
  status?: "watch" | "ok";
};

export type CycleComparisonRow = {
  id: string;
  label: string;
  values: CycleComparisonValue[];
  note?: string | null;
};

export type CycleDistributionSeries = {
  cycleId: string;
  cycleLabel: string;
  segments: Array<{
    id: string;
    label: string;
    value: number;
    color: string;
  }>;
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function formatValue(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function formatDelta(value: number, unit: "pp" | "points"): string {
  const magnitude = formatValue(Math.abs(value));
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}${magnitude} ${unit === "pp" ? "pp" : Math.abs(value) === 1 ? "punct" : "puncte"}`;
}

export function CycleComparisonBars({
  title,
  rows,
  min = 0,
  max,
  suffix = "",
  empty = "Nu există încă rezultate comparabile.",
  deltaUnit,
  higherIsBetter,
}: {
  title: string;
  rows: CycleComparisonRow[];
  min?: number;
  max: number;
  suffix?: string;
  empty?: string;
  deltaUnit?: "pp" | "points";
  higherIsBetter?: boolean;
}) {
  const range = max - min;

  return (
    <Card asChild className="h-full gap-0 border-border/80 px-5 shadow-none [--card-spacing:--spacing(5)]">
      <article>
        <h3 className="text-base font-semibold tracking-tight text-foreground">{title}</h3>
        {rows.length > 0 ? (
          <div className="mt-5 grid gap-7">
            {rows.map((row) => (
              <section key={row.id} aria-label={row.label}>
                <h4 className="text-sm font-semibold text-foreground">
                  {row.label}
                </h4>
                <dl className="mt-3 grid gap-3.5">
                  {row.values.map((item, index) => {
                    const position = range > 0
                      ? clamp(((item.value - min) / range) * 100, 0, 100)
                      : 0;
                    const previous = row.values[index - 1];
                    const delta = previous ? item.value - previous.value : null;
                    const improved = delta !== null && delta !== 0 && higherIsBetter !== undefined
                      ? (delta > 0) === higherIsBetter
                      : null;

                    return (
                      <div
                        key={item.cycleId}
                        className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-2"
                      >
                        <dt className="truncate text-xs font-medium text-muted-foreground">{item.cycleLabel}</dt>
                        <dd className="flex min-w-0 flex-wrap items-center justify-end gap-x-2 gap-y-1 font-mono text-sm font-semibold tabular-nums text-foreground">
                          <span className="whitespace-nowrap">{item.valueLabel ?? `${formatValue(item.value)}${suffix}`}</span>
                          {delta !== null && deltaUnit ? (
                            <span
                              className={cn(
                                "whitespace-nowrap text-[0.68rem] font-semibold",
                                improved === true && "text-emerald-500",
                                improved === false && "text-destructive",
                                improved === null && "text-muted-foreground",
                              )}
                            >
                              {formatDelta(delta, deltaUnit)}
                            </span>
                          ) : null}
                          {item.status ? (
                            <ResultSignalBadge status={item.status} className="font-sans" />
                          ) : null}
                        </dd>
                        <div className="col-span-2 min-w-0" aria-hidden="true" data-cycle-comparison-plot>
                          <span
                            data-cycle-line
                            className="block h-1.5 min-w-px rounded-full"
                            style={{ backgroundColor: item.color, width: `${position}%` }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </dl>
                {row.note ? (
                  <InterpretationDisclosure className="text-xs">{row.note}</InterpretationDisclosure>
                ) : null}
              </section>
            ))}
          </div>
        ) : (
          <p className="mt-5 text-sm text-muted-foreground">{empty}</p>
        )}
      </article>
    </Card>
  );
}

export function CycleDistributionPies({
  title,
  series,
  empty = "Nu există încă distribuții comparabile.",
}: {
  title: string;
  series: CycleDistributionSeries[];
  empty?: string;
}) {
  return (
    <Card asChild className="h-full gap-0 border-border/80 px-5 shadow-none [--card-spacing:--spacing(5)]">
      <article>
        <h3 className="text-base font-semibold tracking-tight text-foreground">{title}</h3>
        {series.some((cycle) => cycle.segments.some((segment) => segment.value > 0)) ? (
          <div className="mt-5 grid gap-6 sm:grid-cols-2 sm:gap-0">
              {series.map((cycle) => {
                const total = cycle.segments.reduce((sum, segment) => sum + segment.value, 0);
                let cursor = 0;
                const visibleSegments = cycle.segments
                  .filter((segment) => segment.value > 0)
                  .map((segment) => {
                    const start = total > 0 ? (cursor / total) * 100 : 0;
                    cursor += segment.value;
                    const end = total > 0 ? (cursor / total) * 100 : 0;
                    return { ...segment, start, end, share: Math.round(((segment.value / total) * 100) || 0) };
                  });
                const summary = visibleSegments
                  .filter((segment) => segment.value > 0)
                  .map((segment) => `${segment.label}: ${segment.value}, ${segment.share}%`)
                  .join("; ");
                const background = visibleSegments.length > 0
                  ? `conic-gradient(${visibleSegments.map((segment) => `${segment.color} ${segment.start}% ${segment.end}%`).join(", ")})`
                  : "var(--muted)";
                return (
                  <section
                    key={cycle.cycleId}
                    className="min-w-0 border-border sm:border-l sm:px-5 sm:first:border-l-0 sm:first:pl-0 sm:last:pr-0"
                  >
                    <h4 className="text-sm font-semibold text-foreground">{cycle.cycleLabel}</h4>
                    <div className="mt-4 grid grid-cols-[7rem_minmax(0,1fr)] items-center gap-4">
                      <div
                        className="relative size-28 shrink-0 rounded-full ring-1 ring-border"
                        role="img"
                        aria-label={`${cycle.cycleLabel}. ${summary || empty}`}
                        data-distribution-pie={cycle.cycleId}
                        style={{ background }}
                      >
                        <span className="absolute inset-4 flex flex-col items-center justify-center rounded-full bg-surface text-center" aria-hidden="true">
                          <span className="font-mono text-2xl font-semibold tabular-nums text-foreground">{total}</span>
                          <span className="text-[0.62rem] font-semibold uppercase tracking-[0.14em] text-muted-foreground">total</span>
                        </span>
                      </div>
                      {visibleSegments.length > 0 ? (
                        <ul className="grid min-w-0 gap-2.5">
                          {visibleSegments.map((segment) => (
                            <li key={segment.id} className="grid min-w-0 grid-cols-[minmax(0,1fr)_auto] items-start gap-2 text-xs">
                              <span className="flex min-w-0 items-start gap-2 text-muted-foreground">
                                <span className="mt-0.5 size-2.5 shrink-0 rounded-full" style={{ backgroundColor: segment.color }} aria-hidden="true" />
                                <span>{segment.label}</span>
                              </span>
                              <span className="shrink-0 font-mono font-semibold tabular-nums text-foreground">
                                {segment.value} {segment.value === 1 ? "participant" : "participanți"} · {segment.share}%
                              </span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-xs leading-5 text-muted-foreground">{empty}</p>
                      )}
                    </div>
                  </section>
                );
              })}
          </div>
        ) : (
          <p className="mt-5 text-sm text-muted-foreground">{empty}</p>
        )}
      </article>
    </Card>
  );
}
