import { CountUp } from "./count-up";

type StatCardProps = {
  label: string;
  value: number;
  suffix?: string;
  detail: string;
  tone?: "default" | "success" | "warning" | "danger";
};

const toneClasses: Record<NonNullable<StatCardProps["tone"]>, string> = {
  default: "text-burgundy",
  success: "text-green-700",
  warning: "text-ochre-700",
  danger: "text-red-700",
};

export function StatCard({ label, value, suffix, detail, tone = "default" }: StatCardProps) {
  return (
    <article className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-foreground/50">{label}</p>
      <div className={`mt-2 flex items-baseline gap-2 ${toneClasses[tone]}`}>
        <CountUp value={value} className="font-display text-3xl font-semibold tracking-tight" />
        {suffix ? <span className="text-sm font-semibold">{suffix}</span> : null}
      </div>
      <p className="mt-2 text-sm leading-6 text-foreground/65">{detail}</p>
    </article>
  );
}
