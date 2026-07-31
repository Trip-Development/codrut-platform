"use client";

import { usePathname, useRouter, useSearchParams } from "next/navigation";

import type { AssessmentCycle } from "@/api/companies";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

const CYCLE_STATUS_LABELS: Record<AssessmentCycle["status"], string> = {
  active: "În desfășurare",
  closed: "Finalizată",
  draft: "În pregătire",
};

export function CycleComparisonControls({
  cycles,
  cycleId,
}: {
  cycles: AssessmentCycle[];
  cycleId: string;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const orderedCycles = [...cycles].sort((left, right) => left.sequence - right.sequence);

  function selectCycle(value: string) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("cycle", value);
    params.delete("baseline");
    params.delete("compare");
    router.push(`${pathname}?${params.toString()}`);
  }

  return (
    <div className="flex flex-wrap items-end gap-3" aria-label="Alege evaluarea">
      <CycleSelect
        label="Evaluare"
        cycles={orderedCycles}
        value={cycleId}
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
