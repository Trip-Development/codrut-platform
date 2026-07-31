import { describe, expect, it } from "vitest";

import type { CompanyAssignment } from "@/api/companies";
import type { CompanyParticipant } from "@/api/companies";
import type { ScoringResultRecord } from "@/api/trainer";
import { adaptReportTeamLenses, buildReportAggregation } from "./report-aggregation";

function assignment(
  id: string,
  questionnaireKey: string,
  status: CompanyAssignment["status"],
  submittedAt: string | null,
): CompanyAssignment {
  return {
    id,
    company_id: "company-1",
    project_id: null,
    respondent_profile_id: `participant-${id}`,
    questionnaire_key: questionnaireKey,
    target_type: "self",
    target_person_id: null,
    target_team_id: null,
    status,
    submitted_at: submittedAt,
    scored_at: status === "scored" ? submittedAt : null,
  };
}

function result(id: string, scores: Record<string, unknown>): ScoringResultRecord {
  return {
    id: `score-${id}`,
    assignment_id: id,
    scores,
    primary_result: null,
  };
}

function participant(
  id: string,
  name: string,
  reportsTo: string | null,
  pcmBase?: string | null,
  pcmPhase?: string | null,
  roleGroup: string | null = null,
): CompanyParticipant {
  return {
    id,
    full_name: name,
    email: `${id}@example.com`,
    reports_to_name: reportsTo,
    position: null,
    location: null,
    role_group: roleGroup,
    pcm_profile: null,
    pcm_base: pcmBase ?? null,
    pcm_phase: pcmPhase ?? null,
    user_id: null,
  };
}

describe("buildReportAggregation", () => {
  it("computes exact averages, completion rate, and newest-first report order", () => {
    const assignments = [
      assignment("old", "lencioni", "scored", "2026-06-10T09:00:00Z"),
      assignment("new", "lencioni", "scored", "2026-06-11T09:00:00Z"),
      assignment("driver", "distress_drivers", "submitted", "2026-06-09T09:00:00Z"),
      assignment("feedback", "boss_360", "scored", "2026-06-11T10:00:00Z"),
      assignment("pending", "lencioni", "assigned", null),
    ];
    const results = new Map<string, ScoringResultRecord | null>([
      [
        "old",
        result("old", {
          team_signal_a: { score: 6, label: "Semnal echipă A" },
          team_signal_b: { score: 3, label: "Semnal echipă B" },
          team_signal_c: { score: 9, label: "Semnal echipă C" },
          team_signal_d: { score: 6, label: "Semnal echipă D" },
          team_signal_e: { score: 6, label: "Semnal echipă E" },
        }),
      ],
      [
        "new",
        result("new", {
          team_signal_a: { score: 9, label: "Semnal echipă A" },
          team_signal_b: { score: 6, label: "Semnal echipă B" },
          team_signal_c: { score: 3, label: "Semnal echipă C" },
          team_signal_d: { score: 9, label: "Semnal echipă D" },
          team_signal_e: { score: 9, label: "Semnal echipă E" },
        }),
      ],
      [
        "driver",
        result("driver", {
          work_signal_a: { score: 100, label: "Semnal lucru A" },
          work_signal_b: { score: 50, label: "Semnal lucru B" },
          work_signal_c: { score: 25, label: "Semnal lucru C" },
          work_signal_d: { score: 75, label: "Semnal lucru D" },
          work_signal_e: { score: 0, label: "Semnal lucru E" },
        }),
      ],
      [
        "feedback",
        result("feedback", {
          feedback_signal_a: { score: 76, label: "Feedback A" },
          feedback_signal_b: { score: 80, label: "Feedback B" },
          feedback_signal_c: { score: 66, label: "Feedback C" },
          feedback_signal_d: { score: 90, label: "Feedback D" },
          feedback_signal_e: { score: 86, label: "Feedback E" },
        }),
      ],
    ]);

    const aggregation = buildReportAggregation(assignments, results);

    expect(aggregation.totalAssigned).toBe(5);
    expect(aggregation.totalCompleted).toBe(4);
    expect(aggregation.completionRate).toBe(80);
    expect(aggregation.reportableAssignments.map((item) => item.id)).toEqual(["feedback", "new", "old", "driver"]);
    expect(aggregation.lencioniCount).toBe(2);
    expect(aggregation.lencioniAverages.find((item) => item.id === "team_signal_a")).toMatchObject({
      avg: 7.5,
    });
    expect(aggregation.lencioniAverages.find((item) => item.id === "team_signal_c")).toMatchObject({
      avg: 6,
    });
    expect(aggregation.driverCount).toBe(1);
    expect(aggregation.driverAverages.map((item) => item.id)).toEqual([
      "work_signal_a",
      "work_signal_b",
      "work_signal_c",
      "work_signal_d",
      "work_signal_e",
    ]);
    expect(aggregation.driverAverages.find((item) => item.id === "work_signal_b")).toMatchObject({
      avg: 50,
      interpretation: null,
    });
    expect(aggregation.driverAverages.find((item) => item.id === "work_signal_d")).toMatchObject({
      avg: 75,
      interpretation: null,
      range_label: null,
    });
    expect(aggregation.boss360Count).toBe(1);
    expect(aggregation.boss360Averages.find((item) => item.id === "feedback_signal_c")).toMatchObject({
      avg: 66,
    });
    expect(aggregation.lencioniAverages.find((item) => item.id === "team_signal_b")).toMatchObject({
      interpretation: null,
      range_label: null,
    });
  });

  it("does not count completed assignments with missing scoring results in aggregate respondent totals", () => {
    const aggregation = buildReportAggregation(
      [
        assignment("missing", "lencioni", "submitted", "2026-06-11T09:00:00Z"),
        assignment("scored", "lencioni", "scored", "2026-06-11T10:00:00Z"),
      ],
      new Map([
        [
          "scored",
          result("scored", {
            team_signal_a: { score: 9 },
            team_signal_b: { score: 9 },
            team_signal_c: { score: 9 },
          }),
        ],
      ]),
    );

    expect(aggregation.totalCompleted).toBe(2);
    expect(aggregation.lencioniCount).toBe(1);
    expect(aggregation.lencioniAverages.every((item) => item.avg === 9)).toBe(true);
  });

  it("aggregates English questionnaire variants with the same scoring buckets", () => {
    const aggregation = buildReportAggregation(
      [
        assignment("lencioni-en", "lencioni_en", "scored", "2026-06-11T09:00:00Z"),
        assignment("driver-en", "distress_drivers_en", "scored", "2026-06-11T09:10:00Z"),
        assignment("boss-en", "boss_360_en", "scored", "2026-06-11T09:20:00Z"),
      ],
      new Map([
        [
          "lencioni-en",
          result("lencioni-en", {
            team_signal_a: { score: 8 },
            team_signal_b: { score: 7 },
            team_signal_c: { score: 6 },
          }),
        ],
        [
          "driver-en",
          result("driver-en", {
            work_signal_a: 20,
            work_signal_b: 40,
            work_signal_c: 60,
            work_signal_d: 80,
            work_signal_e: 100,
          }),
        ],
        [
          "boss-en",
          result("boss-en", {
            feedback_signal_a: { score: 70 },
            feedback_signal_b: { score: 90 },
          }),
        ],
      ]),
    );

    expect(aggregation.lencioniCount).toBe(1);
    expect(aggregation.lencioniAverages.find((item) => item.id === "team_signal_a")).toMatchObject({ avg: 8 });
    expect(aggregation.driverCount).toBe(1);
    expect(aggregation.driverAverages.find((item) => item.id === "work_signal_e")).toMatchObject({ avg: 100 });
    expect(aggregation.boss360Count).toBe(1);
    expect(aggregation.boss360Averages.find((item) => item.id === "feedback_signal_b")).toMatchObject({ avg: 90 });
  });

  it("counts score-bearing feedback results without reconstructing private dimensions", () => {
    const aggregation = buildReportAggregation(
      [assignment("legacy-360", "boss_360", "scored", "2026-06-11T09:00:00Z")],
      new Map([
        [
          "legacy-360",
          result("legacy-360", {
            feedback_signal_a: { score: 76, label: "Feedback A" },
          }),
        ],
      ]),
    );

    expect(aggregation.totalCompleted).toBe(1);
    expect(aggregation.boss360Count).toBe(1);
  });

  it("adapts backend canonical team lenses to the report view model", () => {
    expect(
      adaptReportTeamLenses([
        {
          id: "manager:leader",
          name: "Echipa Ana Manager",
          member_count: 3,
          assigned_count: 7,
          completed_count: 5,
          completion_rate: 71,
          lencioni_count: 3,
          driver_count: 2,
          boss_360_count: 1,
          pcm_base_count: 2,
          pcm_phase_count: 2,
          lencioni_averages: [{ id: "team_signal_a", label: "Semnal echipă A", avg: 8, interpretation: null, range_label: null }],
          lencioni_scale: { score_unit: "score", scale_min: 0, scale_max: 12 },
          driver_averages: [{ id: "work_signal_a", label: "Semnal lucru A", avg: 62, interpretation: null, range_label: null }],
          boss_360_averages: [{ id: "feedback_signal_a", label: "Feedback A", avg: 80 }],
          pcm_base_distribution: [{ id: "thinker", label: "Gânditor", value: 1, color: null }],
          pcm_phase_distribution: [{ id: "harmonizer", label: "Armonizator", value: 1, color: "#f97316" }],
        },
      ]),
    ).toEqual([
      {
        id: "manager:leader",
        name: "Echipa Ana Manager",
        memberCount: 3,
        assignedCount: 7,
        completedCount: 5,
        completionRate: 71,
        lencioniCount: 3,
        driverCount: 2,
        boss360Count: 1,
        pcmBaseCount: 2,
        pcmPhaseCount: 2,
        lencioniAverages: [{ id: "team_signal_a", label: "Semnal echipă A", avg: 8, interpretation: null, range_label: null }],
        lencioniScale: { score_unit: "score", scale_min: 0, scale_max: 12 },
        driverAverages: [{ id: "work_signal_a", label: "Semnal lucru A", avg: 62, interpretation: null, range_label: null }],
        boss360Averages: [{ id: "feedback_signal_a", label: "Feedback A", avg: 80 }],
        pcmBaseDistribution: [{ id: "thinker", label: "Gânditor", value: 1, color: undefined }],
        pcmPhaseDistribution: [{ id: "harmonizer", label: "Armonizator", value: 1, color: "#f97316" }],
      },
    ]);
  });

  it("builds PCM distributions and team lenses from project participants", () => {
    const assignments = [
      assignment("leader-score", "lencioni", "scored", "2026-06-11T09:00:00Z"),
      assignment("member-score", "distress_drivers", "submitted", "2026-06-11T09:10:00Z"),
      assignment("leader-pcm", "pcm_base", "submitted", "2026-06-11T09:20:00Z"),
      assignment("member-pcm", "pcm_phase", "submitted", "2026-06-11T09:25:00Z"),
      assignment("member-pending", "boss_360", "assigned", null),
    ].map((item) => ({
      ...item,
      respondent_profile_id: item.id.startsWith("leader") ? "leader" : "member",
    }));

    const aggregation = buildReportAggregation(
      assignments,
      new Map([
        [
          "leader-score",
          result("leader-score", {
            team_signal_a: { score: 8, label: "Semnal echipă A" },
            team_signal_b: { score: 7, label: "Semnal echipă B" },
          }),
        ],
        [
          "member-score",
          result("member-score", {
            work_signal_a: { score: 60, label: "Semnal lucru A" },
          }),
        ],
      ]),
      [
        participant("leader", "Ana Manager", null, "harmonizer", "thinker"),
        participant("member", "Mihai Pop", "Ana Manager", "harmonizer", "persister"),
      ],
    );

    expect(aggregation.pcmBaseDistribution).toEqual([
      { id: "harmonizer", label: "Armonizator", value: 2, color: "#f97316" },
    ]);
    expect(aggregation.pcmBaseCount).toBe(2);
    expect(aggregation.pcmPhaseDistribution).toEqual([
      { id: "thinker", label: "Gânditor", value: 1, color: "#2563eb" },
      { id: "persister", label: "Perseverent", value: 1, color: "#7c3aed" },
    ]);
    expect(aggregation.pcmPhaseCount).toBe(2);
    expect(aggregation.teamLenses).toHaveLength(1);
    expect(aggregation.teamLenses[0]).toMatchObject({
      id: "manager:leader",
      name: "Echipa Ana Manager",
      memberCount: 2,
      assignedCount: 5,
      completedCount: 4,
      completionRate: 80,
      lencioniCount: 1,
      driverCount: 1,
      pcmBaseCount: 2,
      pcmPhaseCount: 2,
      pcmBaseDistribution: [{ id: "harmonizer", label: "Armonizator", value: 2, color: "#f97316" }],
      pcmPhaseDistribution: [
        { id: "thinker", label: "Gânditor", value: 1, color: "#2563eb" },
        { id: "persister", label: "Perseverent", value: 1, color: "#7c3aed" },
      ],
    });
    expect(aggregation.teamLenses[0].driverAverages.find((item) => item.id === "work_signal_a")).toMatchObject({
      avg: 60,
      interpretation: null,
    });
  });

  it("keeps CEO and direct-report managers in Leadership without duplicating a root manager team", () => {
    const assignments = [
      assignment("ceo-lencioni", "lencioni", "scored", "2026-06-11T09:00:00Z"),
      assignment("ilinca-lencioni", "lencioni", "scored", "2026-06-11T09:05:00Z"),
      assignment("vlad-lencioni", "lencioni", "scored", "2026-06-11T09:10:00Z"),
      assignment("ceo-pcm", "pcm_base", "submitted", "2026-06-11T09:11:00Z"),
      assignment("ilinca-pcm", "pcm_base", "submitted", "2026-06-11T09:12:00Z"),
      assignment("vlad-pcm", "pcm_base", "submitted", "2026-06-11T09:13:00Z"),
      assignment("alex-driver", "distress_drivers", "scored", "2026-06-11T09:15:00Z"),
      assignment("member-driver", "distress_drivers", "scored", "2026-06-11T09:20:00Z"),
    ].map((item) => {
      const respondentByAssignmentId: Record<string, string> = {
        "ceo-lencioni": "andrei",
        "ilinca-lencioni": "ilinca",
        "vlad-lencioni": "vlad",
        "ceo-pcm": "andrei",
        "ilinca-pcm": "ilinca",
        "vlad-pcm": "vlad",
        "alex-driver": "alex",
        "member-driver": "member-vlad",
      };
      return { ...item, respondent_profile_id: respondentByAssignmentId[item.id] ?? item.respondent_profile_id };
    });

    const lencioniScores = {
      team_signal_a: { score: 8, label: "Semnal echipă A" },
      team_signal_b: { score: 7, label: "Semnal echipă B" },
    };
    const aggregation = buildReportAggregation(
      assignments,
      new Map([
        ["ceo-lencioni", result("ceo-lencioni", lencioniScores)],
        ["ilinca-lencioni", result("ilinca-lencioni", lencioniScores)],
        ["vlad-lencioni", result("vlad-lencioni", lencioniScores)],
        ["alex-driver", result("alex-driver", { work_signal_a: 80, work_signal_b: 20 })],
        ["member-driver", result("member-driver", { work_signal_a: 40, work_signal_b: 90 })],
      ]),
      [
        participant("andrei", "Alex Dima", "1", "thinker", "thinker", "manager"),
        participant("ilinca", "Mara Ionescu", "AlexDima", "harmonizer", "harmonizer", "manager"),
        participant("vlad", "Sorin Pavel", "AlexDima", "rebel", "promoter", "manager"),
        participant("alex", "Diana Luca", "MaraIonescu", "persister", "persister"),
        participant("member-vlad", "Tudor Stan", "MaraIonescu", "imaginer", "imaginer"),
        participant("member-ilinca", "Ioana Rusu", "SorinPavel", "promoter", "rebel"),
      ],
    );

    expect(aggregation.teamLenses.map((team) => team.id)).toEqual([
      "leadership",
      "manager:ilinca",
      "manager:vlad",
    ]);
    expect(aggregation.teamLenses[0]).toMatchObject({
      name: "Leadership",
      memberCount: 3,
      assignedCount: 6,
      completedCount: 6,
      lencioniCount: 3,
      pcmBaseDistribution: [
        { id: "harmonizer", label: "Armonizator", value: 1, color: "#f97316" },
        { id: "thinker", label: "Gânditor", value: 1, color: "#2563eb" },
        { id: "rebel", label: "Rebel", value: 1, color: "#eab308" },
      ],
    });
    expect(aggregation.teamLenses.find((team) => team.id === "manager:ilinca")).toMatchObject({
      memberCount: 3,
      driverCount: 2,
    });
    expect(aggregation.teamLenses.find((team) => team.id === "manager:vlad")).toMatchObject({
      memberCount: 2,
      assignedCount: 2,
      completedCount: 2,
    });
  });

  it("marks hierarchy as ambiguous when a referenced manager name is duplicated", () => {
    const aggregation = buildReportAggregation(
      [],
      new Map(),
      [
        participant("manager-a", "Ana Pop", null, null, null, "manager"),
        participant("manager-b", "Ana Pop", null, null, null, "manager"),
        participant("member", "Mihai Ionescu", "Ana Pop"),
      ],
    );

    expect(aggregation.hierarchyAmbiguous).toBe(true);
    expect(aggregation.hierarchyAmbiguityMessage).toContain("Ana Pop");
    expect(aggregation.teamLenses).toEqual([]);
  });
});
