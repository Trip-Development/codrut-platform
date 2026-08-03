"use client";

import type { AssessmentCycle } from "@/api/companies";
import { CycleComparisonToolbar } from "@/components/reports/CycleComparisonToolbar";

export function CycleComparisonControls({
  cycles,
  cycleId,
  baselineId,
  compareId,
}: {
  cycles: AssessmentCycle[];
  cycleId: string | null;
  baselineId: string;
  compareId: string;
}) {
  return (
    <CycleComparisonToolbar
      cycles={cycles}
      cycleId={cycleId}
      baselineId={baselineId}
      compareId={compareId}
    />
  );
}
