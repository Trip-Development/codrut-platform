"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { cn } from "@/utils/cn";

export type ReportCycleOption = {
  id: string;
  name: string;
  sequence: number;
  status: "active" | "closed" | "draft";
};

const CYCLE_STATUS_LABELS: Record<ReportCycleOption["status"], string> = {
  active: "În desfășurare",
  closed: "Finalizată",
  draft: "În pregătire",
};

const ALL_CYCLES_VALUE = "all";

export function CycleComparisonToolbar({
  cycles,
  cycleId,
  baselineId,
  compareId,
  className,
}: {
  cycles: ReportCycleOption[];
  cycleId?: string | null;
  baselineId: string;
  compareId: string;
  className?: string;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const orderedCycles = [...cycles].sort((left, right) => left.sequence - right.sequence);

  if (orderedCycles.length <= 1) return null;

  function navigate(mutator: (params: URLSearchParams) => void) {
    const params = new URLSearchParams(searchParams.toString());
    mutator(params);
    const query = params.toString();
    router.push(query ? `${pathname}?${query}` : pathname);
  }

  return (
    <div
      className={cn(
        "grid gap-3 rounded-lg border border-border/80 bg-muted/20 p-3 shadow-none",
        cycleId
          ? "w-full max-w-sm"
          : "md:grid-cols-[minmax(10rem,0.72fr)_minmax(0,1fr)] md:items-end",
        className,
      )}
      aria-label="Alege evaluarea"
    >
      <CycleSelect
        label="Evaluare"
        cycles={orderedCycles}
        value={cycleId ?? ALL_CYCLES_VALUE}
        includeAll
        onValueChange={(value) => navigate((params) => {
          if (value === ALL_CYCLES_VALUE) {
            params.delete("cycle");
            params.set("baseline", baselineId);
            params.set("compare", compareId);
          } else {
            params.set("cycle", value);
            params.delete("baseline");
            params.delete("compare");
          }
        })}
      />
      {!cycleId ? (
        <div className="grid min-w-0 gap-3 sm:grid-cols-2" aria-label="Compară două evaluări">
          <CycleSelect
            label="Evaluare de bază"
            cycles={orderedCycles}
            value={baselineId}
            excludedId={compareId}
            onValueChange={(value) => navigate((params) => {
              params.delete("cycle");
              params.set("baseline", value);
              params.set("compare", compareId);
            })}
          />
          <CycleSelect
            label="Evaluare comparată"
            cycles={orderedCycles}
            value={compareId}
            excludedId={baselineId}
            onValueChange={(value) => navigate((params) => {
              params.delete("cycle");
              params.set("baseline", baselineId);
              params.set("compare", value);
            })}
          />
        </div>
      ) : null}
    </div>
  );
}

function CycleSelect({
  label,
  cycles,
  value,
  onValueChange,
  includeAll = false,
  excludedId,
}: {
  label: string;
  cycles: ReportCycleOption[];
  value: string;
  onValueChange: (value: string) => void;
  includeAll?: boolean;
  excludedId?: string;
}) {
  return (
    <label className="grid w-full min-w-0 gap-1.5 text-[0.6875rem] font-semibold text-muted-foreground">
      {label}
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger className="h-10 w-full bg-control shadow-none" aria-label={label}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {includeAll ? <SelectItem value={ALL_CYCLES_VALUE}>Compară evaluări</SelectItem> : null}
          {cycles.map((cycle) => (
            <SelectItem key={cycle.id} value={cycle.id} disabled={cycle.id === excludedId}>
              {cycle.name} · {CYCLE_STATUS_LABELS[cycle.status]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </label>
  );
}
