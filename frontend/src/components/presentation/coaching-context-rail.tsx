import type { ReactNode } from "react";

import { ArrowRightIcon } from "lucide-react";

import { cn } from "@/utils/cn";

/**
 * Component intent: orient a person in a sensitive workflow by connecting
 * current state, useful context, and the next meaningful action in one quiet
 * rail. It is shared by trainer operational lists and guided participant work.
 */
type CoachingContextRailProps = {
  eyebrow: string;
  title: string;
  detail: string;
  nextAction: string;
  action?: ReactNode;
  tone?: "brand" | "success" | "info";
};

const toneClasses = {
  brand: "bg-primary",
  success: "bg-success",
  info: "bg-info",
} as const;

export function CoachingContextRail({
  eyebrow,
  title,
  detail,
  nextAction,
  action,
  tone = "brand",
}: CoachingContextRailProps) {
  return (
    <aside
      aria-label="Contextul fluxului"
      className="grid gap-4 border-y border-border bg-surface-muted px-4 py-4 md:grid-cols-[minmax(0,1fr)_minmax(15rem,20rem)] md:items-center md:px-5"
    >
      <div className="min-w-0">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          {eyebrow}
        </p>
        <div className="mt-1.5 flex min-w-0 items-center gap-2">
          <span className={cn("size-2 shrink-0 rounded-full", toneClasses[tone])} aria-hidden="true" />
          <p className="truncate text-sm font-semibold text-foreground">{title}</p>
        </div>
        <p className="mt-1 max-w-2xl text-sm leading-5 text-muted-foreground">{detail}</p>
      </div>

      <div className="grid gap-2 border-t border-border pt-3 md:border-l md:border-t-0 md:pl-5 md:pt-0">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          Următorul pas
        </p>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="flex min-w-0 items-center gap-2 text-sm font-semibold text-foreground">
            <ArrowRightIcon className="size-4 shrink-0 text-primary" aria-hidden="true" strokeWidth={1.8} />
            <span className="truncate">{nextAction}</span>
          </p>
          {action}
        </div>
      </div>
    </aside>
  );
}
