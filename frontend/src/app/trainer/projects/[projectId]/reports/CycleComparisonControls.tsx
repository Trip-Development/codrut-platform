"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

import type { AssessmentCycle } from "@/api/companies";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const CYCLE_STATUS_LABELS: Record<AssessmentCycle["status"], string> = {
  active: "În desfășurare",
  closed: "Finalizată",
  draft: "În pregătire",
};

const ALL_CYCLES_VALUE = "all";

export function CycleComparisonControls({
  cycles,
  cycleId,
}: {
  cycles: AssessmentCycle[];
  cycleId: string | null;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const orderedCycles = [...cycles].sort((left, right) => left.sequence - right.sequence);

  function selectCycle(value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value === ALL_CYCLES_VALUE) {
      params.delete("cycle");
    } else {
      params.set("cycle", value);
    }
    params.delete("baseline");
    params.delete("compare");
    const query = params.toString();
    router.push(query ? `${pathname}?${query}` : pathname);
  }

  return (
    <div className="flex flex-wrap items-end gap-3" aria-label="Alege evaluarea">
      <CycleSelect
        label="Evaluare"
        cycles={orderedCycles}
        value={cycleId ?? ALL_CYCLES_VALUE}
        onValueChange={selectCycle}
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
    <label className="grid w-full max-w-72 gap-1.5 text-xs font-semibold text-muted-foreground">
      {label}
      <Select value={value} onValueChange={onValueChange}>
        <SelectTrigger className="h-9 w-full bg-surface" aria-label={label}>
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL_CYCLES_VALUE}>Toate evaluările</SelectItem>
          {cycles.map((cycle) => (
            <SelectItem key={cycle.id} value={cycle.id}>
              {cycle.name} · {CYCLE_STATUS_LABELS[cycle.status]}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </label>
  );
}
