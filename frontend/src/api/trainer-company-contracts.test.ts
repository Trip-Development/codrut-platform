import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  createCompanyAssignment,
  createCompanyProject,
  deleteCompany,
  deleteCompanyProject,
  importCompanyRoster,
  resendParticipantInvitation,
  saveCompanyDefaultAssignmentPlan,
  sendParticipantInvitations,
  type CompanyAssignmentPlanItem,
  updateCompanyParticipant,
  updateCompanyProject,
} from "./companies";
import {
  getScoringResult,
  getTrainerDashboardSummary,
  getTrainerOperationsSummary,
  getTrainerReports,
} from "./trainer";

function response({
  ok,
  status = ok ? 200 : 400,
  payload,
  jsonError,
}: {
  ok: boolean;
  status?: number;
  payload?: unknown;
  jsonError?: unknown;
}): Response {
  return {
    ok,
    status,
    json: jsonError
      ? vi.fn().mockRejectedValue(jsonError)
      : vi.fn().mockResolvedValue(payload),
  } as unknown as Response;
}

const companySummary = {
  id: "company-synthetic",
  name: "Companie sintetică",
  participant_count: 2,
  project_count: 1,
  assignment_count: 0,
  completed_count: 0,
  scored_count: 0,
  stage: "setup",
};

describe("company mutation contracts", () => {
  beforeEach(() => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    document.cookie = "codrut_csrf=; Max-Age=0; path=/";
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    delete process.env.CODRUT_FRONTEND_DEMO_FALLBACK;
    delete process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK;
  });

  it("maps structured roster validation details and limits the error summary", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      ok: false,
      status: 422,
      payload: {
        error: {
          details: [
            { loc: ["body", "rows", 0, "email"], msg: "Email invalid" },
            { loc: ["body", "rows", 1, "Name"], message: "Numele lipsește" },
            { loc: ["body", "rows", 2, "Position"], message: "Poziția lipsește" },
            { loc: ["body", "rows", 3, "Location"], message: "Locația lipsește" },
          ],
        },
      },
    })));

    await expect(importCompanyRoster("company-synthetic", [], {
      idempotencyKey: "roster-import-test",
    })).rejects.toThrow(
      "rows.0.email: Email invalid; rows.1.Name: Numele lipsește; rows.2.Position: Poziția lipsește; încă 1 erori.",
    );
  });

  it("falls through to string and stable validation messages for participant edits", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: false, status: 422, payload: { detail: "Emailul trebuie corectat." } }))
      .mockResolvedValueOnce(response({ ok: false, status: 500, jsonError: new Error("invalid json") }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(updateCompanyParticipant("company-synthetic", "participant-1", {
      fullName: "Participant sintetic",
      email: "invalid",
    })).rejects.toThrow("Emailul trebuie corectat.");
    await expect(updateCompanyParticipant("company-synthetic", "participant-1", {
      fullName: "Participant sintetic",
      email: "participant@example.com",
    })).rejects.toThrow("Backend refuzat (500)");
  });

  it("persists every project field using the backend naming contract", async () => {
    const project = {
      id: "project-1",
      company_id: "company-synthetic",
      name: "Proiect sintetic",
      status: "active",
    };
    const fetchMock = vi.fn().mockResolvedValue(response({ ok: true, payload: project }));
    vi.stubGlobal("fetch", fetchMock);

    await updateCompanyProject("company-synthetic", "project-1", {
      name: undefined,
      description: null,
      projectType: null,
      status: undefined,
      startsAt: null,
      dueAt: null,
      formOpensAt: null,
      formClosesAt: null,
    });

    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      name: "",
      description: null,
      project_type: null,
      status: "draft",
      starts_at: null,
      due_at: null,
      form_opens_at: null,
      form_closes_at: null,
    });
  });

  it("surfaces project create, update, and deletion failures", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: false, status: 409, payload: { error: { message: "Numele proiectului există." } } }))
      .mockResolvedValueOnce(response({ ok: false, status: 403, jsonError: new Error("invalid json") }))
      .mockResolvedValueOnce(response({ ok: false, status: 409, payload: { error: { message: "Proiectul are asignări active." } } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(createCompanyProject("company-synthetic", { name: "Duplicat" })).rejects.toThrow(
      "Numele proiectului există.",
    );
    await expect(updateCompanyProject("company-synthetic", "project-1", { status: "active" })).rejects.toThrow(
      "Backend refuzat (403)",
    );
    await expect(deleteCompanyProject("company-synthetic", "project-1")).rejects.toThrow(
      "Proiectul are asignări active.",
    );
  });

  it("pins assignment scope and visibility in the persistence payload", async () => {
    const persisted = {
      id: "assignment-1",
      respondent_profile_id: "participant-1",
      questionnaire_key: "synthetic_pulse",
      target_type: "self",
      status: "assigned",
    };
    const fetchMock = vi.fn().mockResolvedValue(response({ ok: true, payload: persisted }));
    vi.stubGlobal("fetch", fetchMock);

    await createCompanyAssignment("company-synthetic", {
      respondentProfileId: "participant-1",
      questionnaireKey: "synthetic_pulse",
      targetType: "self",
    });
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      respondent_profile_id: "participant-1",
      project_id: null,
      questionnaire_key: "synthetic_pulse",
      target_type: "self",
      target_person_id: null,
      target_team_id: null,
      visibility_policy: "trainer_raw_review",
    });
  });

  it("saves a project-scoped assignment plan without mutating item shape", async () => {
    const saved = { created: 1, skipped: 0, assignments: [] };
    const fetchMock = vi.fn().mockResolvedValue(response({ ok: true, payload: saved }));
    vi.stubGlobal("fetch", fetchMock);
    const item: CompanyAssignmentPlanItem = {
      key: "assignment-1",
      scope_id: "team-1",
      scope_name: "Echipă sintetică",
      scope_type: "functional",
      respondent_profile_id: "participant-1",
      respondent_name: "Participant sintetic",
      questionnaire_key: "synthetic_pulse",
      target_type: "team",
      target_person_id: null,
      target_person_name: null,
      target_team_id: "team-1",
      target_team_name: "Echipă sintetică",
      target_team_type: "functional",
      target_team_member_ids: ["participant-1"],
      target_team_leader_id: "participant-1",
      visibility_policy: "reviewed_anonymized",
      selected: true,
      existing_assignment_id: null,
    };

    await saveCompanyDefaultAssignmentPlan("company-synthetic", [item], "project-1");
    expect(fetchMock.mock.calls[0]?.[0]).toMatch(/default-plan\?project_id=project-1$/);
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      project_id: "project-1",
      assignments: [{
        respondent_profile_id: "participant-1",
        questionnaire_key: "synthetic_pulse",
        target_type: "team",
        target_person_id: null,
        target_team_id: "team-1",
        target_team_name: "Echipă sintetică",
        target_team_type: "functional",
        target_team_member_ids: ["participant-1"],
        target_team_leader_id: "participant-1",
        visibility_policy: "reviewed_anonymized",
      }],
    });
  });

  it("derives invitation targeting defaults and carries idempotency through retries", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({
      ok: true,
      payload: { mode: "secure_links", selected_count: 2, email_results: [], secure_links: [] },
    }));
    vi.stubGlobal("fetch", fetchMock);

    await sendParticipantInvitations("company-synthetic", {
      participantIds: ["participant-1", "participant-2"],
      projectId: "project-1",
      mode: "secure_links",
      idempotencyKey: "invite-batch-test",
    });
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(new Headers(init.headers).get("Idempotency-Key")).toBe("invite-batch-test");
    expect(JSON.parse(String(init.body))).toEqual({
      participant_ids: ["participant-1", "participant-2"],
      project_id: "project-1",
      mode: "secure_links",
      target_mode: "selected",
      force_rotate: false,
    });
  });

  it("returns null when a successful resend has no email result", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      ok: true,
      payload: { imported: 0, skipped: 0, errors: [], email_results: [] },
    })));

    await expect(resendParticipantInvitation(
      "company-synthetic",
      "participant-1",
      null,
      "invite-resend-test",
    )).resolves.toBeNull();
  });

  it("surfaces company deletion messages and stable fallback status", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: false, status: 409, payload: { error: { message: "Compania are proiecte active." } } }))
      .mockResolvedValueOnce(response({ ok: false, status: 500, jsonError: new Error("invalid json") }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(deleteCompany("company-synthetic")).rejects.toThrow("Compania are proiecte active.");
    await expect(deleteCompany("company-synthetic")).rejects.toThrow("Server returned status 500");
  });
});

describe("trainer aggregation contracts", () => {
  beforeEach(() => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    delete process.env.CODRUT_FRONTEND_DEMO_FALLBACK;
    delete process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK;
  });

  it("returns an explicit empty dashboard when no companies exist", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ ok: true, payload: [] })));

    const summary = await getTrainerDashboardSummary();
    expect(summary.stats[0]).toMatchObject({ label: "Companii", value: 0 });
    expect(summary.activeCompanies).toEqual([]);
  });

  it("marks companies without assignments as blocked setup work", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({ ok: true, payload: [companySummary] })));

    await expect(getTrainerDashboardSummary()).resolves.toMatchObject({
      stats: expect.arrayContaining([expect.objectContaining({ label: "Rata completare", value: 0 })]),
      activeCompanies: [expect.objectContaining({
        stage: "setup",
        blockers: ["Fără asignări configurate"],
        nextAction: "Configurează rosterul și chestionarele",
      })],
    });
  });

  it("fails closed to an empty operational dashboard when company loading is unavailable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));
    await expect(getTrainerDashboardSummary()).resolves.toMatchObject({ stats: [], activeCompanies: [], actions: [] });
    await expect(getTrainerOperationsSummary()).resolves.toMatchObject({ roster: [] });
  });

  it("maps real roster defaults and reports partial backend failures", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/companies/summary")) return response({ ok: true, payload: [companySummary] });
      if (url.endsWith("/companies")) return response({ ok: true, payload: [{ id: "company-synthetic", name: "Companie sintetică" }] });
      if (url.endsWith("/companies/company-synthetic/projects")) return response({ ok: true, payload: [] });
      if (url.endsWith("/companies/company-synthetic/participants")) {
        return response({ ok: true, payload: [
          {
            id: "participant-1",
            full_name: "Participant cu cont",
            email: "account@example.com",
            user_id: "user-1",
            reports_to_name: "Manager inexistent",
            role_group: "leadership",
          },
          {
            id: "participant-2",
            full_name: "Participant fără cont",
            email: null,
            user_id: null,
            reports_to_name: null,
            role_group: "member",
          },
        ] });
      }
      if (url.endsWith("/companies/company-synthetic/assignments")) return response({ ok: true, payload: [] });
      if (url.includes("/participants/invitations/status")) return response({ ok: true, payload: [] });
      if (url.endsWith("/companies/company-synthetic/teams")) return response({ ok: false, status: 503 });
      return response({ ok: false, status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    const summary = await getTrainerOperationsSummary();
    expect(summary.roster).toEqual([
      expect.objectContaining({ inviteStatus: "account_active", role: "leadership", position: "Participant", location: "Remote" }),
      expect.objectContaining({ inviteStatus: "not_sent", email: "Email indisponibil", role: "member" }),
    ]);
    expect(summary.validations).toEqual(expect.arrayContaining([
      expect.objectContaining({ label: "Reports To", severity: "warning" }),
      expect.objectContaining({ label: "Date backend", severity: "warning" }),
    ]));
  });

  it("returns persisted scoring results and no synthetic result on API failure", async () => {
    const result = {
      id: "score-1",
      assignment_id: "assignment-1",
      scores: { sample_rating: 4 },
      primary_result: "sample_rating",
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: true, payload: result }))
      .mockResolvedValueOnce(response({ ok: false, status: 404 }))
      .mockRejectedValueOnce(new TypeError("offline"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getScoringResult("assignment-1")).resolves.toEqual(result);
    await expect(getScoringResult("missing-assignment")).resolves.toBeNull();
    await expect(getScoringResult("offline-assignment")).resolves.toBeNull();
  });

  it("builds reports from submitted assignments while containing missing participant data", async () => {
    const summaryWithAssignments = { ...companySummary, assignment_count: 2, completed_count: 2, stage: "reporting" };
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/companies/summary")) return response({ ok: true, payload: [summaryWithAssignments] });
      if (url.endsWith("/companies")) return response({ ok: true, payload: [{ id: "company-synthetic", name: "Companie sintetică" }] });
      if (url.endsWith("/companies/company-synthetic/projects")) return response({ ok: true, payload: [] });
      if (url.endsWith("/companies/company-synthetic/participants")) {
        return response({ ok: true, payload: [{
          id: "participant-1",
          full_name: "Participant sintetic",
          email: "participant@example.com",
          role_group: "member",
        }] });
      }
      if (url.endsWith("/companies/company-synthetic/assignments")) {
        return response({ ok: true, payload: [
          {
            id: "assignment-1",
            respondent_profile_id: "participant-1",
            questionnaire_key: "synthetic_pulse",
            target_type: "self",
            status: "scored",
            submitted_at: "2026-07-17T08:00:00Z",
            scored_at: "2026-07-17T08:01:00Z",
          },
          {
            id: "assignment-2",
            respondent_profile_id: "missing-participant",
            questionnaire_key: "synthetic_pulse",
            target_type: "self",
            status: "submitted",
            submitted_at: "2026-07-17T08:05:00Z",
            scored_at: null,
          },
        ] });
      }
      if (url.includes("/participants/invitations/status")) return response({ ok: true, payload: [] });
      if (url.endsWith("/companies/company-synthetic/teams")) return response({ ok: true, payload: [] });
      if (url.endsWith("/scoring/assignments/assignment-1/result")) {
        return response({ ok: true, payload: {
          id: "score-1",
          assignment_id: "assignment-1",
          scores: { sample_rating: 4 },
          primary_result: "sample_rating",
        } });
      }
      if (url.endsWith("/scoring/assignments/assignment-2/result")) return response({ ok: false, status: 404 });
      return response({ ok: false, status: 404 });
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(getTrainerReports()).resolves.toEqual([
      expect.objectContaining({
        assignmentId: "assignment-1",
        participantName: "Participant sintetic",
        participantEmail: "participant@example.com",
        primaryResult: "sample_rating",
      }),
      expect.objectContaining({
        assignmentId: "assignment-2",
        participantName: "Participant necunoscut",
        participantEmail: "email indisponibil",
        primaryResult: null,
      }),
    ]);
  });
});
