import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/utils/cn";

type WorkspaceSkeletonKind = "table" | "cards" | "editor" | "split";

export function WorkspaceSkeleton({
  kind,
  label,
  className,
}: {
  kind: WorkspaceSkeletonKind;
  label: string;
  className?: string;
}) {
  return (
    <section
      role="status"
      aria-live="polite"
      aria-label={label}
      className={cn("flex flex-col gap-5", className)}
    >
      <div className="overflow-hidden rounded-lg bg-surface p-4 shadow-sm ring-1 ring-border">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-foreground">{label}</p>
            <p className="mt-1 text-xs font-semibold text-muted-foreground">Pregătim spațiul de lucru</p>
          </div>
          <Skeleton className="h-9 w-28" />
        </div>
        <div className="mt-4 h-1 overflow-hidden rounded-full bg-muted">
          <div className="loading-bar-sweep h-full w-1/3 rounded-full bg-primary" />
        </div>
      </div>

      {kind === "table" ? <TableWorkspaceSkeleton /> : null}
      {kind === "cards" ? <CardsWorkspaceSkeleton /> : null}
      {kind === "editor" ? <EditorWorkspaceSkeleton /> : null}
      {kind === "split" ? <SplitWorkspaceSkeleton /> : null}
    </section>
  );
}

export function TableWorkspaceSkeleton() {
  return (
    <div className="flex flex-col gap-5">
      <section className="rounded-lg bg-surface p-4 shadow-sm ring-1 ring-border">
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_11rem_11rem_11rem]">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      </section>
      <section className="grid gap-3 xl:grid-cols-5">
        {Array.from({ length: 5 }).map((_, index) => (
          <MetricSkeleton key={index} />
        ))}
      </section>
      <section className="overflow-hidden rounded-lg bg-surface shadow-sm ring-1 ring-border">
        <div className="grid grid-cols-[2.5rem_minmax(15rem,1fr)_8rem_8rem_8rem_8rem_10rem] gap-0 border-b bg-muted/45 px-4 py-3">
          {Array.from({ length: 7 }).map((_, index) => (
            <Skeleton key={index} className="h-4" />
          ))}
        </div>
        <div className="divide-y divide-border">
          {Array.from({ length: 5 }).map((_, index) => (
            <div
              key={index}
              className="grid grid-cols-[2.5rem_minmax(15rem,1fr)_8rem_8rem_8rem_8rem_10rem] items-center gap-0 px-4 py-4"
            >
              <Skeleton className="size-4 rounded" />
              <div className="flex items-center gap-3">
                <Skeleton className="size-9" />
                <div className="min-w-0 flex-1">
                  <Skeleton className="h-4 w-44 max-w-full" />
                  <Skeleton className="mt-2 h-3 w-24" />
                </div>
              </div>
              {Array.from({ length: 5 }).map((__, metricIndex) => (
                <Skeleton key={metricIndex} className="h-5 w-14" />
              ))}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

export function CardsWorkspaceSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <section className="rounded-lg bg-surface p-4 shadow-sm ring-1 ring-border">
        <div className="grid gap-3 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <MetricSkeleton key={index} />
          ))}
        </div>
      </section>
      <section className="rounded-lg bg-surface p-4 shadow-sm ring-1 ring-border">
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_10rem_8rem_8rem]">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      </section>
      <div className="grid gap-5 xl:grid-cols-3">
        {Array.from({ length: 6 }).map((_, index) => (
          <Skeleton key={index} className="h-48" />
        ))}
      </div>
    </div>
  );
}

export function EditorWorkspaceSkeleton() {
  return (
    <div className="grid gap-5 xl:grid-cols-[18rem_minmax(0,1fr)]">
      <aside className="rounded-lg bg-surface p-4 shadow-sm ring-1 ring-border">
        <Skeleton className="h-10 w-full" />
        <div className="mt-4 flex flex-col gap-2">
          {Array.from({ length: 7 }).map((_, index) => (
            <Skeleton key={index} tone={index === 0 ? "wash" : "default"} className="h-14" />
          ))}
        </div>
      </aside>
      <section className="rounded-lg bg-surface p-5 shadow-sm ring-1 ring-border">
        <Skeleton className="h-7 w-72 max-w-full" />
        <Skeleton className="mt-4 h-4 w-full max-w-2xl" />
        <Skeleton className="mt-2 h-4 w-2/3" />
        <div className="mt-8 grid gap-4">
          {Array.from({ length: 5 }).map((_, index) => (
            <Skeleton key={index} className={index === 0 ? "h-32" : "h-20"} />
          ))}
        </div>
      </section>
    </div>
  );
}

export function SplitWorkspaceSkeleton() {
  return (
    <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_23rem]">
      <section className="rounded-lg bg-surface p-5 shadow-sm ring-1 ring-border">
        <Skeleton className="h-6 w-64 max-w-full" />
        <div className="mt-5 grid gap-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-16" />
          ))}
        </div>
      </section>
      <aside className="rounded-lg bg-surface p-5 shadow-sm ring-1 ring-border">
        <Skeleton className="h-5 w-40" />
        <div className="mt-5 grid gap-3">
          {Array.from({ length: 4 }).map((_, index) => (
            <MetricSkeleton key={index} />
          ))}
        </div>
      </aside>
    </div>
  );
}

function MetricSkeleton() {
  return (
    <div className="rounded-lg bg-muted/70 px-4 py-3">
      <Skeleton className="h-3 w-24" />
      <Skeleton className="mt-3 h-7 w-14" />
    </div>
  );
}
