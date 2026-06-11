import { describe, expect, it } from "vitest";

import type { CompanyAssignment } from "@/api/companies";
import type { ScoringResultRecord } from "@/api/trainer";
import { buildReportAggregation } from "./report-aggregation";

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
          absence_of_trust: { score: 6 },
          fear_of_conflict: { score: 3 },
          lack_of_commitment: { score: 9 },
          avoidance_of_accountability: { score: 6 },
          inattention_to_results: { score: 6 },
        }),
      ],
      [
        "new",
        result("new", {
          absence_of_trust: { score: 9 },
          fear_of_conflict: { score: 6 },
          lack_of_commitment: { score: 3 },
          avoidance_of_accountability: { score: 9 },
          inattention_to_results: { score: 9 },
        }),
      ],
      [
        "driver",
        result("driver", {
          be_strong: 100,
          be_perfect: 50,
          try_hard: 25,
          hurry_up: 75,
          please_people: 0,
        }),
      ],
      [
        "feedback",
        result("feedback", {
          inspiring: { score: 75 },
          create_trust: { score: 80 },
          awareness: { score: 65 },
          results: { score: 90 },
          empowerment: { score: 85 },
        }),
      ],
    ]);

    const aggregation = buildReportAggregation(assignments, results);

    expect(aggregation.totalAssigned).toBe(5);
    expect(aggregation.totalCompleted).toBe(4);
    expect(aggregation.completionRate).toBe(80);
    expect(aggregation.reportableAssignments.map((item) => item.id)).toEqual(["feedback", "new", "old", "driver"]);
    expect(aggregation.lencioniCount).toBe(2);
    expect(aggregation.lencioniAverages.find((item) => item.id === "absence_of_trust")).toMatchObject({
      avg: 7.5,
    });
    expect(aggregation.lencioniAverages.find((item) => item.id === "lack_of_commitment")).toMatchObject({
      avg: 6,
    });
    expect(aggregation.driverCount).toBe(1);
    expect(aggregation.driverAverages.find((item) => item.id === "hurry_up")).toMatchObject({
      avg: 75,
    });
    expect(aggregation.boss360Count).toBe(1);
    expect(aggregation.boss360Averages.find((item) => item.id === "awareness")).toMatchObject({
      avg: 65,
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
            absence_of_trust: { score: 9 },
            fear_of_conflict: { score: 9 },
            lack_of_commitment: { score: 9 },
            avoidance_of_accountability: { score: 9 },
            inattention_to_results: { score: 9 },
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
            absence_of_trust: { score: 8 },
            fear_of_conflict: { score: 7 },
            lack_of_commitment: { score: 6 },
            avoidance_of_accountability: { score: 5 },
            inattention_to_results: { score: 4 },
          }),
        ],
        [
          "driver-en",
          result("driver-en", {
            be_strong: 20,
            be_perfect: 40,
            try_hard: 60,
            hurry_up: 80,
            please_people: 100,
          }),
        ],
        [
          "boss-en",
          result("boss-en", {
            inspiring: { score: 70 },
            create_trust: { score: 75 },
            awareness: { score: 80 },
            results: { score: 85 },
            empowerment: { score: 90 },
          }),
        ],
      ]),
    );

    expect(aggregation.lencioniCount).toBe(1);
    expect(aggregation.lencioniAverages.find((item) => item.id === "absence_of_trust")).toMatchObject({ avg: 8 });
    expect(aggregation.driverCount).toBe(1);
    expect(aggregation.driverAverages.find((item) => item.id === "please_people")).toMatchObject({ avg: 100 });
    expect(aggregation.boss360Count).toBe(1);
    expect(aggregation.boss360Averages.find((item) => item.id === "empowerment")).toMatchObject({ avg: 90 });
  });
});
