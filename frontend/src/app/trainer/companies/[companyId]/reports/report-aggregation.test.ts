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
          inspiring: { score: 3.8 },
          create_trust: { score: 4 },
          awareness: { score: 3.3 },
          results: { score: 4.5 },
          empowerment: { score: 4.3 },
          icare_01_dezvolta_oamenii: { score: 3.8 },
          icare_02_conduce_prin_puterea_exemplului: { score: 4 },
          icare_03_creeaza_un_mediu_care_stimuleaza_implicarea: { score: 4.3 },
          icare_04_promotor_al_colaborarii: { score: 4.5 },
          icare_05_ancorat_in_realitate: { score: 4.8 },
          icare_06_aduce_claritate: { score: 5 },
          icare_07_modestie: { score: 3.3 },
          icare_08_inteligenta_emotionala_si_situationala: { score: 3 },
          icare_09_deschis_catre_lume: { score: 2.8 },
          icare_10_ambitios_pentru_companie: { score: 2.5 },
          icare_11_grija_egala_pentru_angajati_si_clienti: { score: 2.3 },
          icare_12_agilitate_antreprenoriala: { score: 2 },
          icare_13_decizii_cat_mai_aproape_de_teren: { score: 1.8 },
          icare_14_cultiva_inteligenta_colectiva: { score: 1.5 },
          icare_15_ajuta_echipa: { score: 1.3 },
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
    expect(aggregation.driverAverages.map((item) => item.id)).toEqual([
      "be_strong",
      "be_perfect",
      "try_hard",
      "hurry_up",
      "please_people",
    ]);
    expect(aggregation.driverAverages.find((item) => item.id === "be_perfect")).toMatchObject({
      avg: 50,
      interpretation: null,
    });
    expect(aggregation.driverAverages.find((item) => item.id === "hurry_up")).toMatchObject({
      avg: 75,
      interpretation: "Driver prezent peste pragul de atenție; merită explorat în debrief.",
      range_label: ">50",
    });
    expect(aggregation.boss360Count).toBe(1);
    expect(aggregation.boss360Averages.find((item) => item.id === "icare_07_modestie")).toMatchObject({
      avg: 3.3,
    });
    expect(aggregation.lencioniAverages.find((item) => item.id === "fear_of_conflict")).toMatchObject({
      interpretation: "Disfuncția trebuie probabil abordată.",
      range_label: "3-5",
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
            inspiring: { score: 3.5 },
            create_trust: { score: 3.8 },
            awareness: { score: 4 },
            results: { score: 4.3 },
            empowerment: { score: 4.5 },
            icare_15_ajuta_echipa: { score: 4.5 },
          }),
        ],
      ]),
    );

    expect(aggregation.lencioniCount).toBe(1);
    expect(aggregation.lencioniAverages.find((item) => item.id === "absence_of_trust")).toMatchObject({ avg: 8 });
    expect(aggregation.driverCount).toBe(1);
    expect(aggregation.driverAverages.find((item) => item.id === "please_people")).toMatchObject({ avg: 100 });
    expect(aggregation.boss360Count).toBe(1);
    expect(aggregation.boss360Averages.find((item) => item.id === "icare_15_ajuta_echipa")).toMatchObject({ avg: 4.5 });
  });

  it("does not count legacy 360 result keys as reportable iCARE aggregate scores", () => {
    const aggregation = buildReportAggregation(
      [assignment("legacy-360", "boss_360", "scored", "2026-06-11T09:00:00Z")],
      new Map([
        [
          "legacy-360",
          result("legacy-360", {
            inspiring: { score: 3.8 },
            create_trust: { score: 4 },
            awareness: { score: 3.3 },
            results: { score: 4.5 },
            empowerment: { score: 4.3 },
          }),
        ],
      ]),
    );

    expect(aggregation.totalCompleted).toBe(1);
    expect(aggregation.boss360Count).toBe(0);
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
          lencioni_averages: [{ id: "absence_of_trust", label: "Trust", avg: 8, interpretation: null, range_label: null }],
          driver_averages: [{ id: "be_strong", label: "Fii Puternic", avg: 62, interpretation: ">50", range_label: ">50" }],
          boss_360_averages: [{ id: "icare_01_dezvolta_oamenii", label: "Dezvoltă oamenii", avg: 4 }],
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
        lencioniAverages: [{ id: "absence_of_trust", label: "Trust", avg: 8, interpretation: null, range_label: null }],
        driverAverages: [{ id: "be_strong", label: "Fii Puternic", avg: 62, interpretation: ">50", range_label: ">50" }],
        boss360Averages: [{ id: "icare_01_dezvolta_oamenii", label: "Dezvoltă oamenii", avg: 4 }],
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
            absence_of_trust: { score: 8 },
            fear_of_conflict: { score: 7 },
            lack_of_commitment: { score: 6 },
            avoidance_of_accountability: { score: 5 },
            inattention_to_results: { score: 4 },
          }),
        ],
        [
          "member-score",
          result("member-score", {
            be_strong: 60,
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
    expect(aggregation.teamLenses[0].driverAverages.find((item) => item.id === "be_strong")).toMatchObject({
      avg: 60,
      interpretation: "Driver prezent peste pragul de atenție; merită explorat în debrief.",
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
      absence_of_trust: { score: 8 },
      fear_of_conflict: { score: 7 },
      lack_of_commitment: { score: 6 },
      avoidance_of_accountability: { score: 5 },
      inattention_to_results: { score: 4 },
    };
    const aggregation = buildReportAggregation(
      assignments,
      new Map([
        ["ceo-lencioni", result("ceo-lencioni", lencioniScores)],
        ["ilinca-lencioni", result("ilinca-lencioni", lencioniScores)],
        ["vlad-lencioni", result("vlad-lencioni", lencioniScores)],
        ["alex-driver", result("alex-driver", { be_strong: 80, be_perfect: 20 })],
        ["member-driver", result("member-driver", { be_strong: 40, be_perfect: 90 })],
      ]),
      [
        participant("andrei", "Andrei Vacaru", "1", "thinker", "thinker", "manager"),
        participant("ilinca", "Ilinca Corbu", "AndreiVacaru", "harmonizer", "harmonizer", "manager"),
        participant("vlad", "Vlad Soimu", "AndreiVacaru", "rebel", "promoter", "manager"),
        participant("alex", "Alexandra Giurca", "IlincaCorbu", "persister", "persister"),
        participant("member-vlad", "Member Vlad", "IlincaCorbu", "imaginer", "imaginer"),
        participant("member-ilinca", "Member Ilinca", "VladSoimu", "promoter", "rebel"),
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
