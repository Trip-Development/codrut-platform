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
    <article className="bento-card p-6 relative">
      <div className="relative z-10">
        <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-foreground/45">{label}</p>
        <div className={`mt-3 flex items-baseline gap-1.5 ${toneClasses[tone]}`}>
          <CountUp value={value} className="font-display text-4xl font-bold tracking-tight" />
          {suffix ? <span className="text-sm font-bold opacity-80">{suffix}</span> : null}
        </div>
        <p className="mt-3 text-xs leading-relaxed text-foreground/60">{detail}</p>
      </div>
    </article>
  );
}
