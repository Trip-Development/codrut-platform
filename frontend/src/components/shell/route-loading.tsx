import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems, trainerNavItems } from "@/components/shell/nav";
import {
  CardsWorkspaceSkeleton,
  EditorWorkspaceSkeleton,
  TableWorkspaceSkeleton,
} from "@/components/shell/workspace-skeletons";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/utils/cn";

type TrainerLoadingKind = "dashboard" | "table" | "cards" | "editor" | "settings";
type ParticipantLoadingKind = "home" | "list" | "results" | "account";

export function TrainerRouteLoading({
  title,
  activeHref,
  kind,
  loadingLabel,
}: {
  title: string;
  activeHref: string;
  kind: TrainerLoadingKind;
  loadingLabel?: string;
}) {
  return (
    <AppShell
      audience="trainer"
      eyebrow=""
      title={title}
      description=""
      navItems={trainerNavItems}
      activeHref={activeHref}
    >
      <LoadingStatus label={loadingLabel ?? `Pregătim ${title.toLowerCase()}`} />
      {kind === "dashboard" ? <DashboardSkeleton /> : null}
      {kind === "table" ? <TableWorkspaceSkeleton /> : null}
      {kind === "cards" ? <CardsWorkspaceSkeleton /> : null}
      {kind === "editor" ? <EditorWorkspaceSkeleton /> : null}
      {kind === "settings" ? <SettingsSkeleton /> : null}
    </AppShell>
  );
}

export function ParticipantRouteLoading({
  title,
  activeHref,
  kind,
  loadingLabel,
}: {
  title: string;
  activeHref: string;
  kind: ParticipantLoadingKind;
  loadingLabel?: string;
}) {
  return (
    <AppShell
      audience="participant"
      eyebrow=""
      title={title}
      description=""
      navItems={participantNavItems}
      activeHref={activeHref}
      userLabel="Participant"
    >
      <LoadingStatus label={loadingLabel ?? `Pregătim ${title.toLowerCase()}`} />
      {kind === "home" ? <ParticipantHomeSkeleton /> : null}
      {kind === "list" ? <ParticipantListSkeleton /> : null}
      {kind === "results" ? <ParticipantResultsSkeleton /> : null}
      {kind === "account" ? <SettingsSkeleton compact /> : null}
    </AppShell>
  );
}

export function LoadingStatus({ label }: { label: string }) {
  return (
    <section
      role="status"
      aria-live="polite"
      aria-busy="true"
      className="mb-5 overflow-hidden rounded-lg border bg-surface px-4 py-3 shadow-sm"
    >
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm font-semibold text-foreground">{label}</p>
        <span className="text-xs font-semibold text-muted-foreground">Sincronizare</span>
      </div>
      <div className="mt-3 h-1 overflow-hidden rounded-full bg-muted">
        <div className="loading-bar-sweep h-full w-1/3 rounded-full bg-primary" />
      </div>
    </section>
  );
}

export function TabBarSkeleton({ count = 5 }: { count?: number }) {
  return (
    <nav className="mb-6 rounded-lg bg-surface p-2 shadow-sm ring-1 ring-border" aria-label="Pregătim navigarea">
      <div className="flex items-center gap-1 overflow-hidden">
        {Array.from({ length: count }).map((_, index) => (
          <Skeleton key={index} className="h-9 w-24 shrink-0" />
        ))}
      </div>
    </nav>
  );
}

export function CompanyDetailSkeleton() {
  return (
    <div className="flex flex-col gap-5">
      <section className="rounded-lg border bg-surface p-5 shadow-sm md:p-6">
        <Skeleton className="h-3 w-28" />
        <Skeleton className="mt-3 h-8 w-72 max-w-full" />
        <div className="mt-6 grid gap-3 md:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <MetricBlockSkeleton key={index} />
          ))}
        </div>
      </section>
      <section className="rounded-lg border bg-surface p-5 shadow-sm">
        <Skeleton className="h-5 w-44" />
        <div className="mt-5 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-44" />
          ))}
        </div>
      </section>
    </div>
  );
}

export function ProjectDetailSkeleton() {
  return (
    <div className="flex flex-col gap-5">
      <section className="rounded-lg bg-surface p-5 shadow-sm ring-1 ring-border">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="min-w-0">
            <Skeleton className="h-3 w-28" />
            <Skeleton className="mt-3 h-6 w-56 max-w-full" />
          </div>
          <Skeleton className="h-10 w-32" />
        </div>
        <div className="mt-6 grid gap-3 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <MetricBlockSkeleton key={index} />
          ))}
        </div>
      </section>
      <TableFrameSkeleton rows={4} />
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_26rem]">
        <section className="rounded-lg bg-primary p-6 text-primary-foreground shadow-[0_24px_60px_-36px_rgba(137,5,5,0.75)]">
          <Skeleton tone="inverted" className="h-7 w-80 max-w-full" />
          <Skeleton tone="inverted" className="mt-4 h-4 w-full max-w-2xl" />
          <Skeleton tone="inverted" className="mt-2 h-4 w-2/3" />
          <Skeleton tone="inverted" className="mt-6 h-10 w-40" />
        </section>
        <section className="rounded-lg bg-surface p-4 shadow-sm ring-1 ring-border">
          <div className="grid grid-cols-2 gap-3">
            {Array.from({ length: 4 }).map((_, index) => (
              <MetricBlockSkeleton key={index} />
            ))}
          </div>
        </section>
      </div>
      <TableFrameSkeleton rows={4} />
    </div>
  );
}

function SettingsSkeleton({ compact = false }: { compact?: boolean }) {
  return (
    <div className={cn("grid gap-5", compact ? "xl:grid-cols-[minmax(0,1fr)_20rem]" : "xl:grid-cols-[minmax(0,1fr)_24rem]")}>
      <section className="rounded-lg border bg-surface p-5 shadow-sm">
        <Skeleton className="h-5 w-48" />
        <div className="mt-5 grid gap-4 md:grid-cols-2">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="flex flex-col gap-2">
              <Skeleton className="h-3 w-24" />
              <Skeleton className="h-11 w-full" />
            </div>
          ))}
        </div>
        <Skeleton className="mt-6 h-10 w-40" />
      </section>
      <aside className="rounded-lg border bg-surface p-5 shadow-sm">
        <Skeleton className="h-5 w-36" />
        <div className="mt-5 flex flex-col gap-3">
          {Array.from({ length: 4 }).map((_, index) => (
            <MetricBlockSkeleton key={index} />
          ))}
        </div>
      </aside>
    </div>
  );
}

function ParticipantHomeSkeleton() {
  return (
    <div className="flex flex-col gap-5">
      <section className="rounded-lg bg-primary p-6 text-primary-foreground shadow-[0_24px_60px_-36px_rgba(137,5,5,0.75)]">
        <Skeleton tone="inverted" className="h-4 w-44" />
        <Skeleton tone="inverted" className="mt-3 h-8 w-72 max-w-full" />
        <Skeleton tone="inverted" className="mt-6 h-10 w-40" />
      </section>
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_22rem]">
        <TableFrameSkeleton rows={3} />
        <section className="rounded-lg border bg-surface p-4 shadow-sm">
          <div className="flex flex-col gap-3">
            {Array.from({ length: 4 }).map((_, index) => (
              <MetricBlockSkeleton key={index} />
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

function ParticipantListSkeleton() {
  return (
    <div className="grid gap-4 xl:grid-cols-3">
      {Array.from({ length: 3 }).map((_, index) => (
        <section key={index} className="rounded-lg border bg-surface p-5 shadow-sm">
          <Skeleton className="h-4 w-28" />
          <Skeleton className="mt-4 h-7 w-52 max-w-full" />
          <Skeleton className="mt-5 h-3 w-full" />
          <Skeleton className="mt-2 h-3 w-2/3" />
          <Skeleton className="mt-6 h-10 w-full" />
        </section>
      ))}
    </div>
  );
}

function ParticipantResultsSkeleton() {
  return (
    <div className="flex flex-col gap-5">
      <section className="rounded-lg border bg-surface p-5 shadow-sm">
        <Skeleton className="h-5 w-52" />
        <div className="mt-5 grid gap-3 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, index) => (
            <MetricBlockSkeleton key={index} />
          ))}
        </div>
      </section>
      <section className="rounded-lg border bg-surface p-5 shadow-sm">
        <Skeleton className="h-5 w-40" />
        <div className="mt-5 flex flex-col gap-3">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-20" />
          ))}
        </div>
      </section>
    </div>
  );
}

function TableFrameSkeleton({ rows }: { rows: number }) {
  return (
    <section className="overflow-hidden rounded-lg border bg-surface shadow-sm">
      <div className="border-b bg-muted/70 px-5 py-4">
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_10rem_10rem]">
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
        </div>
      </div>
      <div className="divide-y divide-border">
        {Array.from({ length: rows }).map((_, index) => (
          <div key={index} className="grid gap-4 px-5 py-4 lg:grid-cols-[minmax(0,1fr)_8rem_8rem_8rem]">
            <div className="min-w-0">
              <Skeleton className="h-4 w-60 max-w-full" />
              <Skeleton className="mt-2 h-3 w-40 max-w-full" />
            </div>
            <Skeleton className="h-7 w-full" />
            <Skeleton className="h-7 w-full" />
            <Skeleton className="h-7 w-full" />
          </div>
        ))}
      </div>
    </section>
  );
}

function MetricBlockSkeleton() {
  return (
    <div className="rounded-lg bg-muted px-4 py-3">
      <Skeleton tone="wash" className="h-3 w-24" />
      <Skeleton tone="wash" className="mt-3 h-7 w-16" />
    </div>
  );
}
