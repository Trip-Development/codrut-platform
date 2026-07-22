"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

import type { AssessmentCycle } from "@/api/companies";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export function CycleComparisonControls({
  cycles,
  baselineCycleId,
  comparisonCycleId,
}: {
  cycles: AssessmentCycle[];
  baselineCycleId: string;
  comparisonCycleId: string;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const orderedCycles = [...cycles].sort((left, right) => left.sequence - right.sequence);
  const baseline = orderedCycles.find((cycle) => cycle.id === baselineCycleId);
  const comparison = orderedCycles.find((cycle) => cycle.id === comparisonCycleId);

  function selectCycle(key: "baseline" | "cycle", value: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set(key, value);
    router.push(`${pathname}?${params.toString()}`);
  }

  return (
    <div className="flex flex-wrap items-end gap-3" aria-label="Compară evaluări">
      <CycleSelect
        label="Referință"
        cycles={orderedCycles.filter(
          (cycle) => comparison === undefined || cycle.sequence < comparison.sequence,
        )}
        value={baselineCycleId}
        onValueChange={(value) => selectCycle("baseline", value)}
      />
      <CycleSelect
        label="Comparație"
        cycles={orderedCycles.filter(
          (cycle) => baseline === undefined || cycle.sequence > baseline.sequence,
        )}
        value={comparisonCycleId}
        onValueChange={(value) => selectCycle("cycle", value)}
      />
    </div>
  );
}

function CycleSelect({
  label,
  cycles,
  value,
  onValueChange,
}: {
  label: string;
  cycles: AssessmentCycle[];
  value: string;
  onValueChange: (value: string) => void;
}) {
  return (
    <label className="grid gap-1.5 text-xs font-semibold text-muted-foreground">
      {label}
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger className="h-9 w-52 bg-surface" aria-label={label}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {cycles.map((cycle) => (
            <SelectItem key={cycle.id} value={cycle.id}>
              {cycle.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </label>
  );
}
