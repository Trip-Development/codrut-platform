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
  icare_01_dezvolta_oamenii: "Dezvoltă oamenii",
  icare_02_conduce_prin_puterea_exemplului: "Conduce prin puterea exemplului",
  icare_03_creeaza_un_mediu_care_stimuleaza_implicarea: "Creează un mediu care stimulează implicarea",
  icare_04_promotor_al_colaborarii: "Promotor al colaborării",
  icare_05_ancorat_in_realitate: "Ancorat în realitate",
  icare_06_aduce_claritate: "Aduce claritate",
  icare_07_modestie: "Modestie",
  icare_08_inteligenta_emotionala_si_situationala: "Inteligență emoțională și situațională",
  icare_09_deschis_catre_lume: "Deschis către lume",
  icare_10_ambitios_pentru_companie: "Ambițios pentru companie",
  icare_11_grija_egala_pentru_angajati_si_clienti: "Grijă egală pentru angajați și clienți",
  icare_12_agilitate_antreprenoriala: "Agilitate antreprenorială",
  icare_13_decizii_cat_mai_aproape_de_teren: "Decizii cât mai aproape de teren",
  icare_14_cultiva_inteligenta_colectiva: "Cultivă inteligența colectivă",
  icare_15_ajuta_echipa: "Ajută echipa",
};

const lencioniInterpretations = [
  { min: 8, max: 9, range: "8-9", label: "Disfuncția probabil nu este o problemă." },
  { min: 6, max: 7.99, range: "6-7", label: "Disfuncția poate fi o problemă." },
  { min: 3, max: 5.99, range: "3-5", label: "Disfuncția trebuie probabil abordată." },
];

const completedStatuses = new Set(["submitted", "validated", "scored"]);
const lencioniKeys = new Set(["lencioni", "lencioni_en"]);
const distressDriverKeys = new Set(["distress_drivers", "distress_drivers_en"]);
const boss360Keys = new Set(["boss_360", "boss_360_en", "icare"]);

export type ReportAverage = {
  id: string;
  label: string;
  avg: number;
  interpretation?: string | null;
  range_label?: string | null;
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
    lencioniAverages: averagesFromSums(lencioniSums, lencioniLabels, lencioniCount, {
      interpretation: lencioniInterpretation,
    }),
    driverAverages: averagesFromSums(driverSums, driverLabels, driverCount, { minimumAvg: 50.0000001 }),
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
  options: {
    minimumAvg?: number;
    interpretation?: (score: number) => { label: string; range: string };
  } = {},
): ReportAverage[] {
  return Object.entries(sums).flatMap(([key, sum]) => {
    const avg = Number((count > 0 ? sum / count : 0).toFixed(1));
    if (options.minimumAvg !== undefined && avg < options.minimumAvg) return [];
    const interpretation = options.interpretation?.(avg);
    return [
      {
        id: key,
        label: labels[key] || key,
        avg,
        interpretation: interpretation?.label ?? null,
        range_label: interpretation?.range ?? null,
      },
    ];
  });
}

function lencioniInterpretation(score: number): { label: string; range: string } {
  const match = lencioniInterpretations.find((item) => item.min <= score && score <= item.max);
  if (match) return { label: match.label, range: match.range };
  if (score < 3) return { label: "Scor sub intervalul de referință Lencioni.", range: "<3" };
  return { label: "Scor peste intervalul de referință Lencioni.", range: ">9" };
}
