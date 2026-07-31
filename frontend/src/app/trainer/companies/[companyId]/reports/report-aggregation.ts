import { managerReferenceKey, normalizeReportsToName } from "@/api/roster-format";
import type { CompanyAssignment, CompanyParticipant, ReportScoreScale, ReportTeamLens } from "@/api/companies";
import { formatPcmLabel, getPcmColor } from "@/api/pcm";
import type { ScoringResultRecord } from "@/api/trainer";

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
  lencioniScale?: ReportScoreScale | null;
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

export function adaptReportTeamLenses(teamLenses: ReportTeamLens[]): TeamLens[] {
  return teamLenses.map((team) => ({
    id: team.id,
    name: team.name,
    memberCount: team.member_count,
    assignedCount: team.assigned_count,
    completedCount: team.completed_count,
    completionRate: team.completion_rate,
    lencioniCount: team.lencioni_count,
    driverCount: team.driver_count,
    boss360Count: team.boss_360_count,
    pcmBaseCount: team.pcm_base_count,
    pcmPhaseCount: team.pcm_phase_count,
    lencioniAverages: team.lencioni_averages,
    lencioniScale: team.lencioni_scale,
    driverAverages: team.driver_averages,
    boss360Averages: team.boss_360_averages,
    pcmBaseDistribution: team.pcm_base_distribution.map((item) => ({ ...item, color: item.color ?? undefined })),
    pcmPhaseDistribution: team.pcm_phase_distribution.map((item) => ({ ...item, color: item.color ?? undefined })),
  }));
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
  const lencioni = summarizeCategory(reportableAssignments, resultMap, lencioniKeys);
  const drivers = summarizeCategory(reportableAssignments, resultMap, distressDriverKeys);
  const boss360 = summarizeCategory(reportableAssignments, resultMap, boss360Keys);

  return {
    lencioniCount: lencioni.count,
    driverCount: drivers.count,
    boss360Count: boss360.count,
    lencioniAverages: lencioni.averages,
    driverAverages: drivers.averages,
    boss360Averages: boss360.averages,
  };
}

function summarizeCategory(
  assignments: CompanyAssignment[],
  resultMap: Map<string, ScoringResultRecord | null>,
  questionnaireKeys: Set<string>,
): { count: number; averages: ReportAverage[] } {
  const dimensions = new Map<string, { label: string; total: number; count: number }>();
  let count = 0;

  for (const assignment of assignments) {
    if (!questionnaireKeys.has(assignment.questionnaire_key)) continue;
    const scores = resultMap.get(assignment.id)?.scores;
    if (!scores) continue;
    let hasScore = false;
    for (const [id, value] of Object.entries(scores)) {
      const score = numericScore(value);
      if (score === null) continue;
      const current = dimensions.get(id) ?? {
        label: scoreLabel(id, value),
        total: 0,
        count: 0,
      };
      current.total += score;
      current.count += 1;
      dimensions.set(id, current);
      hasScore = true;
    }
    if (hasScore) count += 1;
  }

  return {
    count,
    averages: [...dimensions.entries()].map(([id, dimension]) => ({
      id,
      label: dimension.label,
      avg: Number((dimension.total / dimension.count).toFixed(1)),
      interpretation: null,
      range_label: null,
    })),
  };
}

function numericScore(value: unknown): number | null {
  const raw = typeof value === "object" && value !== null && "score" in value ? (value as { score?: unknown }).score : value;
  return typeof raw === "number" && Number.isFinite(raw) ? raw : null;
}

function scoreLabel(id: string, value: unknown): string {
  if (typeof value === "object" && value !== null && "label" in value) {
    const label = (value as { label?: unknown }).label;
    if (typeof label === "string" && label.trim()) return label.trim();
  }
  return id
    .replace(/_/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toLocaleUpperCase("ro-RO") + part.slice(1))
    .join(" ");
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
    participants.map((participant) => [managerReferenceKey(participant.full_name), participant]),
  );
  const teamsById = new Map<string, { id: string; name: string; memberIds: Set<string> }>();
  const directReportsByManagerId = new Map<string, CompanyParticipant[]>();
  const rootIds = new Set<string>();
  const managerIds = new Set<string>();

  for (const participant of participants) {
    const managerName = normalizeReportsToName(participant.reports_to_name);
    const manager = managerName ? participantByName.get(managerReferenceKey(managerName)) : null;
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
    const key = managerReferenceKey(label);
    if (!key) continue;
    const existing = names.get(key);
    names.set(key, { label: existing?.label ?? label, count: (existing?.count ?? 0) + 1 });
  }

  const referencedManagerNames = new Set(
    participants
      .map((participant) => normalizeReportsToName(participant.reports_to_name))
      .filter((name): name is string => Boolean(name))
      .map((name) => managerReferenceKey(name))
      .filter((key) => Boolean(key)),
  );

  for (const [key, item] of names) {
    if (item.count > 1 && referencedManagerNames.has(key)) return item.label;
  }

  return null;
}
