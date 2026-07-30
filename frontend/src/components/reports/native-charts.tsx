import { cn } from "@/utils/cn";

type ChartDatum = {
  id: string;
  label: string;
  value: number;
  color?: string;
};

const defaultColors = [
  "var(--chart-1)",
  "var(--foreground)",
  "var(--brand-gray)",
  "var(--chart-2)",
  "var(--burgundy-dark)",
  "var(--success-ink)",
  "var(--muted-foreground)",
];

function stableColorForId(id: string): string {
  let hash = 2166136261;
  for (const character of id) {
    hash ^= character.codePointAt(0) ?? 0;
    hash = Math.imul(hash, 16777619);
  }
  return defaultColors[(hash >>> 0) % defaultColors.length];
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function peopleLabel(value: number): string {
  return `${value} ${value === 1 ? "persoană" : "persoane"}`;
}

function includedPeopleLabel(value: number): string {
  return `${peopleLabel(value)} ${value === 1 ? "inclusă" : "incluse"}`;
}

function percentage(value: number, total: number): number {
  return total > 0 ? Math.round((value / total) * 100) : 0;
}

export function ParticipantFrequencyPie({
  title,
  data,
  totalPeople,
  emptyLabel = "Nu există încă rezultate TA finalizate pentru această evaluare.",
}: {
  title: string;
  data: ChartDatum[];
  totalPeople: number;
  emptyLabel?: string;
}) {
  const total = Math.max(0, totalPeople);
  const visibleData = total > 0 ? data.filter((item) => item.value > 0) : [];
  let cursor = 0;
  const segments = visibleData.map((item) => {
    const start = clamp((cursor / total) * 100, 0, 100);
    cursor += item.value;
    const end = clamp((cursor / total) * 100, start, 100);
    const color = item.color ?? stableColorForId(item.id);
    return { ...item, color, start, end, share: percentage(item.value, total) };
  });
  const filledUntil = segments.at(-1)?.end ?? 0;
  const backgroundImage = total > 0 && segments.length > 0
    ? `conic-gradient(${[
        ...segments.map((item) => `${item.color} ${item.start}% ${item.end}%`),
        ...(filledUntil < 100 ? [`var(--muted) ${filledUntil}% 100%`] : []),
      ].join(", ")})`
    : undefined;
  const accessibleSummary = segments.length > 0
    ? segments
        .map((item) => `${item.label}: ${peopleLabel(item.value)}, ${item.share}%`)
        .join("; ")
    : emptyLabel;

  return (
    <figure className="grid gap-4 sm:grid-cols-[132px_1fr] sm:items-center">
      <div
        className="mx-auto size-32 rounded-full border border-border bg-muted"
        role="img"
        aria-label={`${title}. ${includedPeopleLabel(total)}. ${accessibleSummary}.`}
        style={{
          backgroundImage,
          printColorAdjust: "exact",
          WebkitPrintColorAdjust: "exact",
        }}
      />
      <figcaption>
        <p className="text-sm font-semibold text-foreground">{includedPeopleLabel(total)}</p>
        {segments.length > 0 ? (
          <ul className="mt-3 grid gap-2">
            {segments.map((item) => (
              <li key={item.id} className="flex items-start justify-between gap-3 text-sm">
                <span className="flex min-w-0 items-start gap-2 text-muted-foreground">
                  <span
                    aria-hidden="true"
                    className="mt-1 size-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: item.color }}
                  />
                  <span>{item.label}</span>
                </span>
                <span className="shrink-0 font-semibold tabular-nums text-foreground">
                  {peopleLabel(item.value)} · {item.share}%
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-3 text-sm leading-6 text-muted-foreground">{emptyLabel}</p>
        )}
      </figcaption>
    </figure>
  );
}

export function DonutChart({
  title,
  data,
  emptyLabel = "Nu există date",
}: {
  title: string;
  data: ChartDatum[];
  emptyLabel?: string;
}) {
  const visibleData = data.filter((item) => item.value > 0);
  const total = visibleData.reduce((sum, item) => sum + item.value, 0);
  const radius = 44;
  const circumference = 2 * Math.PI * radius;
  let offset = 0;

  return (
    <div className="grid gap-4 sm:grid-cols-[132px_1fr] sm:items-center">
      <div className="relative mx-auto size-32" role="img" aria-label={title}>
        <svg viewBox="0 0 120 120" className="size-32 -rotate-90">
          <circle cx="60" cy="60" r={radius} fill="none" stroke="var(--muted)" strokeWidth="18" />
          {total > 0
            ? visibleData.map((item, index) => {
                const fraction = item.value / total;
                const dash = fraction * circumference;
                const segment = (
                  <circle
                    key={item.id}
                    cx="60"
                    cy="60"
                    r={radius}
                    fill="none"
                    stroke={item.color ?? defaultColors[index % defaultColors.length]}
                    strokeDasharray={`${dash} ${circumference - dash}`}
                    strokeDashoffset={-offset}
                    strokeLinecap="butt"
                    strokeWidth="18"
                  />
                );
                offset += dash;
                return segment;
              })
            : null}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
          <span className="text-2xl font-semibold text-foreground">{total}</span>
          <span className="text-[11px] font-semibold uppercase text-foreground/48">total</span>
        </div>
      </div>
      {total > 0 ? (
        <div className="flex flex-col gap-2">
          {visibleData.map((item, index) => (
            <div key={item.id} className="flex items-center justify-between gap-3 text-sm">
              <span className="flex min-w-0 items-center gap-2 text-muted-foreground">
                <span
                  className="size-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: item.color ?? defaultColors[index % defaultColors.length] }}
                />
                <span className="truncate">{item.label}</span>
              </span>
              <span className="font-semibold text-foreground">{item.value}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">{emptyLabel}</p>
      )}
    </div>
  );
}

export function ScaledBar({
  value,
  max,
  colorClassName = "bg-burgundy",
}: {
  value: number;
  max: number;
  colorClassName?: string;
}) {
  const width = max > 0 ? clamp((value / max) * 100, 0, 100) : 0;

  return (
    <div className="mt-1.5 h-2 rounded-full bg-surface-muted" aria-hidden="true">
      <div className={cn("h-full rounded-full", colorClassName)} style={{ width: `${width}%` }} />
    </div>
  );
}
