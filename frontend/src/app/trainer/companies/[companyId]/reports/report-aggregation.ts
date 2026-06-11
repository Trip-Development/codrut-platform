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

export const boss360Labels: Record<string, string> = {
  inspiring: "Inspiring",
  create_trust: "Construirea încrederii",
  awareness: "Awareness",
  results: "Results",
  empowerment: "Empowerment",
};

const completedStatuses = new Set(["submitted", "validated", "scored"]);
const lencioniKeys = new Set(["lencioni", "lencioni_en"]);
const distressDriverKeys = new Set(["distress_drivers", "distress_drivers_en"]);
const boss360Keys = new Set(["boss_360", "boss_360_en", "icare"]);

export type ReportAverage = {
  id: string;
  label: string;
  avg: number;
};

export type ReportAggregation = {
  reportableAssignments: CompanyAssignment[];
  lencioniCount: number;
  driverCount: number;
  boss360Count: number;
  lencioniAverages: ReportAverage[];
  driverAverages: ReportAverage[];
  boss360Averages: ReportAverage[];
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
  const boss360Sums = zeroRecord(boss360Labels);
  let lencioniCount = 0;
  let driverCount = 0;
  let boss360Count = 0;

  for (const assignment of reportableAssignments) {
    const result = resultMap.get(assignment.id);
    if (!result?.scores) continue;

    if (lencioniKeys.has(assignment.questionnaire_key)) {
      lencioniCount += 1;
      for (const key of Object.keys(lencioniSums)) {
        const value = result.scores[key];
        const score = typeof value === "object" && value !== null ? (value as { score?: unknown }).score : value;
        lencioniSums[key] += Number(score || 0);
      }
    } else if (distressDriverKeys.has(assignment.questionnaire_key)) {
      driverCount += 1;
      for (const key of Object.keys(driverSums)) {
        driverSums[key] += Number(result.scores[key] || 0);
      }
    } else if (boss360Keys.has(assignment.questionnaire_key)) {
      boss360Count += 1;
      for (const key of Object.keys(boss360Sums)) {
        const value = result.scores[key];
        const score = typeof value === "object" && value !== null ? (value as { score?: unknown }).score : value;
        boss360Sums[key] += Number(score || 0);
      }
    }
  }

  const totalAssigned = assignments.length;
  const totalCompleted = reportableAssignments.length;

  return {
    reportableAssignments,
    lencioniCount,
    driverCount,
    boss360Count,
    lencioniAverages: averagesFromSums(lencioniSums, lencioniLabels, lencioniCount),
    driverAverages: averagesFromSums(driverSums, driverLabels, driverCount),
    boss360Averages: averagesFromSums(boss360Sums, boss360Labels, boss360Count),
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
