import { normalizeReportsToName } from "@/api/roster-format";
import type { CompanyAssignment, CompanyParticipant, CompanyReportAggregate } from "@/api/companies";
import { formatPcmLabel, getPcmColor } from "@/api/pcm";
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
const pcmKeys = new Set(["pcm_base", "pcm_phase", "phase"]);

export type ReportAverage = {
  id: string;
  label: string;
  avg: number;
  interpretation?: string | null;
  range_label?: string | null;
};

export type ReportDistribution = {
  id: string;
  label: string;
  value: number;
  color?: string;
};

export type TeamLens = {
  id: string;
  name: string;
  memberCount: number;
  assignedCount: number;
  completedCount: number;
  completionRate: number;
  lencioniCount: number;
  driverCount: number;
  boss360Count: number;
  pcmBaseCount: number;
  pcmPhaseCount: number;
  lencioniAverages: ReportAverage[];
  driverAverages: ReportAverage[];
  boss360Averages: ReportAverage[];
  pcmBaseDistribution: ReportDistribution[];
  pcmPhaseDistribution: ReportDistribution[];
};

export type ReportAggregation = {
  reportableAssignments: CompanyAssignment[];
  lencioniCount: number;
  driverCount: number;
  boss360Count: number;
  pcmBaseCount: number;
  pcmPhaseCount: number;
  lencioniAverages: ReportAverage[];
  driverAverages: ReportAverage[];
  boss360Averages: ReportAverage[];
  pcmBaseDistribution: ReportDistribution[];
  pcmPhaseDistribution: ReportDistribution[];
  teamLenses: TeamLens[];
  hierarchyAmbiguous: boolean;
  hierarchyAmbiguityMessage?: string;
  totalAssigned: number;
  totalCompleted: number;
  completionRate: number;
};

export type ReportAggregationMismatch = {
  field:
    | "total_assigned"
    | "total_completed"
    | "lencioni_count"
    | "driver_count"
    | "boss_360_count"
    | "lencioni_averages"
    | "driver_averages"
    | "boss_360_averages";
};

export function buildReportAggregation(
  assignments: CompanyAssignment[],
  resultMap: Map<string, ScoringResultRecord | null>,
  participants: CompanyParticipant[] = [],
): ReportAggregation {
  const reportableAssignments = assignments
    .filter((assignment) => completedStatuses.has(assignment.status))
    .sort((first, second) => (second.submitted_at ?? "").localeCompare(first.submitted_at ?? ""));

  const scoreSummary = buildScoreSummary(reportableAssignments, resultMap);
  const totalAssigned = assignments.length;
  const totalCompleted = reportableAssignments.length;
  const pcmBaseDistribution = distributionFromCompletedPcmAssignments(participants, assignments, "pcm_base");
  const pcmPhaseDistribution = distributionFromCompletedPcmAssignments(participants, assignments, "pcm_phase");
  const teamLensResult = buildTeamLenses(participants, assignments, resultMap);

  return {
    reportableAssignments,
    ...scoreSummary,
    pcmBaseCount: distributionCount(pcmBaseDistribution),
    pcmPhaseCount: distributionCount(pcmPhaseDistribution),
    pcmBaseDistribution,
    pcmPhaseDistribution,
    teamLenses: teamLensResult.teamLenses,
    hierarchyAmbiguous: teamLensResult.hierarchyAmbiguous,
    hierarchyAmbiguityMessage: teamLensResult.hierarchyAmbiguityMessage,
    totalAssigned,
    totalCompleted,
    completionRate: totalAssigned > 0 ? Math.round((totalCompleted / totalAssigned) * 100) : 0,
  };
}

export function findReportAggregationMismatches(
  aggregate: CompanyReportAggregate,
  report: ReportAggregation,
): ReportAggregationMismatch[] {
  const mismatches: ReportAggregationMismatch[] = [];

  if (aggregate.total_assigned !== report.totalAssigned) {
    mismatches.push({ field: "total_assigned" });
  }
  if (aggregate.total_completed !== report.totalCompleted) {
    mismatches.push({ field: "total_completed" });
  }
  if (aggregate.lencioni_count !== report.lencioniCount) {
    mismatches.push({ field: "lencioni_count" });
  }
  if (aggregate.driver_count !== report.driverCount) {
    mismatches.push({ field: "driver_count" });
  }
  if (aggregate.boss_360_count !== report.boss360Count) {
    mismatches.push({ field: "boss_360_count" });
  }
  if (!reportAveragesMatch(aggregate.lencioni_averages, report.lencioniAverages)) {
    mismatches.push({ field: "lencioni_averages" });
  }
  if (!driverAveragesMatch(aggregate.driver_averages, report.driverAverages)) {
    mismatches.push({ field: "driver_averages" });
  }
  if (!reportAveragesMatch(aggregate.boss_360_averages, report.boss360Averages)) {
    mismatches.push({ field: "boss_360_averages" });
  }

  return mismatches;
}

function buildScoreSummary(
  reportableAssignments: CompanyAssignment[],
  resultMap: Map<string, ScoringResultRecord | null>,
): Pick<
  ReportAggregation,
  | "lencioniCount"
  | "driverCount"
  | "boss360Count"
  | "lencioniAverages"
  | "driverAverages"
  | "boss360Averages"
> {
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

  return {
    lencioniCount,
    driverCount,
    boss360Count,
    lencioniAverages: averagesFromSums(lencioniSums, lencioniLabels, lencioniCount, {
      interpretation: lencioniInterpretation,
    }),
    driverAverages: averagesFromSums(driverSums, driverLabels, driverCount, {
      interpretation: distressDriverInterpretation,
    }),
    boss360Averages: averagesFromSums(boss360Sums, boss360Labels, boss360Count),
  };
}

function zeroRecord(labels: Record<string, string>): Record<string, number> {
  return Object.fromEntries(Object.keys(labels).map((key) => [key, 0]));
}

function reportAveragesMatch(expected: ReportAverage[], actual: ReportAverage[]): boolean {
  if (expected.length !== actual.length) return false;

  return expected.every((item, index) => {
    const candidate = actual[index];
    return (
      candidate?.id === item.id &&
      candidate.avg === item.avg &&
      (candidate.interpretation ?? null) === (item.interpretation ?? null) &&
      (candidate.range_label ?? null) === (item.range_label ?? null)
    );
  });
}

function driverAveragesMatch(expected: ReportAverage[], actual: ReportAverage[]): boolean {
  return (
    reportAveragesMatch(expected, actual) ||
    reportAveragesMatch(
      expected,
      actual.filter((item) => item.avg > 50),
    )
  );
}

function averagesFromSums(
  sums: Record<string, number>,
  labels: Record<string, string>,
  count: number,
  options: {
    minimumAvg?: number;
    interpretation?: (score: number) => { label: string; range: string } | undefined;
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

function distressDriverInterpretation(score: number): { label: string; range: string } | undefined {
  if (score <= 50) return undefined;
  return {
    label: "Driver prezent peste pragul de atenție; merită explorat în debrief.",
    range: ">50",
  };
}

function distributionFromCompletedPcmAssignments(
  participants: CompanyParticipant[],
  assignments: CompanyAssignment[],
  field: "pcm_base" | "pcm_phase",
): ReportDistribution[] {
  const counts = new Map<string, number>();
  const participantsById = new Map(participants.map((participant) => [participant.id, participant]));
  const participantIdsWithCompletedPcm = new Set(
    assignments
      .filter((assignment) => completedStatuses.has(assignment.status) && pcmKeys.has(assignment.questionnaire_key))
      .map((assignment) => assignment.respondent_profile_id),
  );

  for (const participantId of participantIdsWithCompletedPcm) {
    const participant = participantsById.get(participantId);
    if (!participant) continue;
    const value = participant[field]?.trim();
    if (!value) continue;
    counts.set(value, (counts.get(value) ?? 0) + 1);
  }

  return [...counts.entries()]
    .map(([id, value]) => ({ id, label: formatPcmLabel(id), value, color: getPcmColor(id) }))
    .sort((first, second) => second.value - first.value || first.label.localeCompare(second.label));
}

function distributionCount(distribution: ReportDistribution[]): number {
  return distribution.reduce((total, item) => total + item.value, 0);
}

function buildTeamLenses(
  participants: CompanyParticipant[],
  assignments: CompanyAssignment[],
  resultMap: Map<string, ScoringResultRecord | null>,
): {
  teamLenses: TeamLens[];
  hierarchyAmbiguous: boolean;
  hierarchyAmbiguityMessage?: string;
} {
  const ambiguousName = findAmbiguousReferencedName(participants);
  if (ambiguousName) {
    return {
      teamLenses: [],
      hierarchyAmbiguous: true,
      hierarchyAmbiguityMessage: `Numele "${ambiguousName}" apare de mai multe ori în roster și este folosit ca manager.`,
    };
  }

  const participantByName = new Map(
    participants.map((participant) => [participant.full_name.trim().toLowerCase(), participant]),
  );
  const teamsById = new Map<string, { id: string; name: string; memberIds: Set<string> }>();
  const directReportsByManagerId = new Map<string, CompanyParticipant[]>();
  const rootIds = new Set<string>();
  const managerIds = new Set<string>();

  for (const participant of participants) {
    const managerName = normalizeReportsToName(participant.reports_to_name);
    const manager = managerName ? participantByName.get(managerName.toLowerCase()) : null;
    if (!manager) {
      rootIds.add(participant.id);
      continue;
    }

    managerIds.add(manager.id);
    const directReports = directReportsByManagerId.get(manager.id) ?? [];
    directReports.push(participant);
    directReportsByManagerId.set(manager.id, directReports);
  }

  for (const managerId of managerIds) {
    const manager = participants.find((participant) => participant.id === managerId);
    if (!manager) continue;
    const directReports = directReportsByManagerId.get(manager.id) ?? [];
    const rootLeadershipManager = rootIds.has(manager.id) && directReports.some((item) => managerIds.has(item.id));
    if (rootLeadershipManager && directReports.every((item) => managerIds.has(item.id))) continue;

    const teamId = `manager:${manager.id}`;
    const team = teamsById.get(teamId) ?? {
      id: teamId,
      name: `Echipa ${manager.full_name}`,
      memberIds: new Set<string>([manager.id]),
    };
    for (const directReport of directReports) {
      team.memberIds.add(directReport.id);
    }
    teamsById.set(teamId, team);
  }

  const leadershipIds = new Set(rootIds);
  for (const rootId of rootIds) {
    for (const directReport of directReportsByManagerId.get(rootId) ?? []) {
      if (isManagerLikeParticipant(directReport, managerIds)) leadershipIds.add(directReport.id);
    }
  }

  if (leadershipIds.size > 1 || rootIds.size > 1) {
    teamsById.set("leadership", {
      id: "leadership",
      name: "Leadership",
      memberIds: leadershipIds,
    });
  }

  const statsByTeamId = new Map<string, { assignedCount: number; completedCount: number }>();
  const completedAssignments = new Set(assignments.filter((assignment) => completedStatuses.has(assignment.status)).map((assignment) => assignment.id));

  for (const assignment of assignments) {
    for (const [teamId, team] of teamsById) {
      if (!team.memberIds.has(assignment.respondent_profile_id)) continue;
      const stats = statsByTeamId.get(teamId) ?? { assignedCount: 0, completedCount: 0 };
      stats.assignedCount += 1;
      if (completedAssignments.has(assignment.id)) stats.completedCount += 1;
      statsByTeamId.set(teamId, stats);
    }
  }

  const teamLenses = [...teamsById.values()]
    .map((team) => {
      const stats = statsByTeamId.get(team.id) ?? { assignedCount: 0, completedCount: 0 };
      const teamAssignments = assignments.filter((assignment) => team.memberIds.has(assignment.respondent_profile_id));
      const teamReportableAssignments = teamAssignments.filter((assignment) => completedStatuses.has(assignment.status));
      const scoreSummary = buildScoreSummary(teamReportableAssignments, resultMap);
      const teamParticipants = participants.filter((participant) => team.memberIds.has(participant.id));
      const pcmBaseDistribution = distributionFromCompletedPcmAssignments(teamParticipants, teamAssignments, "pcm_base");
      const pcmPhaseDistribution = distributionFromCompletedPcmAssignments(teamParticipants, teamAssignments, "pcm_phase");
      return {
        id: team.id,
        name: team.name,
        memberCount: team.memberIds.size,
        assignedCount: stats.assignedCount,
        completedCount: stats.completedCount,
        completionRate: stats.assignedCount > 0 ? Math.round((stats.completedCount / stats.assignedCount) * 100) : 0,
        ...scoreSummary,
        pcmBaseCount: distributionCount(pcmBaseDistribution),
        pcmPhaseCount: distributionCount(pcmPhaseDistribution),
        pcmBaseDistribution,
        pcmPhaseDistribution,
      };
    })
    .sort((first, second) => {
      if (first.id === "leadership") return -1;
      if (second.id === "leadership") return 1;
      return second.memberCount - first.memberCount || first.name.localeCompare(second.name);
    });

  return { teamLenses, hierarchyAmbiguous: false };
}

function isManagerLikeParticipant(participant: CompanyParticipant, managerIds: Set<string>): boolean {
  const role = participant.role_group?.trim().toLowerCase();
  return managerIds.has(participant.id) || role === "manager" || role === "leadership" || Boolean(participant.user_id);
}

function findAmbiguousReferencedName(participants: CompanyParticipant[]): string | null {
  const names = new Map<string, { label: string; count: number }>();
  for (const participant of participants) {
    const label = participant.full_name.trim();
    if (!label) continue;
    const key = label.toLowerCase();
    const existing = names.get(key);
    names.set(key, { label: existing?.label ?? label, count: (existing?.count ?? 0) + 1 });
  }

  const referencedManagerNames = new Set(
    participants
      .map((participant) => normalizeReportsToName(participant.reports_to_name))
      .filter((name): name is string => Boolean(name))
      .map((name) => name.toLowerCase()),
  );

  for (const [key, item] of names) {
    if (item.count > 1 && referencedManagerNames.has(key)) return item.label;
  }

  return null;
}
