import type { ReactNode } from "react";

type EmptyStateProps = {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
};

export function EmptyState({ title, description, icon, action, className = "" }: EmptyStateProps) {
  return (
    <div className={`rounded-xl border border-[var(--border)] bg-surface px-5 py-6 text-center shadow-sm ${className}`}>
      {icon ? (
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-cream-100 text-lg">
          {icon}
        </div>
      ) : null}
      <p className="text-base font-semibold text-foreground">{title}</p>
      {description ? <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-foreground/65">{description}</p> : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  );
}
