import type { ReportScoreScale } from "@/api/companies";

export type ResolvedReportScoreScale = {
  min: number;
  max: number;
  suffix: string;
  compatible: boolean;
};

export function resolveReportScoreScale(
  scale: ReportScoreScale | null | undefined,
  fallback: Omit<ResolvedReportScoreScale, "compatible">,
): ResolvedReportScoreScale {
  const compatible = scale?.score_scale_compatible !== false
    && scale?.unavailable_reason !== "incompatible_score_scales";
  const min = scale?.scale_min ?? fallback.min;
  const max = scale?.scale_max ?? fallback.max;

  if (scale?.score_unit === "percent") {
    return { min, max, suffix: "%", compatible };
  }
  if (scale?.score_unit === "grade_1_to_5") {
    return { min, max, suffix: ` din ${max}`, compatible };
  }
  if (scale?.score_unit && scale.scale_max != null) {
    return { min, max, suffix: ` / ${max}`, compatible };
  }
  return { ...fallback, compatible };
}

export function reportScaleEmptyCopy(
  scale: ReportScoreScale | null | undefined,
  fallback: string,
): string {
  if (
    scale?.score_scale_compatible === false
    || scale?.unavailable_reason === "incompatible_score_scales"
  ) {
    return "Aceste rezultate folosesc scale diferite și nu pot fi calculate împreună. Alege o singură evaluare.";
  }
  return fallback;
}
