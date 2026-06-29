type ChartDatum = {
  id: string;
  label: string;
  value: number;
  color?: string;
};

const defaultColors = ["#7f1d1d", "#0f766e", "#b45309", "#1d4ed8", "#6d28d9", "#be123c", "#15803d"];

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
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
      <div className="relative mx-auto h-32 w-32" role="img" aria-label={title}>
        <svg viewBox="0 0 120 120" className="h-32 w-32 -rotate-90">
          <circle cx="60" cy="60" r={radius} fill="none" stroke="rgba(34, 24, 20, 0.08)" strokeWidth="18" />
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
        <div className="space-y-2">
          {visibleData.map((item, index) => (
            <div key={item.id} className="flex items-center justify-between gap-3 text-sm">
              <span className="flex min-w-0 items-center gap-2 text-foreground/72">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ backgroundColor: item.color ?? defaultColors[index % defaultColors.length] }}
                />
                <span className="truncate">{item.label}</span>
              </span>
              <span className="font-semibold text-foreground">{item.value}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-foreground/52">{emptyLabel}</p>
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
      <div className={`h-full rounded-full ${colorClassName}`} style={{ width: `${width}%` }} />
    </div>
  );
}
