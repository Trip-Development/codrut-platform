import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  AuthRoleMismatchError,
  AuthSessionUnavailableError,
  changePassword,
  getAuthenticatedSession,
  getCurrentParticipant,
  getCurrentTrainer,
  getParticipantSession,
  getTrainerSession,
} from "./auth";
import {
  archiveCampaignRecipientOnServer,
  bulkCreateCampaignRecipientsOnServer,
  buildVideoCampaignCreatePayload,
  campaignAssetFileNameFromUrl,
  createCampaignOnServer,
  createEmailTemplateOnServer,
  deleteCampaignAssetOnServer,
  deleteCampaignOnServer,
  deleteCampaignRecipientOnServer,
  deleteEmailTemplateOnServer,
  formatEmailTemplateApiError,
  getEmailOpsSummary,
  htmlToPlainText,
  listCampaignRecipientMembershipOnServer,
  listCampaignsOnServer,
  listEmailSurfaceStubs,
  listEmailTemplatesOnServer,
  replaceCampaignRecipientMembershipOnServer,
  restoreCampaignRecipientOnServer,
  sendCampaignOnServer,
  updateCampaignOnServer,
  updateCampaignRecipientOnServer,
  updateEmailTemplateOnServer,
  uploadCampaignAssetOnServer,
} from "./email";
import {
  exchangeInviteSession,
  inviteQuestionnaireLabel,
  inviteTaskHref,
  participantTaskTypeLabel,
  resolveInviteBundle,
} from "./invites";
import { getParticipantWorkspaceSummary } from "./participants";
import {
  addCompanyTeamMembership,
  buildFallbackDriverAggregate,
  createCompanyAssignment,
  createCompany,
  createCompanyTeam,
  deleteCompany,
  getAllCompanyProjects,
  getAssessmentCycles,
  getCompanyAssignments,
  getCompanyDefaultAssignmentPlan,
  getCompanyDetail,
  getIcareAnswerReview,
  getCompanyList,
  getCompanyParticipants,
  getCompanyProjectById,
  getCompanyProjects,
  getCompanyReportAggregate,
  getCompanyTeamMemberships,
  getProjectParticipants,
  getParticipantAccountLinkStatus,
  importCompanyRoster,
  repairParticipantAccountLink,
  removeCompanyTeamMembership,
  resendParticipantInvitation,
  saveCompanyDefaultAssignmentPlan,
  sendParticipantInvitations,
  type CompanyAssignment,
  type CompanyScoringResult,
} from "./companies";
import {
  clearQuestionnaireDefinitionCache,
  getQuestionnaireDefinition,
  getQuestionnaireResponse,
  groupQuestionnaireStubsByKey,
  isQuestionnaireSessionError,
  listQuestionnaireDefinitionStubs,
  type QuestionnaireDefinition,
  QuestionnaireRequestError,
  saveQuestionnaireResponse,
  submitQuestionnaireResponse,
  updateQuestionnaireDefinitionOnServer,
} from "./questionnaires";
import { isDemoFallbackEnabled, isSeededDemoFallbackEnabled } from "./runtime";
import { getTrainerDashboardSummary, getTrainerOperationsSummary } from "./trainer";

describe("frontend API adapter stubs", () => {
  beforeEach(() => {
    clearQuestionnaireDefinitionCache();
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "true";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "true";
  });

  afterEach(() => {
    clearQuestionnaireDefinitionCache();
    vi.unstubAllGlobals();
    window.localStorage.clear();
    delete process.env.CODRUT_FRONTEND_DEMO_FALLBACK;
    delete process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK;
  });

  it("returns role-scoped local users", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 } as Response));

    await expect(getCurrentTrainer()).resolves.toMatchObject({ role: "trainer" });
    await expect(getCurrentParticipant()).resolves.toMatchObject({ role: "participant" });
    await expect(getTrainerSession()).resolves.toMatchObject({ state: "fallback" });
    await expect(getParticipantSession()).resolves.toMatchObject({ state: "fallback" });
  });

  it("never falls back to slug-like questionnaire labels in participant UI", () => {
    expect(inviteQuestionnaireLabel("boss_360")).toBe("iCARE 360 pentru manager");
    expect(inviteQuestionnaireLabel("lencioni_en")).toBe("Lencioni - evaluare echipă");
    expect(inviteQuestionnaireLabel("distress_drivers_en")).toBe("Driveri de stres TA");
    expect(inviteQuestionnaireLabel("unknown_internal_slug")).toBe("Chestionar");
    expect(participantTaskTypeLabel("boss_360")).toBe("Feedback confidențial");
    expect(participantTaskTypeLabel("distress_drivers")).toBe("Formular individual");
    expect(participantTaskTypeLabel("pcm_base")).toBe("Formular individual");
    expect(participantTaskTypeLabel("phase")).toBe("Formular individual");
    expect(participantTaskTypeLabel("pcm_phase")).toBe("Formular individual");
  });

  it("does not duplicate secure invite return targets on task links", () => {
    expect(
      inviteTaskHref(
        {
          id: "task-1",
          title: "Task",
          status: "not_started",
          detail: "Detail",
          href: "/participant/questionnaires/lencioni?assignmentId=a1&access=secure&returnTo=%2Finvite%2Fabc",
          assignmentId: "a1",
          targetLabel: "Leadership",
          estimatedMinutes: 12,
          questionnaireKey: "lencioni",
        },
        { returnTo: "/invite/abc" },
      ),
    ).toBe(
      "/invite/abc/tasks/a1?returnTo=%2Finvite%2Fabc&target=Leadership",
    );
  });

  it("keeps permanent participant questionnaire task links out of the secure invite route", () => {
    expect(
      inviteTaskHref(
        {
          id: "task-1",
          title: "Chestionar",
          status: "not_started",
          detail: "Completează formularul.",
          href: "/participant/questionnaires/lencioni?assignmentId=a1",
          assignmentId: "a1",
          targetLabel: "Leadership",
          estimatedMinutes: 12,
          questionnaireKey: "lencioni",
        },
        { returnTo: "/participant/questionnaires" },
      ),
    ).toBe(
      "/participant/questionnaires/lencioni?assignmentId=a1&returnTo=%2Fparticipant%2Fquestionnaires&target=Leadership",
    );
  });

  it("uses the test fallback only when no explicit setting is present", () => {
    delete process.env.CODRUT_FRONTEND_DEMO_FALLBACK;
    delete process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK;

    expect(isDemoFallbackEnabled()).toBe(true);

    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";

    expect(isDemoFallbackEnabled()).toBe(false);
  });

  it("honors an explicit server false when the public fallback env is empty", () => {
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "";
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";

    expect(isDemoFallbackEnabled()).toBe(false);
  });

  it("fails closed for all demo data on non-local server runtimes", async () => {
    delete process.env.CODRUT_FRONTEND_DEMO_FALLBACK;
    delete process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK;

    const originalInternalApiBaseUrl = process.env.INTERNAL_API_BASE_URL;
    const originalVitest = process.env.VITEST;

    delete process.env.VITEST;
    vi.stubGlobal("window", undefined);
    vi.stubEnv("NODE_ENV", "development");
    process.env.INTERNAL_API_BASE_URL = "https://api.codrut.ro/api";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 } as Response));

    try {
      expect(isDemoFallbackEnabled()).toBe(false);
      expect(isSeededDemoFallbackEnabled()).toBe(false);
      await expect(getTrainerSession()).rejects.toThrow("Trainer authentication required");
      await expect(getParticipantSession()).rejects.toThrow("Participant authentication required");
      await expect(getQuestionnaireDefinition("boss_360")).rejects.toMatchObject({
        name: "QuestionnaireRequestError",
        status: 401,
      });
      await expect(listQuestionnaireDefinitionStubs()).rejects.toMatchObject({
        name: "QuestionnaireRequestError",
        status: 401,
      });
      await expect(getParticipantWorkspaceSummary()).rejects.toMatchObject({
        name: "ParticipantWorkspaceError",
        status: 401,
      });
    } finally {
      if (originalInternalApiBaseUrl === undefined) {
        delete process.env.INTERNAL_API_BASE_URL;
      } else {
        process.env.INTERNAL_API_BASE_URL = originalInternalApiBaseUrl;
      }
      if (originalVitest === undefined) {
        delete process.env.VITEST;
      } else {
        process.env.VITEST = originalVitest;
      }
    }
  });

  it("does not return fake email ops data when demo fallback is disabled", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 503 } as Response));

    await expect(getEmailOpsSummary()).rejects.toThrow("Server returned status 503");
  });

  it("posts campaign send requests to the communications API", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        campaign_id: "campaign-1",
        total: 1,
        sent: 1,
        failed: 0,
        skipped: 0,
        dry_run: false,
        results: [],
      }),
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const result = await sendCampaignOnServer("campaign-1", {
      recipientIds: ["recipient-1"],
    });

    expect(result.sent).toBe(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/communications/campaigns/campaign-1/send"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        headers: expect.objectContaining({
          "Idempotency-Key": expect.stringMatching(/^campaign-send-/),
        }),
        body: JSON.stringify({
          dry_run: false,
          recipient_ids: ["recipient-1"],
          mode: "selected",
        }),
      }),
    );
  });

  it("keeps demo fallback campaigns visible after local create, update, and delete", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 } as Response));

    const created = await createCampaignOnServer({
      name: "Campanie locală",
      segment: null,
      subject: "Subiect local",
      html_body: "<p>Salut.</p>",
      text_body: "Salut.",
    });

    await expect(listCampaignsOnServer()).resolves.toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: created.id,
          name: "Campanie locală",
          segment: null,
          status: "ready",
        }),
      ]),
    );

    await updateCampaignOnServer(created.id, { name: "Campanie locală actualizată" });
    await expect(listCampaignsOnServer()).resolves.toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: created.id,
          name: "Campanie locală actualizată",
        }),
      ]),
    );

    await deleteCampaignOnServer(created.id);
    await expect(listCampaignsOnServer()).resolves.not.toEqual(
      expect.arrayContaining([expect.objectContaining({ id: created.id })]),
    );
  });

  it("persists demo fallback campaign recipient memberships after saving", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 } as Response));

    const savedRows = await replaceCampaignRecipientMembershipOnServer("campaign-local", [
      "recipient-1",
      "recipient-2",
      "recipient-1",
    ]);
    expect(savedRows.map((recipient) => recipient.id)).toEqual(["recipient-1", "recipient-2"]);

    await expect(listCampaignRecipientMembershipOnServer("campaign-local")).resolves.toEqual([
      expect.objectContaining({ id: "recipient-1", membershipSource: "manual" }),
      expect.objectContaining({ id: "recipient-2", membershipSource: "manual" }),
    ]);

    await deleteCampaignOnServer("campaign-local");
    await expect(listCampaignRecipientMembershipOnServer("campaign-local")).resolves.toEqual([]);
  });

  it("keeps demo fallback contacts visible after manual add, update, and delete", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 } as Response));

    await expect(
      bulkCreateCampaignRecipientsOnServer([
        {
          email: "ada@manual.example",
          contact_name: "Ada Test",
          organization_name: "Local Org",
          segment: "potential_customer",
        },
      ]),
    ).resolves.toMatchObject({ created: 1, updated: 0 });

    await expect(
      bulkCreateCampaignRecipientsOnServer([
        {
          email: "ada@manual.example",
          contact_name: "Ada Lovelace",
          organization_name: "Updated Org",
          segment: "past_customer",
        },
      ]),
    ).resolves.toMatchObject({ created: 0, updated: 1 });

    const summary = await getEmailOpsSummary();
    const addedContact = summary.campaign.recipients.find((recipient) => recipient.email === "ada@manual.example");
    expect(addedContact).toEqual(
      expect.objectContaining({
        company: "Updated Org",
        firstName: "Ada",
        lastName: "Lovelace",
        clientType: "tip_1",
      }),
    );

    await deleteCampaignRecipientOnServer(addedContact?.id ?? "");
    await expect(getEmailOpsSummary()).resolves.toEqual(
      expect.objectContaining({
        campaign: expect.objectContaining({
          recipients: expect.not.arrayContaining([
            expect.objectContaining({ email: "ada@manual.example" }),
          ]),
        }),
      }),
    );
  });

  it("preserves protected contact status through demo archive and restore", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 } as Response));

    await bulkCreateCampaignRecipientsOnServer([
      {
        email: "protected@demo.example",
        contact_name: "Contact Protejat",
        organization_name: "Demo Org",
        segment: "potential_customer",
      },
    ]);
    const created = (await getEmailOpsSummary()).campaign.recipients.find(
      (recipient) => recipient.email === "protected@demo.example",
    );
    expect(created).toBeDefined();

    await updateCampaignRecipientOnServer(created?.id ?? "", {
      status: "unsubscribed",
    });
    await archiveCampaignRecipientOnServer(created?.id ?? "");

    await expect(getEmailOpsSummary({ catalogScope: "archived" })).resolves.toEqual(
      expect.objectContaining({
        campaign: expect.objectContaining({
          recipients: expect.arrayContaining([
            expect.objectContaining({
              id: created?.id,
              status: "archived",
              statusBeforeArchive: "unsubscribed",
            }),
          ]),
        }),
      }),
    );

    await expect(restoreCampaignRecipientOnServer(created?.id ?? "")).resolves.toMatchObject({
      status: "unsubscribed",
    });
    await expect(getEmailOpsSummary()).resolves.toEqual(
      expect.objectContaining({
        campaign: expect.objectContaining({
          recipients: expect.arrayContaining([
            expect.objectContaining({
              id: created?.id,
              status: "unsubscribed",
              statusBeforeArchive: null,
            }),
          ]),
        }),
      }),
    );
  });

  it("auto-selects active demo contacts for typed campaigns but keeps no-group campaigns empty", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 } as Response));

    const existingCampaign = await createCampaignOnServer({
      name: "Campanie clienți existenți",
      segment: "past_customer",
      subject: "Subiect clienți",
      html_body: "<p>Salut.</p>",
      text_body: "Salut.",
    });

    await expect(listCampaignRecipientMembershipOnServer(existingCampaign.id)).resolves.toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "campaign-atlas-ceo" }),
        expect.objectContaining({ id: "campaign-meridian-director" }),
      ]),
    );
    await expect(listCampaignRecipientMembershipOnServer(existingCampaign.id)).resolves.not.toEqual(
      expect.arrayContaining([expect.objectContaining({ id: "campaign-nova-retail" })]),
    );

    await replaceCampaignRecipientMembershipOnServer(existingCampaign.id, [
      "campaign-atlas-ceo",
      "campaign-nova-retail",
    ]);
    await expect(listCampaignRecipientMembershipOnServer(existingCampaign.id)).resolves.toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "campaign-atlas-ceo" }),
        expect.objectContaining({ id: "campaign-nova-retail" }),
      ]),
    );

    await replaceCampaignRecipientMembershipOnServer(existingCampaign.id, []);
    await expect(listCampaignRecipientMembershipOnServer(existingCampaign.id)).resolves.toEqual([]);

    const noGroupCampaign = await createCampaignOnServer({
      name: "Campanie fără grup",
      segment: null,
      subject: "Subiect liber",
      html_body: "<p>Salut.</p>",
      text_body: "Salut.",
    });
    await expect(listCampaignRecipientMembershipOnServer(noGroupCampaign.id)).resolves.toEqual([]);
  });

  it("loads and replaces campaign-specific recipient membership", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ([{ id: "recipient-1", email: "ana@example.com", membershipSource: "manual" }]),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ recipients: [{ id: "recipient-2", email: "ioana@example.com" }] }),
      } as Response);
    vi.stubGlobal("fetch", fetchMock);

    await expect(listCampaignRecipientMembershipOnServer("campaign-1")).resolves.toEqual([
      expect.objectContaining({ id: "recipient-1", membershipSource: "manual" }),
    ]);
    await expect(
      replaceCampaignRecipientMembershipOnServer("campaign-1", ["recipient-2"]),
    ).resolves.toEqual([
      expect.objectContaining({ id: "recipient-2" }),
    ]);

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining("/communications/campaigns/campaign-1/recipients"),
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining("/communications/campaigns/campaign-1/recipients"),
      expect.objectContaining({
        method: "PUT",
        credentials: "include",
        body: JSON.stringify({ recipient_ids: ["recipient-2"] }),
      }),
    );
  });

  it("deletes campaigns through the communications API", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    const fetchMock = vi.fn().mockResolvedValue({ ok: true } as Response);
    vi.stubGlobal("fetch", fetchMock);

    await deleteCampaignOnServer("campaign-1");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/communications/campaigns/campaign-1"),
      expect.objectContaining({
        method: "DELETE",
        credentials: "include",
      }),
    );
  });

  it("updates and deletes campaign contacts through the communications API", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ id: "recipient-1", email: "ana@example.com" }),
      } as Response)
      .mockResolvedValueOnce({ ok: true } as Response);
    vi.stubGlobal("fetch", fetchMock);

    await updateCampaignRecipientOnServer("recipient-1", {
      email: "ana@example.com",
      contact_name: "Ana",
      organization_name: "Compania A",
      segment: "potential_customer",
    });
    await deleteCampaignRecipientOnServer("recipient-1");

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining("/communications/campaigns/recipients/recipient-1"),
      expect.objectContaining({
        method: "PATCH",
        credentials: "include",
        body: JSON.stringify({
          email: "ana@example.com",
          contact_name: "Ana",
          organization_name: "Compania A",
          segment: "potential_customer",
        }),
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining("/communications/campaigns/recipients/recipient-1"),
      expect.objectContaining({
        method: "DELETE",
        credentials: "include",
      }),
    );
  });

  it("returns trainer dashboard placeholder data", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 } as Response));

    const summary = await getTrainerDashboardSummary();

    expect(summary.stats).toHaveLength(4);
    expect(summary.stats[0]).toMatchObject({ label: "Companii" });
    expect(summary.cards.map((card) => card.title)).toContain("Email");
    expect(summary.activeCompanies[0]).toMatchObject({
      id: "demo-project",
      company: "Atlas Mobility",
    });
    expect(Object.prototype.hasOwnProperty.call(summary.activeCompanies[0], "projectName")).toBe(false);
  });

  it("builds trainer dashboard rows around companies from backend data", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/companies/summary")) {
        return {
          ok: true,
          json: async () => [
            {
              id: "company-1",
              name: "Michelin",
              participant_count: 12,
              assignment_count: 10,
              completed_count: 6,
              scored_count: 3,
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
    expect(fetchMock).toHaveBeenCalledTimes(1);
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
              project_id: null,
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

  it("maps participant workspace data from the backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        participant_profile_id: "profile-1",
        participant_full_name: "Ana Participant",
        participant_email: "ana@example.com",
        company_id: "company-1",
        company_name: "Michelin",
        project_id: "project-1",
        project_name: "Leadership septembrie",
        pcm_base: "Gânditor",
        pcm_phase: "Perseverent",
        deadline_label: "30.09.2026",
        tasks: [
          {
            id: "assignment-1",
            title: "Lencioni",
            status: "not_started",
            detail: "Completează formularul.",
            href: "/participant/questionnaires/lencioni?assignmentId=assignment-1",
            assignmentId: "assignment-1",
            targetLabel: "Leadership",
            estimatedMinutes: 12,
            questionnaireKey: "lencioni",
          },
        ],
        results: [
          {
            assignment_id: "result-assignment-1",
            questionnaire_key: "distress_drivers",
            title: "Driveri de stres TA",
            target_label: "Autoevaluare",
            scores: { work_signal_a: { score: 72, label: "Semnal de lucru A" } },
            primary_result: "work_signal_a",
            score_unit: "percent",
            scale_min: 0,
            scale_max: 100,
            score_scale_compatible: true,
            unavailable_reason: null,
          },
        ],
        received_feedback: {
          completed_count: 2,
          minimum_completed: 2,
          visible: true,
          overall_average: 82,
          dimensions: [
            {
              id: "feedback_signal_a",
              label: "Claritate",
              average_score: 90,
              completed_count: 2,
            },
          ],
        },
        cards: [{ title: "De completat", description: "1 sarcini active", meta: "Acum" }],
        empty_state: { title: "Nu ai sarcini active", description: "Revino mai târziu." },
      }),
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const summary = await getParticipantWorkspaceSummary();

    expect(summary).toMatchObject({
      participantProfileId: "profile-1",
      participantFullName: "Ana Participant",
      participantEmail: "ana@example.com",
      companyName: "Michelin",
      projectName: "Leadership septembrie",
      pcmBase: "Gânditor",
      pcmPhase: "Perseverent",
      tasks: [expect.objectContaining({ assignmentId: "assignment-1" })],
      results: [
        expect.objectContaining({
          assignmentId: "result-assignment-1",
          scoreUnit: "percent",
          scaleMin: 0,
          scaleMax: 100,
          scoreScaleCompatible: true,
        }),
      ],
      receivedFeedback: {
        completedCount: 2,
        minimumCompleted: 2,
        visible: true,
        overallAverage: 82,
        dimensions: [
          {
            id: "feedback_signal_a",
            label: "Claritate",
            averageScore: 90,
            completedCount: 2,
          },
        ],
      },
      emptyState: expect.objectContaining({ title: "Nu ai sarcini active" }),
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/participants/me/workspace"),
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
      }),
    );
  });

  it("returns a participant workspace recovery state when the backend profile is unavailable", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({
        error: {
          code: "participant_profile_not_found",
          message: "Participant profile not found for this account.",
        },
      }),
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const summary = await getParticipantWorkspaceSummary();

    expect(summary).toMatchObject({
      participantFullName: "Participant",
      projectName: "Niciun proiect activ",
      tasks: [],
      emptyState: {
        title: "Spațiul nu este disponibil",
        description: "Profilul nu este încă legat de acest cont. Verifică adresa de email cu trainerul.",
      },
    });
  });

  it("maps multi-project participant results and grouped feedback without optional payload fields", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        participant_profile_id: "profile-1",
        participant_full_name: "Ana Participant",
        participant_email: "ana@example.com",
        company_id: "company-1",
        company_name: "Michelin",
        project_id: "project-2",
        project_name: "Leadership avansat",
        projects: [
          { id: "project-1", name: "Leadership de bază", deadline_label: "1 august" },
          { id: "project-2", name: "Leadership avansat", deadline_label: "15 august", deadline_at: "2026-08-15" },
        ],
        deadline_label: "15 august",
        tasks: [],
        results: [{
          assignment_id: "assignment-1",
          project_id: "project-1",
          project_name: "Leadership de bază",
          questionnaire_key: "lencioni",
          title: "Evaluare echipă",
          target_label: "Echipa Nord",
          scores: {},
        }],
        received_feedback_groups: [{
          project_id: "project-2",
          project_name: "Leadership avansat",
          completed_count: 1,
          minimum_completed: 2,
          visible: false,
        }],
        cards: [],
        empty_state: { title: "Fără sarcini", description: "Nu există activitate." },
      }),
    } as Response));

    const summary = await getParticipantWorkspaceSummary({ headers: { "X-Test": "true" } });

    expect(summary.projects).toEqual([
      {
        id: "project-1",
        name: "Leadership de bază",
        status: "active",
        historyBucket: "current",
        deadlineLabel: "1 august",
        deadlineAt: undefined,
      },
      {
        id: "project-2",
        name: "Leadership avansat",
        status: "active",
        historyBucket: "current",
        deadlineLabel: "15 august",
        deadlineAt: "2026-08-15",
      },
    ]);
    expect(summary.results[0]).toMatchObject({
      assignmentId: "assignment-1",
      projectId: "project-1",
      primaryResult: undefined,
    });
    expect(summary.receivedFeedback).toBeNull();
    expect(summary.receivedFeedbackGroups[0]).toMatchObject({
      visible: false,
      overallAverage: undefined,
      dimensions: [],
    });
  });

  it("reports participant workspace network failures when demo fallback is disabled", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    await expect(getParticipantWorkspaceSummary()).rejects.toMatchObject({
      name: "ParticipantWorkspaceError",
      status: 0,
      code: "network_error",
    });
  });

  it("preserves structured participant API errors and request references", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({
        error: { code: "permission_denied", message: "Acces refuzat.", request_id: "request-123" },
      }),
    } as Response));

    await expect(getParticipantWorkspaceSummary()).rejects.toMatchObject({
      status: 403,
      code: "permission_denied",
      message: "Acces refuzat.",
      requestId: "request-123",
    });
  });

  it("creates a stable HTTP error when the participant response is not JSON", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      status: 502,
      headers: new Headers({ "X-Request-ID": "proxy-456" }),
      json: async () => { throw new SyntaxError("invalid json"); },
    } as unknown as Response));

    await expect(getParticipantWorkspaceSummary()).rejects.toMatchObject({
      status: 502,
      code: "http_502",
      requestId: "proxy-456",
    });
  });

  it("uses synthetic participant data only when the local fallback is explicit", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("offline")));

    const summary = await getParticipantWorkspaceSummary();

    expect(summary.participantFullName).toBeTruthy();
    expect(summary.projects[0]?.id).toBe("synthetic-leadership-project");
    expect(summary.receivedFeedback?.visible).toBe(true);
    expect(summary.results).toHaveLength(2);
  });

  it("keeps questionnaire and email surfaces explicit", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false } as Response));

    const questionnaires = await listQuestionnaireDefinitionStubs();

    expect(questionnaires.map((definition) => definition.id)).toEqual(
      expect.arrayContaining(["boss_360", "pcm_base"]),
    );
    expect(questionnaires.map((definition) => definition.id)).not.toContain("phase");
    expect(questionnaires.map((definition) => definition.id)).not.toContain("lencioni_en");
    expect(questionnaires.map((definition) => definition.id)).not.toContain("distress_drivers_en");
    expect(questionnaires.map((definition) => definition.id)).not.toContain("boss_360_en");
    expect(questionnaires.map((definition) => definition.id)).not.toContain("icare");
    expect(questionnaires.find((definition) => definition.id === "boss_360")).toMatchObject({
      status: "active",
      estimatedItems: 2,
    });
    await expect(listEmailSurfaceStubs()).resolves.toEqual([
      { id: "assessment-invites", name: "Invitații assessment", lane: "transactional" },
      { id: "assessment-reminders", name: "Remindere assessment", lane: "transactional" },
      { id: "video-campaigns", name: "Campanii cu link video", lane: "campaign" },
    ]);
  });

  it("builds video campaign payloads with linked thumbnail images", () => {
    const payload = buildVideoCampaignCreatePayload({
      name: " Campanie video ",
      segment: "potential_customer",
      subject: "O idee pentru {first_name}",
      videoUrl: "https://video.codrut.ro/watch/intro",
      thumbnailUrl: "https://cdn.codrut.ro/thumb.jpg?size=large&variant=\"hero\"",
      landingUrl: "https://cody.andreivacaru.ro/watch/intro?source=email&name=\"hero\"",
    });

    expect(payload).toMatchObject({
      name: "Campanie video",
      segment: "potential_customer",
      subject: "O idee pentru ${first_name}",
      video_url: "https://video.codrut.ro/watch/intro",
      thumbnail_url: "https://cdn.codrut.ro/thumb.jpg?size=large&variant=%22hero%22",
      landing_page_url: "https://cody.andreivacaru.ro/watch/intro?source=email&name=%22hero%22",
    });
    expect(payload?.html_body).toContain('href="${landing_page_url}"');
    expect(payload?.html_body).toContain('<img src="${thumbnail_url}"');
    expect(payload?.text_body).toContain("${landing_page_url}");
  });

  it("adds the video block when authored campaign text has no media markup", () => {
    const payload = buildVideoCampaignCreatePayload({
      name: "Campanie editată",
      segment: "potential_customer",
      subject: "Salut",
      htmlBody: "<p>Mesaj personalizat.</p>",
      textBody: "Mesaj personalizat.",
      videoUrl: "https://vimeo.com/123456789",
      thumbnailUrl: "https://cdn.codrut.ro/thumb.jpg",
      landingUrl: "",
    });

    expect(payload?.html_body).toContain("<p>Mesaj personalizat.</p>");
    expect(payload?.html_body).toContain('href="${landing_page_url}"');
    expect(payload?.html_body).toContain('<img src="${thumbnail_url}"');
    expect(payload?.html_body.match(/\$\{thumbnail_url\}/g)).toHaveLength(1);
  });

  it("uses the video url as the campaign destination when landing page is empty", () => {
    const payload = buildVideoCampaignCreatePayload({
      name: "Campanie Vimeo",
      segment: "potential_customer",
      subject: "Salut",
      videoUrl: "https://vimeo.com/123456789",
      thumbnailUrl: "https://cdn.codrut.ro/thumb.jpg",
      landingUrl: "",
    });

    expect(payload).toMatchObject({
      video_url: "https://vimeo.com/123456789",
      thumbnail_url: "https://cdn.codrut.ro/thumb.jpg",
    });
    expect(payload?.landing_page_url).toBeUndefined();
    expect(payload?.html_body).toContain('href="${landing_page_url}"');
  });

  it("builds campaign payloads without video assets", () => {
    const payload = buildVideoCampaignCreatePayload({
      name: " Campanie fără video ",
      segment: "potential_customer",
      subject: "Salut {first_name}",
      videoUrl: "",
      thumbnailUrl: "",
      landingUrl: "",
    });

    expect(payload).toMatchObject({
      name: "Campanie fără video",
      segment: "potential_customer",
      subject: "Salut ${first_name}",
    });
    expect(payload?.video_url).toBeUndefined();
    expect(payload?.thumbnail_url).toBeUndefined();
    expect(payload?.landing_page_url).toBeUndefined();
    expect(payload?.html_body).not.toContain("<img");
  });

  it("builds image-only campaign drafts without a video destination", () => {
    const payload = buildVideoCampaignCreatePayload({
      name: " Campanie cu thumbnail ",
      segment: "past_customer",
      subject: "Salut {first_name}",
      videoUrl: "",
      thumbnailUrl: "https://cdn.codrut.ro/thumb.jpg",
      landingUrl: "",
    });

    expect(payload).toMatchObject({
      name: "Campanie cu thumbnail",
      segment: "past_customer",
      subject: "Salut ${first_name}",
      thumbnail_url: "https://cdn.codrut.ro/thumb.jpg",
    });
    expect(payload?.video_url).toBeUndefined();
    expect(payload?.landing_page_url).toBeUndefined();
    expect(payload?.html_body).toContain('<img src="${thumbnail_url}"');
    expect(payload?.html_body).not.toContain('href="${landing_page_url}"');
  });

  it("uploads campaign thumbnail assets as raw image bodies", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    const file = new File([new Uint8Array([137, 80, 78, 71])], "mini thumb.png", {
      type: "image/png",
    });
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        url: "https://cody.andreivacaru.ro/api/campaign-assets/mini.png",
        file_name: "mini.png",
        content_type: "image/png",
        size_bytes: 4,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(uploadCampaignAssetOnServer(file)).resolves.toMatchObject({
      url: "https://cody.andreivacaru.ro/api/campaign-assets/mini.png",
      content_type: "image/png",
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/communications/campaign-assets"),
      expect.objectContaining({
        method: "POST",
        body: file,
        credentials: "include",
        headers: expect.objectContaining({
          "Content-Type": "image/png",
          "X-File-Name": "mini%20thumb.png",
        }),
      }),
    );
  });

  it("cleans up owned campaign assets through the communications API", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 204 } as Response);
    vi.stubGlobal("fetch", fetchMock);

    await deleteCampaignAssetOnServer("campaign-image-owner-token.png");

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/communications/campaign-assets/campaign-image-owner-token.png"),
      expect.objectContaining({ method: "DELETE" }),
    );
    expect(campaignAssetFileNameFromUrl(
      "https://codrut.example/api/campaign-assets/campaign-image-owner-token.png",
    )).toBe("campaign-image-owner-token.png");
    expect(campaignAssetFileNameFromUrl("https://cdn.example/image.png")).toBeNull();
  });

  it("rejects incomplete or non-http video campaign URLs", () => {
    expect(buildVideoCampaignCreatePayload({
      name: "Campanie video",
      segment: "past_customer",
      subject: "Salut",
      videoUrl: "ftp://video.codrut.ro/watch/intro",
      thumbnailUrl: "https://cdn.codrut.ro/thumb.jpg",
      landingUrl: "https://cody.andreivacaru.ro/watch/intro",
    })).toBeNull();
    expect(buildVideoCampaignCreatePayload({
      name: "Campanie video",
      segment: "past_customer",
      subject: "Salut",
      videoUrl: "https://video.codrut.ro/watch/intro",
      thumbnailUrl: "",
      landingUrl: "",
    })).toBeNull();
    expect(buildVideoCampaignCreatePayload({
      name: "Campanie video",
      segment: "past_customer",
      subject: "Salut",
      videoUrl: "https://video.codrut.ro/watch/intro",
      thumbnailUrl: "https://cdn.codrut.ro/thumb.jpg",
      landingUrl: "not-a-url",
    })).toBeNull();
  });

  it("resolves invite bundle fallback states", async () => {
    await expect(resolveInviteBundle("demo-token")).resolves.toMatchObject({
      state: "valid",
      projectName: "Leadership operațional Q3",
      participantEmail: "participant.demo@example.com",
      tasks: [
        expect.objectContaining({
          title: "Driveri de stres TA",
          questionnaireKey: "distress_drivers",
          targetLabel: "Autoevaluare",
        }),
        expect.objectContaining({ targetLabel: "Echipa operațională Atlas" }),
        expect.objectContaining({
          title: "Feedback confidențial",
          detail: "Oferă feedback pentru persoana indicată în această sarcină.",
        }),
        expect.any(Object),
      ],
    });
    const demoBundle = await resolveInviteBundle("demo-token");
    expect(demoBundle.state === "valid" ? demoBundle.tasks[0].href : "").toContain("/participant/questionnaires/");
    expect(demoBundle.state === "valid" ? demoBundle.tasks[0].href : "").not.toContain("access=secure");
    await expect(resolveInviteBundle("expired-demo")).resolves.toMatchObject({
      state: "expired",
    });
  });

  it("keeps real permanent participant links from the backend on questionnaire routes", async () => {
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
            title: "Feedback pentru echipă",
            status: "not_started",
            detail: "Răspunde pentru echipa indicată în această sarcină.",
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
    const bundle = await resolveInviteBundle("real-token");
    expect(bundle.state === "valid" ? bundle.tasks[0].href : "").toBe(
      "/participant/questionnaires/lencioni?assignmentId=assignment-1",
    );
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/auth/invite/verify?token=real-token"),
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
      }),
    );
  });

  it("exchanges real invite tokens through an explicit unsafe request", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      action: "secure_link_ready",
      destination: "/invite/real-token",
      participant_profile_id: "participant-1",
    })));
    vi.stubGlobal("fetch", fetchMock);

    await exchangeInviteSession("real-token");

    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/auth/invite/exchange"),
      expect.objectContaining({
        method: "POST",
        cache: "no-store",
        credentials: "include",
        body: JSON.stringify({ token: "real-token" }),
      }),
    );
  });

  it("surfaces invite-session conflicts instead of reporting false success", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({
          error: {
            code: "invite_session_conflict",
            message: "Invitația aparține unui alt participant autentificat.",
          },
        }),
        { status: 409, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(exchangeInviteSession("real-token")).rejects.toThrow(
      "Invitația aparține unei alte sesiuni active.",
    );
  });

  it("marks invite session replacement only after explicit confirmation", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({
      action: "secure_link_ready",
      destination: "/invite/real-token",
      participant_profile_id: "participant-1",
    })));
    vi.stubGlobal("fetch", fetchMock);

    await exchangeInviteSession("real-token", { replaceExistingSession: true });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/auth/invite/exchange"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          token: "real-token",
          replace_existing_session: true,
        }),
      }),
    );
  });

  it("resolves real secure invite links through the backend when access is marked secure", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
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
            title: "Feedback pentru echipă",
            status: "not_started",
            detail: "Răspunde pentru echipa indicată în această sarcină.",
            href: "/participant/questionnaires/lencioni?assignmentId=assignment-1&access=secure&returnTo=%2Finvite%2Freal-secure-token",
            assignmentId: "assignment-1",
            targetLabel: "Leadership",
            estimatedMinutes: 12,
            questionnaireKey: "lencioni",
          },
        ],
      }),
    } as Response));

    const bundle = await resolveInviteBundle("real-secure-token");

    expect(bundle.state === "valid" ? bundle.tasks[0].href : "").toBe(
      "/invite/real-secure-token/tasks/assignment-1?returnTo=%2Finvite%2Freal-secure-token&target=Leadership",
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
      message: "Linkul a expirat. Cere un link nou de la trainer.",
    });
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it("localizes invalid invite errors by backend code", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({
        error: {
          code: "task_link_invalid",
          message: "Invalid task link.",
        },
      }),
    } as Response));

    await expect(resolveInviteBundle("invalid-real")).resolves.toMatchObject({
      state: "not_found",
      message: "Linkul de invitație nu este valid. Cere un link nou de la trainer.",
    });
  });

  it("keeps demo invite tokens unavailable when demo fallback is disabled", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(resolveInviteBundle("demo-token")).resolves.toMatchObject({
      state: "not_found",
      message: "Nu am găsit o invitație activă pentru acest link.",
    });
    await expect(resolveInviteBundle("expired-demo")).resolves.toMatchObject({
      state: "not_found",
      message: "Nu am găsit o invitație activă pentru acest link.",
    });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("uses seeded questionnaire response fallback for demo assignments", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    await expect(
      saveQuestionnaireResponse("11111111-1111-4111-8111-111111111111", { q1: 1, pcm_base: "thinker" }),
    ).resolves.toMatchObject({
      status: "draft",
      questionnaire_key: "lencioni",
      answers: { q1: 1, pcm_base: "thinker" },
    });
    await expect(
      submitQuestionnaireResponse("11111111-1111-4111-8111-111111111111", { q1: 1 }),
    ).resolves.toMatchObject({
      status: "submitted",
      questionnaire_key: "lencioni",
    });

  });

  it("passes keepalive through for exit-safe questionnaire saves", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "draft", answers: { q1: 1 } }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await saveQuestionnaireResponse(
      "assignment-1",
      { q1: 1 },
      { keepalive: true, expectedUpdatedAt: "2026-08-13T09:00:00Z" },
    );

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/forms/assignments/assignment-1/response"),
      expect.objectContaining({
        keepalive: true,
        body: JSON.stringify({
          answers: { q1: 1 },
          expected_updated_at: "2026-08-13T09:00:00Z",
        }),
      }),
    );
  });

  it("passes server-provided auth headers when loading an assignment draft", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        id: "response-1",
        assignment_id: "assignment-1",
        questionnaire_key: "lencioni",
        questionnaire_version: 1,
        status: "draft",
        answers: { q1: 2 },
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      getQuestionnaireResponse("assignment-1", {
        headers: { Cookie: "codrut_session=session-token" },
      }),
    ).resolves.toMatchObject({
      status: "draft",
      answers: { q1: 2 },
    });

    expect(fetchMock.mock.calls[0]?.[0]).toEqual(
      expect.stringContaining("/forms/assignments/assignment-1/response"),
    );
    expect(fetchMock.mock.calls[0]?.[1]).toMatchObject({
      cache: "no-store",
      credentials: "include",
    });
    expect(new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get("Cookie")).toBe(
      "codrut_session=session-token",
    );
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
    ).rejects.toThrow("Nu am putut trimite răspunsurile.");
  });

  it("surfaces stale participant-session errors from questionnaire saves", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 403,
      json: async () => ({
        error: {
          code: "http_403",
          message: "Sesiunea activă nu este un cont de participant.",
          request_id: "req-participant",
        },
      }),
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    const error = await saveQuestionnaireResponse("assignment-1", { q1: 1 }).catch((caught: unknown) => caught);

    expect(error).toMatchObject({
      name: "QuestionnaireRequestError",
      status: 403,
      message: "Sesiunea activă nu este un cont de participant.",
    });
    expect(error).toBeInstanceOf(QuestionnaireRequestError);
    expect(isQuestionnaireSessionError(error)).toBe(true);
  });

  it("resolves a synthetic boss 360 sample without bundling protected content", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    const definition = await getQuestionnaireDefinition("boss_360");

    expect(definition).toMatchObject({
      key: "boss_360",
      title: "Mostră sintetică: feedback 360",
    });
    expect(definition?.schema.sections[0]?.questions).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "sample_feedback_q1" }),
      ]),
    );
  });

  it("resolves a synthetic profile sample advertised in the trainer catalog", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    const definition = await getQuestionnaireDefinition("pcm_base@1");

    expect(definition).toMatchObject({
      key: "pcm_base",
      title: "Mostră sintetică: profil participant",
    });
    expect(definition?.schema.sections[0]?.questions).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "sample_profile_q1",
          type: "single_choice",
          scale: expect.arrayContaining([expect.objectContaining({ value: "sample_a", label: "Varianta A" })]),
        }),
      ]),
    );
  });

  it("does not fall back to demo sessions when fallback is disabled", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 } as Response));

    await expect(getTrainerSession()).rejects.toThrow("Trainer authentication required");
    await expect(getParticipantSession()).rejects.toThrow("Participant authentication required");
  });

  it("does not treat transient session API failures as logout when fallback is disabled", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 503 } as Response));

    await expect(getTrainerSession()).rejects.toBeInstanceOf(AuthSessionUnavailableError);
    await expect(getParticipantSession()).rejects.toThrow("Nu am putut verifica sesiunea");
  });

  it("uses local fallback instead of trapping on an opposite-role cookie during demo fallback", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          user_id: "participant-1",
          email: "participant@example.com",
          role: "participant",
        }),
      } as Response),
    );

    await expect(getTrainerSession()).resolves.toMatchObject({
      state: "fallback",
      user: {
        id: "trainer-local",
        role: "trainer",
      },
    });
    await expect(getParticipantSession()).resolves.toMatchObject({
      state: "authenticated",
      user: {
        id: "participant-1",
        role: "participant",
      },
    });
  });

  it("does not replace an authenticated role mismatch with demo fallback when fallback is disabled", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          user_id: "participant-1",
          email: "participant@example.com",
          role: "participant",
        }),
      } as Response),
    );

    await expect(getTrainerSession()).rejects.toBeInstanceOf(AuthRoleMismatchError);
  });

  it("does not replace an authenticated role mismatch with demo fallback on production-like API hosts", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "true";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "true";
    const originalInternalApiBaseUrl = process.env.INTERNAL_API_BASE_URL;
    const originalVitest = process.env.VITEST;

    delete process.env.VITEST;
    vi.stubGlobal("window", undefined);
    vi.stubEnv("NODE_ENV", "development");
    process.env.INTERNAL_API_BASE_URL = "https://api.codrut.ro/api";
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({
          user_id: "participant-1",
          email: "participant@example.com",
          role: "participant",
        }),
      } as Response),
    );

    try {
      await expect(getTrainerSession()).rejects.toBeInstanceOf(AuthRoleMismatchError);
    } finally {
      if (originalInternalApiBaseUrl === undefined) {
        delete process.env.INTERNAL_API_BASE_URL;
      } else {
        process.env.INTERNAL_API_BASE_URL = originalInternalApiBaseUrl;
      }
      if (originalVitest === undefined) {
        delete process.env.VITEST;
      } else {
        process.env.VITEST = originalVitest;
      }
    }
  });

  it("loads the active authenticated session without demo fallback", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        user_id: "trainer-1",
        email: "trainer@example.com",
        role: "trainer",
      }),
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    await expect(getAuthenticatedSession()).resolves.toMatchObject({
      state: "authenticated",
      user: {
        id: "trainer-1",
        email: "trainer@example.com",
        role: "trainer",
      },
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/auth/me"),
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
      }),
    );
  });

  it("returns null for missing active authenticated sessions", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 } as Response));

    await expect(getAuthenticatedSession()).resolves.toBeNull();
  });

  it("changes password through the authenticated backend endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);

    await expect(changePassword("old-password-123", "New-password-123")).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/auth/change-password"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({
          current_password: "old-password-123",
          new_password: "New-password-123",
        }),
      }),
    );
  });

  it("rejects weak password changes before calling the backend", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(changePassword("old-password-123", "weakpw")).rejects.toThrow(
      "Parola trebuie să aibă cel puțin 8 caractere.",
    );
    expect(fetchMock).not.toHaveBeenCalled();
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

  it("does not fabricate companies when backend creation returns unauthorized in demo mode", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "true";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "true";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 } as Response));

    await expect(createCompany("Local-only Company")).rejects.toThrow(
      "Nu sunteți autentificat. Vă rugăm să vă reconectați.",
    );
  });

  it("does not fabricate companies when backend creation cannot be reached in demo mode", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "true";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "true";
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed to fetch")));

    await expect(createCompany("Local-only Company")).rejects.toThrow("failed to fetch");
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

  it("reads and repairs participant account links with an explicit audit reason", async () => {
    const status = {
      participant_id: "participant-1",
      participant_email: "person@example.com",
      linked_account: null,
      matching_email_account: {
        user_id: "user-1",
        email: "person@example.com",
        role: "trainer",
        is_shadow_account: false,
      },
      matching_account_is_linked: false,
    };
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(status)))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        ...status,
        linked_account: status.matching_email_account,
        matching_account_is_linked: true,
      })));
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      getParticipantAccountLinkStatus("company-1", "participant-1"),
    ).resolves.toMatchObject(status);
    await expect(
      repairParticipantAccountLink("company-1", "participant-1", {
        action: "link_matching_email",
        confirmationEmail: "person@example.com",
        reason: "Conflict verified with the account owner.",
      }),
    ).resolves.toMatchObject({ matching_account_is_linked: true });

    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining(
        "/companies/company-1/participants/participant-1/account-link/repair",
      ),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({
          action: "link_matching_email",
          confirmation_email: "person@example.com",
          reason: "Conflict verified with the account owner.",
        }),
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
        ok: false,
        status: 404,
      } as Response)
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

  it("loads company cards from the aggregate summary endpoint without per-company fanout", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => [
        {
          id: "company-1",
          name: "Michelin",
          participant_count: 8,
          project_count: 2,
          assignment_count: 16,
          completed_count: 4,
          scored_count: 2,
          stage: "completion",
        },
      ],
    } as Response);

    await expect(getCompanyList()).resolves.toEqual([
      {
        id: "company-1",
        name: "Michelin",
        participantCount: 8,
        projectCount: 2,
        assignmentCount: 16,
        completedCount: 4,
        stage: "completion",
      },
    ]);

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/companies/summary"),
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
      }),
    );
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
      expect.arrayContaining(["demo-project", "leadership-pilot", "past-client-video", "nova-retail"]),
    );
  });

  it("skips protected company fetches in browser demo fallback without a session cookie", async () => {
    const previousVitest = process.env.VITEST;
    delete process.env.VITEST;
    document.cookie = "codrut_session=; Max-Age=0; path=/";
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    try {
      const companies = await getCompanyList();

      expect(companies.map((company) => company.id)).toEqual([
        "demo-project",
        "leadership-pilot",
        "past-client-video",
        "nova-retail",
      ]);
      expect(fetchMock).not.toHaveBeenCalled();
    } finally {
      if (previousVitest) {
        process.env.VITEST = previousVitest;
      }
    }
  });

  it("keeps project routes backed by consistent localhost demo fallback data", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401 }));

    await expect(getAllCompanyProjects()).resolves.toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "demo-project",
          company_id: "demo-project",
          name: "Leadership operațional Q3",
        }),
        expect.objectContaining({
          id: "leadership-pilot",
          company_id: "leadership-pilot",
          name: "Pilot leadership iulie",
        }),
      ]),
    );
    await expect(getCompanyProjectById("demo-project")).resolves.toEqual(
      expect.objectContaining({
        id: "demo-project",
        company_id: "demo-project",
        name: "Leadership operațional Q3",
      }),
    );
    await expect(getCompanyProjects("demo-project")).resolves.toEqual([
      expect.objectContaining({ id: "demo-project", company_id: "demo-project" }),
      expect.objectContaining({ id: "atlas-retrospective", status: "completed" }),
    ]);
    await expect(getCompanyParticipants("demo-project")).resolves.toEqual([
      expect.objectContaining({ id: "radu-munteanu", full_name: "Radu Munteanu" }),
      expect.objectContaining({ id: "bianca-pavel", reports_to_name: "Radu Munteanu" }),
      expect.objectContaining({ id: "sorin-dima", reports_to_name: "Radu Munteanu" }),
      expect.objectContaining({ id: "mihai-matei", reports_to_name: "Bianca Pavel" }),
      expect.objectContaining({ id: "ana-stan", reports_to_name: "Bianca Pavel" }),
      expect.objectContaining({ id: "claudia-neagu", reports_to_name: "Sorin Dima" }),
    ]);
    await expect(getProjectParticipants("demo-project", "demo-project")).resolves.toHaveLength(6);
    await expect(getAssessmentCycles("demo-project", "demo-project")).resolves.toEqual([
      expect.objectContaining({
        id: "demo-project-cycle-1",
        project_id: "demo-project",
        sequence: 1,
        status: "active",
      }),
    ]);

    const assignments = await getCompanyAssignments("demo-project", {}, { projectId: "demo-project" });
    expect(assignments.map((assignment) => assignment.id)).toEqual([
      "atlas-lencioni-radu",
      "atlas-lencioni-bianca",
      "atlas-lencioni-sorin",
      "atlas-driver-mihai",
      "atlas-driver-ana",
      "atlas-driver-claudia",
      "atlas-360-radu-bianca",
      "atlas-360-radu-sorin",
    ]);

    await expect(getCompanyReportAggregate("demo-project", {}, { projectId: "demo-project" })).resolves.toMatchObject({
      total_assigned: 8,
      total_completed: 6,
      lencioni_count: 3,
      driver_count: 1,
      boss_360_count: 2,
      driver_rank_summary: {
        total_people: 1,
        first_rank: [{ id: "hurry_up", label: "Grăbește-te", value: 1 }],
        second_rank: [{ id: "try_hard", label: "Străduiește-te", value: 1 }],
        first_rank_tie_breaks: 0,
        second_rank_tie_breaks: 0,
        insufficient_driver_score_count: 0,
      },
      pcm_base_count: 0,
      pcm_phase_count: 0,
      pcm_base_distribution: [],
      pcm_phase_distribution: [],
      hierarchy_ambiguous: false,
      hierarchy_ambiguity_message: null,
      hierarchy_issues: [],
      team_lenses: [
        expect.objectContaining({
          id: "leadership",
          name: "Leadership",
          member_count: 6,
          assigned_count: 8,
          completed_count: 6,
          driver_count: 1,
        }),
      ],
      results: expect.arrayContaining([
        expect.objectContaining({ assignment_id: "atlas-lencioni-radu" }),
        expect.objectContaining({ assignment_id: "atlas-driver-claudia" }),
      ]),
    });

    await expect(getCompanyProjects("leadership-pilot")).resolves.toEqual([
      expect.objectContaining({ id: "leadership-pilot", company_id: "leadership-pilot" }),
    ]);
    await expect(getCompanyParticipants("leadership-pilot")).resolves.toEqual([
      expect.objectContaining({ id: "alex-dima", role_group: "manager", user_id: "user-alex-dima" }),
      expect.objectContaining({ id: "mara-ionescu", reports_to_name: "Alex Dima", role_group: "manager" }),
      expect.objectContaining({ id: "sorin-pavel", reports_to_name: "Alex Dima", role_group: "manager" }),
      expect.objectContaining({ id: "diana-luca", reports_to_name: "Mara Ionescu", role_group: "member" }),
      expect.objectContaining({ id: "tudor-stan", reports_to_name: "Mara Ionescu", role_group: "member" }),
      expect.objectContaining({ id: "ioana-rusu", reports_to_name: "Sorin Pavel", role_group: "member" }),
    ]);
    await expect(getProjectParticipants("leadership-pilot", "leadership-pilot")).resolves.toHaveLength(6);

    const leadershipAssignments = await getCompanyAssignments("leadership-pilot", {}, { projectId: "leadership-pilot" });
    expect(leadershipAssignments).toHaveLength(23);
    expect(leadershipAssignments).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "leadership-lencioni-alex",
          target_type: "team",
          target_team_id: "leadership",
        }),
        expect.objectContaining({
          id: "icare-mara-on-alex",
          questionnaire_key: "boss_360",
          target_person_id: "alex-dima",
        }),
        expect.objectContaining({
          id: "icare-ioana-on-sorin",
          questionnaire_key: "boss_360",
          target_person_id: "sorin-pavel",
        }),
      ]),
    );

    await expect(getCompanyReportAggregate("leadership-pilot", {}, { projectId: "leadership-pilot" })).resolves.toMatchObject({
      total_assigned: 23,
      total_completed: 23,
      lencioni_count: 6,
      driver_count: 3,
      boss_360_count: 11,
      driver_rank_summary: {
        total_people: 3,
        first_rank: expect.arrayContaining([
          { id: "be_perfect", label: "Fii perfect", value: 1 },
          { id: "hurry_up", label: "Grăbește-te", value: 1 },
          { id: "try_hard", label: "Străduiește-te", value: 1 },
        ]),
        second_rank: expect.arrayContaining([
          { id: "try_hard", label: "Străduiește-te", value: 2 },
          { id: "be_perfect", label: "Fii perfect", value: 1 },
        ]),
        first_rank_tie_breaks: 0,
        second_rank_tie_breaks: 0,
        insufficient_driver_score_count: 0,
      },
      pcm_base_count: 3,
      pcm_phase_count: 3,
      pcm_base_distribution: expect.arrayContaining([
        expect.objectContaining({ id: "harmonizer", value: 1 }),
        expect.objectContaining({ id: "persister", value: 1 }),
        expect.objectContaining({ id: "thinker", value: 1 }),
      ]),
      pcm_phase_distribution: expect.arrayContaining([
        expect.objectContaining({ id: "harmonizer", value: 1 }),
        expect.objectContaining({ id: "persister", value: 1 }),
        expect.objectContaining({ id: "thinker", value: 1 }),
      ]),
      hierarchy_ambiguous: false,
      hierarchy_issues: [],
      team_lenses: [
        expect.objectContaining({
          id: "leadership",
          member_count: 6,
          assigned_count: 23,
          completed_count: 23,
          pcm_base_count: 3,
        }),
      ],
      results: expect.arrayContaining([
        expect.objectContaining({ assignment_id: "leadership-lencioni-alex" }),
        expect.objectContaining({ assignment_id: "icare-mara-on-alex" }),
      ]),
    });
  });

  it("loads trainer iCARE answer review rows with project scoping", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        rows: [
          {
            assignment_id: "assignment-1",
            response_id: "response-1",
            submitted_at: "2026-07-14T12:00:00+00:00",
            respondent_profile_id: "respondent-1",
            respondent_name: "Reviewer One",
            respondent_email: "reviewer@example.com",
            target_profile_id: "target-1",
            target_name: "Target Leader",
            target_type: "person",
            section_id: "sample_section",
            section_label: "Secțiune sintetică",
            measurement_id: "feedback_signal_a",
            measurement_label: "Claritate",
            statement_id: "sample_statement_a",
            statement_label: "Clarifică rezultatul așteptat",
            answer_value: 1,
            answer_label: "1",
            answer_description: "Comportamentul nu a fost observat.",
          },
        ],
        row_count: 1,
      }),
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    await expect(
      getIcareAnswerReview("company-1", {}, { projectId: "project-1" }),
    ).resolves.toMatchObject({
      row_count: 1,
      rows: [
        expect.objectContaining({
          respondent_name: "Reviewer One",
          target_name: "Target Leader",
          statement_label: "Clarifică rezultatul așteptat",
          answer_description: "Comportamentul nu a fost observat.",
        }),
      ],
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/companies/company-1/reports/icare-answers?project_id=project-1"),
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("keeps seeded company detail routes local instead of calling UUID-only backend endpoints", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    await expect(getCompanyDetail("leadership-pilot")).resolves.toMatchObject({
      id: "leadership-pilot",
      name: "Echipa direcție",
      projects: [expect.objectContaining({ id: "leadership-pilot" })],
      participants: expect.arrayContaining([
        expect.objectContaining({ id: "alex-dima" }),
      ]),
    });
    expect(fetchMock).not.toHaveBeenCalled();
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
        projectId: "project-1",
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
          project_id: "project-1",
          mode: "secure_links",
          target_mode: "selected",
          force_rotate: false,
        }),
      }),
    );
  });

  it("surfaces roster import validation details from the backend", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 422,
      json: async () => ({
        error: {
          code: "validation_error",
          message: "Request validation failed.",
          request_id: "req-validation",
          details: [
            {
              loc: ["body", "rows", 0, "email"],
              message: "value is not a valid email address: The part after the @-sign is a special-use or reserved name",
              type: "value_error",
            },
          ],
        },
      }),
    } as Response);

    await expect(
      importCompanyRoster("company-1", [
        {
          Name: "Ana",
          "Reports To": "",
          Position: "Member",
          Location: "Bucharest",
          email: "ana@example.test",
          "Profil PCM": "",
        },
      ]),
    ).rejects.toThrow("rows.0.email: value is not a valid email address");
  });

  it("submits blank and malformed roster emails for backend inactive-row classification", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        participants: [],
        email_results: [],
        total_imported: 2,
        emails_sent: 0,
        emails_failed: 0,
      }),
    } as Response);

    await importCompanyRoster("company-1", [
      {
        Name: "Fără Email",
        "Reports To": "",
        Position: "Member",
        Location: "Bucharest",
        email: "",
        "Profil PCM": "",
      },
      {
        Name: "Email Invalid",
        "Reports To": "",
        Position: "Member",
        Location: "Bucharest",
        email: "not-an-email",
        "Profil PCM": "",
      },
    ]);

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(String(init.body))).toMatchObject({
      rows: [
        expect.objectContaining({ Name: "Fără Email", email: "" }),
        expect.objectContaining({ Name: "Email Invalid", email: "not-an-email" }),
      ],
      send_invites: false,
    });
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

    await expect(resendParticipantInvitation("company-1", "participant-1", "project-1")).resolves.toMatchObject({
      participant_id: "participant-1",
      email_sent: true,
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/companies/company-1/participants/participant-1/resend-invite?project_id=project-1"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
      }),
    );
  });

  it("creates company assignments through the backend", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        id: "assignment-1",
        company_id: "company-1",
        project_id: "project-1",
        respondent_profile_id: "participant-1",
        questionnaire_key: "boss_360",
        target_type: "person",
        target_person_id: "participant-2",
        target_team_id: null,
        access_mode: "account_link",
        status: "assigned",
        visibility_policy: "trainer_raw_review",
        due_at: null,
        invited_at: null,
        started_at: null,
        submitted_at: null,
        validated_at: null,
        scored_at: null,
        reminder_due_at: null,
        last_reminder_sent_at: null,
      }),
    } as Response);

    await expect(
      createCompanyAssignment("company-1", {
        projectId: "project-1",
        respondentProfileId: "participant-1",
        questionnaireKey: "boss_360",
        targetType: "person",
        targetPersonId: "participant-2",
      }),
    ).resolves.toMatchObject({
      id: "assignment-1",
      target_type: "person",
      target_person_id: "participant-2",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/companies/company-1/assignments"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({
          respondent_profile_id: "participant-1",
          project_id: "project-1",
          questionnaire_key: "boss_360",
          target_type: "person",
          target_person_id: "participant-2",
          target_team_id: null,
          visibility_policy: "trainer_raw_review",
        }),
      }),
    );
  });

  it("gets and saves the default company assignment plan through the backend", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          project_id: "project-1",
          scopes: [
            {
              id: "leadership",
              name: "Leadership",
              type: "leadership_team",
              participant_ids: ["participant-1"],
            },
          ],
          assignments: [
            {
              key: "leadership:participant-1:lencioni:team:Leadership",
              scope_id: "leadership",
              scope_name: "Leadership",
              scope_type: "leadership_team",
              respondent_profile_id: "participant-1",
              respondent_name: "Ana",
              questionnaire_key: "lencioni",
              target_type: "team",
              target_person_id: null,
              target_person_name: null,
              target_team_id: null,
              target_team_name: "Leadership",
              target_team_type: "leadership",
              target_team_member_ids: ["participant-1"],
              target_team_leader_id: null,
              visibility_policy: "trainer_raw_review",
              selected: true,
              existing_assignment_id: null,
            },
          ],
          suggested_count: 1,
          existing_count: 0,
        }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          assignments: [{ id: "assignment-1", target_type: "team" }],
          created_count: 1,
          existing_count: 0,
        }),
      } as Response);

    const plan = await getCompanyDefaultAssignmentPlan("company-1", {}, { projectId: "project-1" });

    expect(plan.assignments[0]).toMatchObject({
      respondent_profile_id: "participant-1",
      target_team_name: "Leadership",
    });

    await expect(saveCompanyDefaultAssignmentPlan("company-1", plan.assignments, "project-1")).resolves.toMatchObject({
      created_count: 1,
    });

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      expect.stringContaining("/companies/company-1/assignments/default-plan?project_id=project-1"),
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      expect.stringContaining("/companies/company-1/assignments/default-plan?project_id=project-1"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({
          project_id: "project-1",
          assignments: [
            {
              respondent_profile_id: "participant-1",
              questionnaire_key: "lencioni",
              target_type: "team",
              target_person_id: null,
              target_team_id: null,
              target_team_name: "Leadership",
              target_team_type: "leadership",
              target_team_member_ids: ["participant-1"],
              target_team_leader_id: null,
              visibility_policy: "trainer_raw_review",
            },
          ],
        }),
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
      } as Response)
      .mockResolvedValueOnce({ ok: true } as Response);

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
    await expect(
      removeCompanyTeamMembership("company-1", "team-1", "membership-2"),
    ).resolves.toBeUndefined();

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
    expect(fetchMock).toHaveBeenNthCalledWith(
      4,
      expect.stringContaining(
        "/companies/company-1/teams/team-1/memberships/membership-2",
      ),
      expect.objectContaining({
        method: "DELETE",
        credentials: "include",
      }),
    );
  });

  it("lists only latest active questionnaire definitions by default", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => [
        {
          key: "boss_360",
          version: 1,
          title: "Boss / manager 360 old",
          description: "Old feedback form",
          schema: {
            schema_version: "questionnaire.v1",
            audience: "participant",
            sections: [],
          },
        },
        {
          key: "boss_360",
          version: 2,
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
        version: 2,
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

  it("dedupes repeated questionnaire definition list lookups", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [
        {
          key: "boss_360",
          version: 2,
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
    vi.stubGlobal("fetch", fetchMock);

    await Promise.all([
      listQuestionnaireDefinitionStubs(),
      listQuestionnaireDefinitionStubs(),
    ]);

    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("can list all questionnaire versions when requested", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => [
        {
          key: "boss_360",
          version: 1,
          title: "Boss / manager 360 old",
          description: "Old feedback form",
          schema: {
            schema_version: "questionnaire.v1",
            audience: "participant",
            sections: [],
          },
        },
        {
          key: "boss_360",
          version: 2,
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

    await expect(listQuestionnaireDefinitionStubs(false, { latestOnly: false })).resolves.toEqual([
      expect.objectContaining({ id: "boss_360", version: 1 }),
      expect.objectContaining({ id: "boss_360", version: 2 }),
    ]);
  });

  it("groups questionnaire stubs by key with newest versions first", () => {
    const grouped = groupQuestionnaireStubsByKey([
      {
        id: "boss_360",
        name: "Boss 360 v1",
        description: "",
        status: "active",
        version: 1,
        audience: "participant",
      },
      {
        id: "lencioni",
        name: "Lencioni",
        description: "",
        status: "active",
        version: 1,
        audience: "team",
      },
      {
        id: "boss_360",
        name: "Boss 360 v3",
        description: "",
        status: "active",
        version: 3,
        audience: "participant",
      },
    ]);

    expect(grouped.get("boss_360")?.map((stub) => stub.version)).toEqual([3, 1]);
    expect(grouped.get("lencioni")?.map((stub) => stub.version)).toEqual([1]);
  });

  it("can list inactive questionnaire drafts for the trainer editor", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => [
        {
          key: "draft_custom",
          version: 1,
          title: "Draft custom",
          description: "",
          active: false,
          schema: {
            schema_version: "questionnaire.v1",
            audience: "team",
            sections: [{ id: "sectiunea_1", title: "Secțiunea 1", questions: [] }],
          },
        },
      ],
    } as Response);

    await expect(listQuestionnaireDefinitionStubs(true)).resolves.toEqual([
      expect.objectContaining({
        id: "draft_custom",
        status: "draft",
      }),
    ]);

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/forms\/definitions\?include_retired=true$/),
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
      }),
    );
  });

  it("caches questionnaire definitions and clears the cache after trainer edits", async () => {
    const definition: QuestionnaireDefinition = {
      key: "boss_360",
      version: 2,
      title: "Boss / manager 360",
      description: "Feedback form",
      schema: {
        schema_version: "questionnaire.v1",
        audience: "participant",
        sections: [],
      },
    };
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => definition,
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ...definition, title: "Updated 360" }),
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ ...definition, title: "Updated 360" }),
      } as Response);
    vi.stubGlobal("fetch", fetchMock);

    await expect(getQuestionnaireDefinition("boss_360")).resolves.toMatchObject({ title: "Boss / manager 360" });
    await expect(getQuestionnaireDefinition("boss_360")).resolves.toMatchObject({ title: "Boss / manager 360" });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await updateQuestionnaireDefinitionOnServer("boss_360", {
      title: "Updated 360",
      description: definition.description,
      schema: definition.schema,
    });
    await expect(getQuestionnaireDefinition("boss_360")).resolves.toMatchObject({ title: "Updated 360" });

    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      expect.stringMatching(/\/forms\/definitions\/boss_360$/),
      expect.objectContaining({ cache: "no-store" }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      expect.stringMatching(/\/forms\/definitions\/boss_360$/),
      expect.objectContaining({ method: "PUT" }),
    );
  });

  it("lists email templates without retired templates by default and deletes by key", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: async () => [
          {
            key: "account_setup",
            version: 1,
            name: "Account setup",
            subject: "Setup",
            html_body: "<p>Body</p>",
            text_body: "Body",
            variables: [],
            audience: "transactional",
            active: true,
          },
        ],
      } as Response)
      .mockResolvedValueOnce({
        ok: true,
        text: async () => "",
      } as Response);

    await expect(listEmailTemplatesOnServer()).resolves.toEqual([
      expect.objectContaining({ baseKey: "account_setup", version: 1 }),
    ]);
    await expect(deleteEmailTemplateOnServer("account_setup")).resolves.toBeNull();

    expect(fetchMock).toHaveBeenNthCalledWith(
      1,
      expect.stringMatching(/\/communications\/templates\?include_retired=false$/),
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
      }),
    );
    expect(fetchMock).toHaveBeenNthCalledWith(
      2,
      expect.stringMatching(/\/communications\/templates\/account_setup$/),
      expect.objectContaining({
        method: "DELETE",
        credentials: "include",
      }),
    );
  });

  it("falls back only to synthetic editable campaign and evaluation samples", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    const templates = await listEmailTemplatesOnServer();
    const keys = templates.map((template) => template.baseKey);
    const update = templates.find((template) => template.baseKey === "preview_campaign_update");
    const leadershipInvite = templates.find((template) => template.baseKey === "preview_evaluation_invite");

    expect(keys).toContain("preview_campaign_update");
    expect(keys).toContain("preview_campaign_intro");
    expect(keys).toContain("preview_evaluation_invite");
    expect(keys).not.toContain("account_setup");
    expect(keys).not.toContain("assignment_bundle");
    expect(update).toMatchObject({
      version: 1,
      lane: "campaign",
      audience: "campaign:past_customer",
    });
    expect(update?.body).toContain("conținut sintetic");
    expect(update?.textBody).toContain("conținut sintetic");
    expect(update?.placeholders).toContain("{thumbnail_url}");
    expect(leadershipInvite).toMatchObject({ version: 1, audience: "transactional:leadership" });
    expect(leadershipInvite?.body).toContain("Activitate demonstrativă");
    expect(leadershipInvite?.textBody).toContain("{action_url}");
  });

  it("preserves server text bodies when saving existing HTML email templates", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        key: "promo_test",
        version: 2,
        subject: "Raport pentru ${first_name}",
        html_body: "<p>ok</p>",
        text_body: "ok",
        variables: ["first_name", "calendly_url"],
        audience: "campaign:past_customer",
        active: true,
      }),
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    await updateEmailTemplateOnServer({
      id: "promo_test@1",
      baseKey: "promo_test",
      version: 1,
      name: "Promo test",
      subject: "Raport pentru {first_name}",
      lane: "campaign",
      audience: "campaign:past_customer",
      placeholders: ["{first_name}", "{calendly_url}"],
      body:
        '<table><tr><td style="color:#890505;">✓</td><td>Exemplul sintetic a fost verificat.</td></tr><tr><td>✗</td><td>Exemplul sintetic necesită revizuire.</td></tr></table><p><a href="{calendly_url}" data-codrut-cta="calendly">Alege un slot</a></p>',
      textBody:
        "Salut, {first_name}.\nVideo: {landing_page_url}\nAlege un slot: {calendly_url}",
    });

    const payload = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(payload.text_body).toBe(
      "Salut, ${first_name}.\nVideo: ${landing_page_url}\nAlege un slot: ${calendly_url}",
    );
    expect(payload.variables).toEqual(expect.arrayContaining(["first_name", "landing_page_url", "calendly_url"]));
    expect(payload.html_body).toContain('data-codrut-cta="calendly"');
  });

  it("generates readable fallback text bodies for new HTML email templates", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        key: "promo_test",
        version: 1,
        subject: "Raport pentru ${first_name}",
        html_body: "<p>ok</p>",
        text_body: "ok",
        variables: ["first_name", "calendly_url"],
        audience: "campaign:past_customer",
        active: true,
      }),
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    await createEmailTemplateOnServer({
      id: "promo_test",
      baseKey: "promo_test",
      version: 0,
      name: "Promo test",
      subject: "Raport pentru {first_name}",
      lane: "campaign",
      audience: "campaign:past_customer",
      placeholders: ["{first_name}", "{calendly_url}"],
      body:
        '<table><tr><td style="color:#890505;">✓</td><td>Exemplul sintetic a fost verificat.</td></tr><tr><td>✗</td><td>Exemplul sintetic necesită revizuire.</td></tr></table><p><a href="{calendly_url}" data-codrut-cta="calendly">Alege un slot</a></p>',
    });

    const payload = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(payload.text_body).toContain("✓ Exemplul sintetic a fost verificat.");
    expect(payload.text_body).toContain("✗ Exemplul sintetic necesită revizuire.");
    expect(payload.text_body).toContain("Alege un slot");
    expect(payload.text_body).toContain("${calendly_url}");
    expect(payload.text_body).not.toContain("<td>");
  });

  it("keeps href-only links in generated plain text email bodies", () => {
    const text = htmlToPlainText(
      '<p>Video de reconectare</p><a href="{landing_page_url}"><span><img alt="Video" src="{thumbnail_url}" /></span></a><p><a href="{calendly_url}">Alege un slot</a></p>',
    );

    expect(text).toContain("Video {landing_page_url}");
    expect(text).toContain("Alege un slot {calendly_url}");
  });

  it("does not return seeded email templates when demo fallback is disabled", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 503 } as Response));

    await expect(listEmailTemplatesOnServer()).rejects.toThrow("Server returned status 503");
  });

  it("omits key field from update template payload and includes key in create payload", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        key: "test_template",
        version: 2,
        subject: "Subiect actualizat",
        html_body: "<p>Continut</p>",
        text_body: "Continut",
        variables: ["action_url"],
        audience: "transactional",
        active: true,
      }),
    } as Response);
    vi.stubGlobal("fetch", fetchMock);

    await updateEmailTemplateOnServer({
      id: "test_template@1",
      baseKey: "test_template",
      version: 1,
      name: "Test",
      subject: "Subiect actualizat",
      lane: "transactional",
      placeholders: ["{action_url}"],
      body: "<p>Continut {action_url}</p>",
      textBody: "Continut {action_url}",
    });

    const updatePayload = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(updatePayload.key).toBeUndefined();
    expect(updatePayload.subject).toBe("Subiect actualizat");
    expect(updatePayload.variables).toEqual(["action_url"]);

    await createEmailTemplateOnServer({
      id: "test_template@2",
      baseKey: "test_template",
      version: 1,
      name: "Test",
      subject: "Subiect nou",
      lane: "transactional",
      placeholders: ["{action_url}"],
      body: "<p>Continut {action_url}</p>",
      textBody: "Continut {action_url}",
    });

    const createPayload = JSON.parse(String(fetchMock.mock.calls[1]?.[1]?.body));
    expect(createPayload.key).toBe("test_template");
    expect(createPayload.subject).toBe("Subiect nou");
  });

  it("formats detailed validation errors and domain errors in Romanian", () => {
    const pydanticError = {
      error: {
        code: "validation_error",
        message: "Request validation failed.",
        details: [
          { loc: ["body", "key"], message: "Extra inputs are not permitted", type: "extra_forbidden" },
        ],
      },
    };
    expect(formatEmailTemplateApiError(pydanticError, "Eroare")).toBe("Câmpul „key” nu este permis.");

    const undeclaredError = {
      error: {
        code: "email_template_undeclared_variables",
        message: "Template contains undeclared variables: due_date, sender_name",
      },
    };
    expect(formatEmailTemplateApiError(undeclaredError, "Eroare")).toBe(
      "Șablonul conține variabile nedeclarate: due_date, sender_name",
    );
  });
});

describe("TA demo report aggregation", () => {
  const assignment = (
    id: string,
    respondentProfileId: string,
    createdAt: string,
  ): CompanyAssignment => ({
    id,
    created_at: createdAt,
    company_id: "demo-project",
    project_id: "demo-project",
    respondent_profile_id: respondentProfileId,
    questionnaire_key: "distress_drivers",
    target_type: "self",
    target_person_id: null,
    target_team_id: null,
    status: "scored",
    submitted_at: createdAt,
    scored_at: createdAt,
  });

  const result = (
    assignmentId: string,
    scores: Record<string, unknown>,
  ): CompanyScoringResult => ({
    id: `result-${assignmentId}`,
    assignment_id: assignmentId,
    scores,
    primary_result: null,
  });

  it("uses one latest-valid participant population for averages and both pies", () => {
    const olderValid = assignment(
      "driver-older-valid",
      "participant-1",
      "2026-07-29T08:00:00.000Z",
    );
    const newerInvalid = assignment(
      "driver-newer-invalid",
      "participant-1",
      "2026-07-30T08:00:00.000Z",
    );
    const onlyInvalid = assignment(
      "driver-only-invalid",
      "participant-2",
      "2026-07-30T09:00:00.000Z",
    );

    const aggregate = buildFallbackDriverAggregate(
      [olderValid, newerInvalid, onlyInvalid],
      [
        result(olderValid.id, {
          be_perfect: 80,
          hurry_up: 60,
          try_hard: 20,
        }),
        result(newerInvalid.id, { be_perfect: 99 }),
        result(onlyInvalid.id, { hurry_up: 90 }),
      ],
    );

    expect(aggregate.driverCount).toBe(1);
    expect(aggregate.driverAverages).toEqual([
      expect.objectContaining({ id: "be_perfect", avg: 80 }),
      expect.objectContaining({ id: "hurry_up", avg: 60 }),
      expect.objectContaining({ id: "try_hard", avg: 20 }),
    ]);
    expect(aggregate.driverRankSummary).toMatchObject({
      total_people: 1,
      first_rank: [{ id: "be_perfect", label: "Fii perfect", value: 1 }],
      second_rank: [{ id: "hurry_up", label: "Grăbește-te", value: 1 }],
      insufficient_driver_score_count: 1,
    });
  });
});
