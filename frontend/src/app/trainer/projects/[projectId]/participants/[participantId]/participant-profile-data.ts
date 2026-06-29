import type { CompanyAssignment, CompanyProject, CompanyScoringResult } from "@/api/companies";
import { inviteQuestionnaireLabel } from "@/api/invites";

const completedStatuses = new Set(["submitted", "validated", "scored"]);
const scoreBearingQuestionnaires = new Set([
  "lencioni",
  "lencioni_en",
  "distress_drivers",
  "distress_drivers_en",
  "boss_360",
  "boss_360_en",
  "icare",
]);

export type ParticipantProjectHistoryRow = {
  projectId: string;
  projectName: string;
  assignedCount: number;
  completedCount: number;
  scoredCount: number;
  feedbackGivenCount: number;
  feedbackReceivedCount: number;
  lastActivityAt: string | null;
};

export type ParticipantResultSummary = {
  assignmentId: string;
  questionnaireLabel: string;
  targetLabel: string;
  dimensionCount: number;
  averageScore: number | null;
  primaryResultLabel: string | null;
  completedAt: string | null;
};

export function buildParticipantProjectHistory({
  participantId,
  assignments,
  projects,
}: {
  participantId: string;
  assignments: CompanyAssignment[];
  projects: CompanyProject[];
}): ParticipantProjectHistoryRow[] {
  const projectById = new Map(projects.map((project) => [project.id, project]));
  const rowsByProject = new Map<string, ParticipantProjectHistoryRow>();

  for (const assignment of assignments) {
    if (!assignmentTouchesParticipant(assignment, participantId)) continue;
    const projectId = assignment.project_id ?? "no-project";
    const row = rowsByProject.get(projectId) ?? {
      projectId,
      projectName: projectById.get(projectId)?.name ?? "Fără proiect",
      assignedCount: 0,
      completedCount: 0,
      scoredCount: 0,
      feedbackGivenCount: 0,
      feedbackReceivedCount: 0,
      lastActivityAt: null,
    };

    row.assignedCount += 1;
    if (completedStatuses.has(assignment.status)) row.completedCount += 1;
    if (assignment.status === "scored" || assignment.scored_at) row.scoredCount += 1;
    if (isFeedbackGiven(assignment, participantId)) row.feedbackGivenCount += 1;
    if (isFeedbackReceived(assignment, participantId)) row.feedbackReceivedCount += 1;
    row.lastActivityAt = latestDate(row.lastActivityAt, assignment.scored_at, assignment.submitted_at, assignment.started_at, assignment.invited_at);
    rowsByProject.set(projectId, row);
  }

  return [...rowsByProject.values()].sort((first, second) => {
    const firstTime = first.lastActivityAt ? new Date(first.lastActivityAt).getTime() : 0;
    const secondTime = second.lastActivityAt ? new Date(second.lastActivityAt).getTime() : 0;
    return secondTime - firstTime || first.projectName.localeCompare(second.projectName, "ro-RO");
  });
}

export function buildParticipantResultSummaries({
  participantId,
  assignments,
  results,
}: {
  participantId: string;
  assignments: CompanyAssignment[];
  results: CompanyScoringResult[];
}): ParticipantResultSummary[] {
  const resultByAssignmentId = new Map(results.map((result) => [result.assignment_id, result]));

  return assignments
    .filter((assignment) => assignment.respondent_profile_id === participantId)
    .filter((assignment) => scoreBearingQuestionnaires.has(assignment.questionnaire_key))
    .filter((assignment) => !isPrivateFeedbackForAnotherPerson(assignment, participantId))
    .flatMap((assignment) => {
      const result = resultByAssignmentId.get(assignment.id);
      if (!result) return [];
      const scores = Object.values(result.scores).map(extractScore).filter((score): score is number => score !== null);
      return [
        {
          assignmentId: assignment.id,
          questionnaireLabel: inviteQuestionnaireLabel(assignment.questionnaire_key),
          targetLabel: targetLabelForAssignment(assignment, participantId),
          dimensionCount: scores.length,
          averageScore: scores.length > 0 ? Math.round((scores.reduce((sum, score) => sum + score, 0) / scores.length) * 10) / 10 : null,
          primaryResultLabel: result.primary_result ? prettifyScoreKey(result.primary_result) : null,
          completedAt: assignment.scored_at ?? assignment.submitted_at,
        },
      ];
    })
    .sort((first, second) => (second.completedAt ?? "").localeCompare(first.completedAt ?? ""));
}

export function countPrivateFeedbackGiven(assignments: CompanyAssignment[], participantId: string): number {
  return assignments.filter((assignment) => isFeedbackGiven(assignment, participantId)).length;
}

export function countPrivateFeedbackReceived(assignments: CompanyAssignment[], participantId: string): number {
  return assignments.filter((assignment) => isFeedbackReceived(assignment, participantId)).length;
}

function assignmentTouchesParticipant(assignment: CompanyAssignment, participantId: string): boolean {
  return assignment.respondent_profile_id === participantId || assignment.target_person_id === participantId;
}

function isPrivateFeedbackForAnotherPerson(assignment: CompanyAssignment, participantId: string): boolean {
  return assignment.target_type === "person" && assignment.target_person_id !== null && assignment.target_person_id !== participantId;
}

function isFeedbackGiven(assignment: CompanyAssignment, participantId: string): boolean {
  return assignment.respondent_profile_id === participantId && isPrivateFeedbackForAnotherPerson(assignment, participantId);
}

function isFeedbackReceived(assignment: CompanyAssignment, participantId: string): boolean {
  return assignment.target_type === "person" && assignment.target_person_id === participantId && assignment.respondent_profile_id !== participantId;
}

function targetLabelForAssignment(assignment: CompanyAssignment, participantId: string): string {
  if (assignment.target_type === "team") return "Echipă";
  if (assignment.target_type === "person" && assignment.target_person_id === participantId) return "Autoevaluare";
  if (assignment.target_type === "person") return "Feedback confidențial oferit";
  return "Autoevaluare";
}

function extractScore(value: unknown): number | null {
  const raw = typeof value === "object" && value !== null && "score" in value ? (value as { score?: unknown }).score : value;
  if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  if (typeof raw === "string" && raw.trim()) {
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function latestDate(current: string | null, ...candidates: Array<string | null | undefined>): string | null {
  return [current, ...candidates]
    .filter((value): value is string => Boolean(value))
    .sort((first, second) => second.localeCompare(first))[0] ?? null;
}

function prettifyScoreKey(value: string): string {
  return value
    .replace(/^icare_\d+_/, "")
    .replace(/_/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toLocaleUpperCase("ro-RO") + part.slice(1))
    .join(" ");
}
