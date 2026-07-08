import { describe, expect, it } from "vitest";

import type { CompanyAssignment, CompanyProject, CompanyScoringResult } from "@/api/companies";
import {
  buildParticipantProjectHistory,
  buildParticipantResultSummaries,
  countPrivateFeedbackGiven,
  countPrivateFeedbackReceived,
} from "./participant-profile-data";

const projects: CompanyProject[] = [
  project("project-1", "Pilot leadership"),
  project("project-2", "Program anterior"),
];

describe("participant profile data", () => {
  it("builds same-company project history from respondent and target assignments", () => {
    const assignments = [
      assignment("self-driver", "project-1", "participant-1", "distress_drivers", "self", null, "scored"),
      assignment("feedback-given", "project-1", "participant-1", "boss_360", "person", "manager-1", "submitted"),
      assignment("feedback-received", "project-1", "peer-1", "boss_360", "person", "participant-1", "submitted"),
      assignment("old-lencioni", "project-2", "participant-1", "lencioni", "team", null, "scored"),
    ];

    const rows = buildParticipantProjectHistory({
      participantId: "participant-1",
      assignments,
      projects,
    });

    expect(rows).toHaveLength(2);
    expect(rows[0]).toMatchObject({
      projectId: "project-1",
      assignedCount: 3,
      completedCount: 3,
      scoredCount: 1,
      feedbackGivenCount: 1,
      feedbackReceivedCount: 1,
    });
    expect(rows[1]).toMatchObject({
      projectId: "project-2",
      projectName: "Program anterior",
      assignedCount: 1,
      scoredCount: 1,
    });
  });

  it("summarizes calculated questionnaire results without exposing 360 given to another person", () => {
    const assignments = [
      assignment("self-driver", "project-1", "participant-1", "distress_drivers", "self", null, "scored"),
      assignment("feedback-given", "project-1", "participant-1", "boss_360", "person", "manager-1", "scored"),
      assignment("self-360", "project-1", "participant-1", "boss_360", "person", "participant-1", "scored"),
      assignment("pcm", "project-1", "participant-1", "pcm_base", "self", null, "scored"),
    ];
    const results = [
      result("self-driver", { be_strong: 76, be_perfect: 58 }, "be_strong"),
      result("feedback-given", { icare_01_dezvolta_oamenii: { score: 4.5 } }, "icare_01_dezvolta_oamenii"),
      result("self-360", { icare_01_dezvolta_oamenii: { score: 4.5 }, icare_02_conduce_prin_puterea_exemplului: { score: 3.5 } }, "icare_01_dezvolta_oamenii"),
      result("pcm", { pcm_base: "thinker", pcm_phase: "persister" }, "pcm_base"),
    ];

    const summaries = buildParticipantResultSummaries({
      participantId: "participant-1",
      assignments,
      results,
    });

    expect(summaries.map((summary) => summary.assignmentId)).toEqual(["self-driver", "self-360"]);
    expect(summaries).not.toEqual(
      expect.arrayContaining([expect.objectContaining({ assignmentId: "feedback-given" })]),
    );
    expect(summaries).not.toEqual(
      expect.arrayContaining([expect.objectContaining({ assignmentId: "pcm" })]),
    );
    expect(summaries.find((summary) => summary.assignmentId === "self-360")).toMatchObject({
      questionnaireLabel: "iCARE 360 pentru manager",
      targetLabel: "Autoevaluare",
      dimensionCount: 2,
      averageScore: 4,
      primaryResultLabel: "Dezvolta Oamenii",
    });
    expect(countPrivateFeedbackGiven(assignments, "participant-1")).toBe(1);
    expect(countPrivateFeedbackReceived(assignments, "participant-1")).toBe(0);
  });
});

function project(id: string, name: string): CompanyProject {
  return {
    id,
    company_id: "company-1",
    company_name: "Companie",
    name,
    description: null,
    project_type: "Leadership",
    status: "active",
    starts_at: null,
    due_at: null,
    form_opens_at: null,
    form_closes_at: null,
    created_at: "2026-06-01T00:00:00.000Z",
    updated_at: "2026-06-01T00:00:00.000Z",
  };
}

function assignment(
  id: string,
  projectId: string,
  respondentId: string,
  questionnaireKey: string,
  targetType: CompanyAssignment["target_type"],
  targetPersonId: string | null,
  status: CompanyAssignment["status"],
): CompanyAssignment {
  return {
    id,
    company_id: "company-1",
    project_id: projectId,
    respondent_profile_id: respondentId,
    questionnaire_key: questionnaireKey,
    target_type: targetType,
    target_person_id: targetPersonId,
    target_team_id: targetType === "team" ? "team-1" : null,
    status,
    submitted_at: "2026-06-20T10:00:00.000Z",
    scored_at: status === "scored" ? "2026-06-20T11:00:00.000Z" : null,
  };
}

function result(
  assignmentId: string,
  scores: Record<string, unknown>,
  primaryResult: string,
): CompanyScoringResult {
  return {
    id: `score-${assignmentId}`,
    assignment_id: assignmentId,
    scores,
    primary_result: primaryResult,
  };
}
