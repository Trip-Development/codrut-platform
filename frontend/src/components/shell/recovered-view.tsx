import Link from "next/link";

type RecoveredMetric = {
  label: string;
  value: string;
  detail: string;
  tone?: "default" | "success" | "warning" | "danger";
};

type RecoveredSection = {
  title: string;
  description: string;
  items: string[];
};

type RecoveredAction = {
  label: string;
  href: string;
};

const toneClassName: Record<NonNullable<RecoveredMetric["tone"]>, string> = {
  default: "border-[var(--border)] bg-surface",
  success: "border-green-200 bg-green-50 text-green-900",
  warning: "border-amber-200 bg-amber-50 text-amber-950",
  danger: "border-red-200 bg-red-50 text-red-950",
};

type RecoveredViewProps = {
  metrics?: RecoveredMetric[];
  sections: RecoveredSection[];
  actions?: RecoveredAction[];
};

export function RecoveredView({ metrics = [], sections, actions = [] }: RecoveredViewProps) {
  return (
    <div className="space-y-4">
      {actions.length ? (
        <div className="flex flex-wrap gap-2">
          {actions.map((action) => (
            <Link
              key={action.href}
              href={action.href}
              className="tap-soft rounded-full border border-[var(--border)] bg-surface px-3 py-2 text-sm font-semibold text-foreground/75 hover:border-burgundy/50 hover:text-burgundy"
            >
              {action.label}
            </Link>
          ))}
        </div>
      ) : null}

      {metrics.length ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {metrics.map((metric) => (
            <article
              key={metric.label}
              className={[
                "rounded-2xl border p-5 shadow-sm",
                toneClassName[metric.tone ?? "default"],
              ].join(" ")}
            >
              <p className="text-xs font-bold uppercase tracking-[0.14em] opacity-70">{metric.label}</p>
              <p className="mt-3 text-3xl font-bold">{metric.value}</p>
              <p className="mt-2 text-sm leading-6 opacity-70">{metric.detail}</p>
            </article>
          ))}
        </div>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        {sections.map((section) => (
          <article key={section.title} className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
            <h2 className="text-lg font-bold text-foreground">{section.title}</h2>
            <p className="mt-2 text-sm leading-6 text-foreground/65">{section.description}</p>
            <ul className="mt-4 space-y-2">
              {section.items.map((item) => (
                <li key={item} className="rounded-xl border border-[var(--border)] bg-surface-muted px-3 py-2 text-sm text-foreground/75">
                  {item}
                </li>
              ))}
            </ul>
          </article>
        ))}
      </div>
    </div>
  );
}
