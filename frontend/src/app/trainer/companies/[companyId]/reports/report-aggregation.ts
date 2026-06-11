import type { CompanyAssignment } from "@/api/companies";
import type { ScoringResultRecord } from "@/api/trainer";

export const lencioniLabels: Record<string, string> = {
  absence_of_trust: "Absența încrederii (Trust)",
  fear_of_conflict: "Teama de conflict (Conflict)",
  lack_of_commitment: "Lipsa angajamentului (Commitment)",
  avoidance_of_accountability: "Evitarea responsabilității (Accountability)",
  inattention_to_results: "Neatenția la rezultate (Results)",
};

export const driverLabels: Record<string, string> = {
  be_strong: "Fii Puternic (Be Strong)",
  be_perfect: "Fii Perfect (Be Perfect)",
  try_hard: "Străduiește-te (Try Hard)",
  hurry_up: "Grăbește-te (Hurry Up)",
  please_people: "Mulțumește-i pe alții (Please People)",
};

const completedStatuses = new Set(["submitted", "validated", "scored"]);

export type ReportAverage = {
  id: string;
  label: string;
  avg: number;
};

export type ReportAggregation = {
  reportableAssignments: CompanyAssignment[];
  lencioniCount: number;
  driverCount: number;
  lencioniAverages: ReportAverage[];
  driverAverages: ReportAverage[];
  totalAssigned: number;
  totalCompleted: number;
  completionRate: number;
};

export function buildReportAggregation(
  assignments: CompanyAssignment[],
  resultMap: Map<string, ScoringResultRecord | null>,
): ReportAggregation {
  const reportableAssignments = assignments
    .filter((assignment) => completedStatuses.has(assignment.status))
    .sort((first, second) => (second.submitted_at ?? "").localeCompare(first.submitted_at ?? ""));

  const lencioniSums = zeroRecord(lencioniLabels);
  const driverSums = zeroRecord(driverLabels);
  let lencioniCount = 0;
  let driverCount = 0;

  for (const assignment of reportableAssignments) {
    const result = resultMap.get(assignment.id);
    if (!result?.scores) continue;

    if (assignment.questionnaire_key === "lencioni") {
      lencioniCount += 1;
      for (const key of Object.keys(lencioniSums)) {
        const value = result.scores[key];
        const score = typeof value === "object" && value !== null ? (value as { score?: unknown }).score : value;
        lencioniSums[key] += Number(score || 0);
      }
    } else if (assignment.questionnaire_key === "distress_drivers") {
      driverCount += 1;
      for (const key of Object.keys(driverSums)) {
        driverSums[key] += Number(result.scores[key] || 0);
      }
    }
  }

  const totalAssigned = assignments.length;
  const totalCompleted = reportableAssignments.length;

  return {
    reportableAssignments,
    lencioniCount,
    driverCount,
    lencioniAverages: averagesFromSums(lencioniSums, lencioniLabels, lencioniCount),
    driverAverages: averagesFromSums(driverSums, driverLabels, driverCount),
    totalAssigned,
    totalCompleted,
    completionRate: totalAssigned > 0 ? Math.round((totalCompleted / totalAssigned) * 100) : 0,
  };
}

function zeroRecord(labels: Record<string, string>): Record<string, number> {
  return Object.fromEntries(Object.keys(labels).map((key) => [key, 0]));
}

function averagesFromSums(
  sums: Record<string, number>,
  labels: Record<string, string>,
  count: number,
): ReportAverage[] {
  return Object.entries(sums).map(([key, sum]) => ({
    id: key,
    label: labels[key] || key,
    avg: Number((count > 0 ? sum / count : 0).toFixed(1)),
  }));
}
