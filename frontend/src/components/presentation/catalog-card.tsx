import type { ReactNode } from "react";
import { ChevronRightIcon } from "lucide-react";

import { cn } from "@/utils/cn";

type CatalogStatusTone = "success" | "warning" | "neutral";

type CatalogCardProps = Omit<React.ComponentProps<"button">, "children" | "title"> & {
  eyebrow: ReactNode;
  version?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  metadata?: ReactNode;
  status?: {
    label: ReactNode;
    tone: CatalogStatusTone;
  };
};

const statusDotClasses: Record<CatalogStatusTone, string> = {
  success: "bg-success-ink",
  warning: "bg-warning-ink",
  neutral: "bg-muted-foreground",
};

/** Shared folio for trainer catalogs; navigation remains owned by each workspace. */
export function CatalogCard({
  eyebrow,
  version,
  title,
  description,
  metadata,
  status,
  className,
  ...props
}: CatalogCardProps) {
  return (
    <button
      type="button"
      data-slot="catalog-card"
      className={cn(
        "group relative flex h-full min-h-44 w-full min-w-0 flex-col overflow-hidden rounded-lg border border-border bg-surface p-4 text-left text-foreground outline-none transition-[background-color,border-color,box-shadow,transform] duration-150 hover:border-primary/25 hover:bg-surface-muted focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/45 focus-visible:ring-offset-2 focus-visible:ring-offset-background active:scale-[0.995] disabled:pointer-events-none disabled:opacity-50 motion-reduce:transition-none motion-reduce:active:transform-none md:min-h-48 md:p-5",
        className,
      )}
      {...props}
    >
      <div className="flex w-full items-start justify-between gap-4">
        <span className="rounded-md border border-primary/18 bg-primary/8 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-brand-text">
          {eyebrow}
        </span>
        {version ? (
          <span className="shrink-0 pt-1 text-xs font-medium tabular-nums text-muted-foreground">
            {version}
          </span>
        ) : null}
      </div>

      <div className="mt-4 min-w-0 pr-7">
        <span className="line-clamp-2 break-words text-base font-semibold leading-6 text-foreground">
          {title}
        </span>
        {description ? (
          <span className="mt-1.5 line-clamp-2 break-words text-sm leading-5 text-muted-foreground">
            {description}
          </span>
        ) : null}
      </div>

      <ChevronRightIcon
        aria-hidden="true"
        className="absolute right-4 top-1/2 size-4 -translate-y-1/2 text-muted-foreground opacity-55 transition-[opacity,transform] duration-150 group-hover:translate-x-0.5 group-hover:opacity-100 motion-reduce:transition-none"
        strokeWidth={1.8}
      />

      {(metadata != null || status != null) ? (
        <div className="mt-auto flex w-full min-w-0 items-end justify-between gap-3 border-t border-border/80 pt-3 text-xs text-muted-foreground">
          <div className="min-w-0">{metadata}</div>
          {status ? (
            <span className="inline-flex shrink-0 items-center gap-1.5 font-medium">
              <span
                aria-hidden="true"
                className={cn("size-1.5 rounded-full", statusDotClasses[status.tone])}
              />
              {status.label}
            </span>
          ) : null}
        </div>
      ) : null}
    </button>
  );
}

type CatalogToolbarProps = React.ComponentProps<"div">;

/** Shared search-and-primary-action frame for trainer catalogs. */
export function CatalogToolbar({ className, ...props }: CatalogToolbarProps) {
  return (
    <div
      data-slot="catalog-toolbar"
      className={cn(
        "flex flex-col gap-3 rounded-lg border border-border bg-surface p-3 text-foreground md:flex-row md:items-center",
        className,
      )}
      {...props}
    />
  );
}

export type { CatalogCardProps, CatalogStatusTone };
