import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  audienceAccessNote,
  getCurrentParticipant,
  getCurrentTrainer,
  getParticipantSession,
  getTrainerSession,
} from "./auth";
import { listEmailSurfaceStubs } from "./email";
import { resolveInviteBundle } from "./invites";
import { getParticipantWorkspaceSummary } from "./participants";
import {
  addCompanyTeamMembership,
  createCompany,
  createCompanyTeam,
  deleteCompany,
  getCompanyList,
  getCompanyTeamMemberships,
  importCompanyRoster,
  resendParticipantInvitation,
  sendParticipantInvitations,
} from "./companies";
import {
  getQuestionnaireDefinition,
  listQuestionnaireDefinitionStubs,
  saveQuestionnaireResponse,
  submitQuestionnaireResponse,
} from "./questionnaires";
import { getTrainerDashboardSummary, getTrainerOperationsSummary } from "./trainer";

describe("frontend API adapter stubs", () => {
  beforeEach(() => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "true";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "true";
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
    delete process.env.CODRUT_FRONTEND_DEMO_FALLBACK;
    delete process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK;
  });

  it("returns role-scoped local users", async () => {
    await expect(getCurrentTrainer()).resolves.toMatchObject({ role: "trainer" });
    await expect(getCurrentParticipant()).resolves.toMatchObject({ role: "participant" });
    await expect(getTrainerSession()).resolves.toMatchObject({ state: "fallback" });
    await expect(getParticipantSession()).resolves.toMatchObject({ state: "fallback" });
    expect(audienceAccessNote("invitee")).toContain("linkul securizat");
  });

  it("returns trainer dashboard placeholder data", async () => {
    const summary = await getTrainerDashboardSummary();

    expect(summary.stats).toHaveLength(4);
    expect(summary.stats[0]).toMatchObject({ label: "Companii" });
    expect(summary.cards.map((card) => card.title)).toContain("Email");
    expect(summary.activeCompanies[0]).toMatchObject({
      id: "demo-project",
      company: "Client demo",
    });
    expect(Object.prototype.hasOwnProperty.call(summary.activeCompanies[0], "projectName")).toBe(false);
  });

  it("builds trainer dashboard rows around companies from backend data", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/companies")) {
        return {
          ok: true,
          json: async () => [
            {
              id: "company-1",
              name: "Michelin",
              participantCount: 12,
              assignmentCount: 10,
              completedCount: 6,
              stage: "completion",
            },
          ],
        } as Response;
      }
      return { ok: true, json: async () => [] } as Response;
    });
    vi.stubGlobal("fetch", fetchMock);

    const summary = await getTrainerDashboardSummary();

    expect(summary.stats[0]).toMatchObject({
      label: "Companii",
      value: 1,
    });
    expect(summary.activeCompanies).toEqual([
      expect.objectContaining({
        id: "company-1",
        company: "Michelin",
        href: "/trainer/companies/company-1",
      }),
    ]);
    expect(Object.prototype.hasOwnProperty.call(summary.activeCompanies[0], "projectName")).toBe(false);
  });

  it("builds trainer operations from backend data without localStorage roster state", async () => {
    window.localStorage.setItem(
      "codrut_participants_company-1",
      JSON.stringify([{ id: "local-participant", full_name: "Local Participant", email: "local@example.com" }]),
    );

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/companies")) {
        return {
          ok: true,
          json: async () => [{ id: "company-1", name: "Michelin" }],
        } as Response;
      }
      if (url.endsWith("/companies/company-1/participants")) {
        return {
          ok: true,
          json: async () => [
            {
              id: "participant-1",
              full_name: "Ana Pop",
              email: "ana@example.com",
              reports_to_name: null,
              position: "Manager",
              location: "Bucuresti",
              role_group: "leadership",
              pcm_profile: "Persister",
              user_id: "user-1",
            },
          ],
        } as Response;
      }
      if (url.endsWith("/companies/company-1/assignments")) {
        return {
          ok: true,
          json: async () => [
            {
              id: "assignment-1",
              company_id: "company-1",
              respondent_profile_id: "participant-1",
              questionnaire_key: "lencioni",
              target_type: "self",
              status: "submitted",
              submitted_at: "2026-06-10T08:00:00Z",
              scored_at: null,
            },
          ],
        } as Response;
      }
      if (url.endsWith("/companies/company-1/teams")) {
        return { ok: true, json: async () => [] } as Response;
      }
      return { ok: false, status: 404 } as Response;
    });
    vi.stubGlobal("fetch", fetchMock);

    const summary = await getTrainerOperationsSummary();

    expect(summary.roster.map((participant) => participant.name)).toEqual(["Ana Pop"]);
    expect(summary.roster.map((participant) => participant.name)).not.toContain("Local Participant");
    expect(summary.validations.map((validation) => validation.label)).toContain("Date backend");
  });

  it("returns participant workspace placeholder data", async () => {
    const summary = await getParticipantWorkspaceSummary();

    expect(summary.cards).toHaveLength(3);
    expect(summary.emptyState.title).toContain("Fara");
  });

  it("keeps questionnaire and email surfaces explicit", async () => {
    const questionnaires = await listQuestionnaireDefinitionStubs();

    expect(questionnaires.map((definition) => definition.id)).toEqual(
      expect.arrayContaining(["icare", "boss_360", "pcm_baseline", "phase"]),
    );
    expect(questionnaires.find((definition) => definition.id === "boss_360")).toMatchObject({
      status: "active",
      estimatedItems: 5,
    });
    await expect(listEmailSurfaceStubs()).resolves.toHaveLength(3);
  });

  it("resolves invite bundle fallback states", async () => {
    await expect(resolveInviteBundle("demo-token")).resolves.toMatchObject({
      state: "valid",
      projectName: "Intake Iunie",
      participantEmail: "participant@companie.ro",
    });
    await expect(resolveInviteBundle("expired-demo")).resolves.toMatchObject({
      state: "expired",
    });
  });

  it("resolves real secure invite links through the backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        email: "ana@example.com",
        full_name: "Ana Pop",
        is_leadership: false,
        already_registered: false,
        project_id: "project-1",
        project_name: "Leadership training sept 2026",
        expires_at: "2026-09-30T21:00:00Z",
        token_status: "active",
        tasks: [
          {
            id: "assignment-1",
            title: "Lencioni pentru echipa ta",
            status: "not_started",
            detail: "Raspuns pentru echipa din care faci parte.",
            href: "/participant/questionnaires/lencioni?assignmentId=assignment-1",
            assignmentId: "assignment-1",
            targetLabel: "Leadership",
            estimatedMinutes: 12,
            questionnaireKey: "lencioni",
          },
        ],
      }),
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    await expect(resolveInviteBundle("real-token")).resolves.toMatchObject({
      state: "valid",
      projectName: "Leadership training sept 2026",
      participantEmail: "ana@example.com",
      participantFullName: "Ana Pop",
      isLeadership: false,
      alreadyRegistered: false,
      deadlineLabel: expect.stringContaining("2026"),
      tasks: [expect.objectContaining({ assignmentId: "assignment-1" })],
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/auth/invite/verify?token=real-token"),
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
      }),
    );
  });

  it("maps backend invite failures without falling back to demo data", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({
        error: {
          code: "task_link_expired",
          message: "Linkul a expirat.",
        },
      }),
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    await expect(resolveInviteBundle("expired-real")).resolves.toMatchObject({
      state: "expired",
      message: "Linkul a expirat.",
    });
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("keeps demo invite tokens unavailable when demo fallback is disabled", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(resolveInviteBundle("demo-token")).resolves.toMatchObject({
      state: "not_found",
    });
    await expect(resolveInviteBundle("expired-demo")).resolves.toMatchObject({
      state: "not_found",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("uses seeded questionnaire response fallback for demo assignments", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    await expect(
      saveQuestionnaireResponse("11111111-1111-4111-8111-111111111111", { q1: 1 }),
    ).resolves.toMatchObject({
      status: "draft",
      questionnaire_key: "lencioni",
    });
    await expect(
      submitQuestionnaireResponse("11111111-1111-4111-8111-111111111111", { q1: 1 }),
    ).resolves.toMatchObject({
      status: "submitted",
      questionnaire_key: "lencioni",
    });

  });

  it("does not report seeded questionnaire saves as successful outside demo mode", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    await expect(
      saveQuestionnaireResponse("11111111-1111-4111-8111-111111111111", { q1: 1 }),
    ).rejects.toThrow("Nu am putut salva draftul.");
    await expect(
      submitQuestionnaireResponse("11111111-1111-4111-8111-111111111111", { q1: 1 }),
    ).rejects.toThrow("Nu am putut trimite raspunsurile.");
  });

  it("resolves the seeded boss 360 questionnaire as a runnable fallback", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    await expect(getQuestionnaireDefinition("boss_360")).resolves.toMatchObject({
      key: "boss_360",
      schema: {
        sections: [
          {
            questions: expect.arrayContaining([
              expect.objectContaining({ id: "boss_360_q01" }),
            ]),
          },
        ],
      },
    });

  });

  it("does not fall back to demo sessions when fallback is disabled", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    await expect(getTrainerSession()).rejects.toThrow("Trainer authentication required");
    await expect(getParticipantSession()).rejects.toThrow("Participant authentication required");
  });

  it("creates companies through the backend only", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ id: "company-1", name: "Test Company" }),
    } as Response);

    await expect(createCompany("Test Company")).resolves.toEqual({
      id: "company-1",
      name: "Test Company",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/companies"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({ name: "Test Company" }),
      }),
    );
  });

  it("deletes companies through the backend only", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue({ ok: true } as Response);

    await expect(deleteCompany("company-1")).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/companies/company-1"),
      expect.objectContaining({
        method: "DELETE",
        credentials: "include",
      }),
    );
  });

  it("keeps company list rendering when one company enrichment fails", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [{ id: "company-1", name: "Michelin" }],
      } as Response)
      .mockResolvedValueOnce({
        ok: false,
        status: 400,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [],
      } as Response);

    await expect(getCompanyList()).resolves.toEqual([
      expect.objectContaining({
        id: "company-1",
        name: "Michelin",
        dataUnavailable: true,
      }),
    ]);
  });

  it("does not merge localStorage companies into the company list", async () => {
    window.localStorage.setItem(
      "codrut_local_companies",
      JSON.stringify([{ id: "local-company", name: "Local-only client" }]),
    );
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 500 }));

    const companies = await getCompanyList();

    expect(companies.map((company) => company.id)).not.toContain("local-company");
    expect(companies.map((company) => company.id)).toEqual(
      expect.arrayContaining(["demo-project", "leadership-pilot", "past-client-video"]),
    );
  });

  it("imports roster first and sends participant access through an explicit batch action", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          participants: [{ id: "participant-1", full_name: "Ana", email: "ana@example.com" }],
          email_results: [],
          total_imported: 1,
          emails_sent: 0,
          emails_failed: 0,
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          results: [
            {
              participant_id: "participant-1",
              full_name: "Ana",
              email: "ana@example.com",
              delivery_mode: "secure_links",
              email_sent: false,
              error: null,
              invite_url: "https://app.example.com/invite/token",
            },
          ],
          total: 1,
          emails_sent: 0,
          emails_failed: 0,
          links_generated: 1,
        }),
      } as Response);

    await expect(
      importCompanyRoster("company-1", [
        {
          Name: "Ana",
          "Reports To": "",
          Position: "Member",
          Location: "Bucharest",
          email: "ana@example.com",
          "Profil PCM": "",
        },
      ]),
    ).resolves.toMatchObject({ total_imported: 1, emails_sent: 0 });

    await expect(
      sendParticipantInvitations("company-1", {
        participantIds: ["participant-1"],
        mode: "secure_links",
      }),
    ).resolves.toMatchObject({ links_generated: 1 });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining("/companies/company-1/participants/roster"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: expect.stringContaining('"send_invites":false'),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining("/companies/company-1/participants/invitations"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({
          participant_ids: ["participant-1"],
          mode: "secure_links",
          force_rotate: false,
        }),
      }),
    );
  });

  it("resends participant invitations through the backend", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        participants: [],
        email_results: [
          {
            participant_id: "participant-1",
            full_name: "Ana",
            email: "ana@example.com",
            delivery_mode: "email",
            email_sent: true,
            error: null,
            invite_url: null,
          },
        ],
        total_imported: 0,
        emails_sent: 1,
        emails_failed: 0,
      }),
    } as Response);

    await expect(resendParticipantInvitation("company-1", "participant-1")).resolves.toMatchObject({
      participant_id: "participant-1",
      email_sent: true,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/companies/company-1/participants/participant-1/resend-invite"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
      }),
    );
  });

  it("manages company teams and memberships through the backend", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "team-1",
          company_id: "company-1",
          name: "Leadership",
          type: "leadership",
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          {
            id: "membership-1",
            team_id: "team-1",
            participant_profile_id: "participant-1",
            role: "leader",
          },
        ],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          id: "membership-2",
          team_id: "team-1",
          participant_profile_id: "participant-2",
          role: "member",
        }),
      } as Response);

    await expect(
      createCompanyTeam("company-1", { name: "Leadership", type: "leadership" }),
    ).resolves.toMatchObject({ id: "team-1", type: "leadership" });
    await expect(getCompanyTeamMemberships("company-1", "team-1")).resolves.toHaveLength(1);
    await expect(
      addCompanyTeamMembership("company-1", "team-1", {
        participantProfileId: "participant-2",
        role: "member",
      }),
    ).resolves.toMatchObject({ participant_profile_id: "participant-2" });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining("/companies/company-1/teams"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({ name: "Leadership", type: "leadership" }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining("/companies/company-1/teams/team-1/memberships"),
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      3,
      expect.stringContaining("/companies/company-1/teams/team-1/memberships"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({
          participant_profile_id: "participant-2",
          role: "member",
        }),
      }),
    );
  });

  it("lists only active questionnaire definitions", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => [
        {
          key: "boss_360",
          version: 1,
          title: "Boss / manager 360",
          description: "Feedback form",
          schema: {
            schema_version: "questionnaire.v1",
            audience: "participant",
            sections: [],
          },
        },
      ],
    } as Response);

    await expect(listQuestionnaireDefinitionStubs()).resolves.toEqual([
      expect.objectContaining({
        id: "boss_360",
        name: "Boss / manager 360",
        status: "active",
      }),
    ]);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/forms\/definitions$/),
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
      }),
    );
  });
});
