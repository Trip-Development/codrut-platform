import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  audienceAccessNote,
  changePassword,
  getCurrentParticipant,
  getCurrentTrainer,
  getParticipantSession,
  getTrainerSession,
} from "./auth";
import {
  buildVideoCampaignCreatePayload,
  createEmailTemplateOnServer,
  deleteCampaignOnServer,
  deleteCampaignRecipientOnServer,
  deleteEmailTemplateOnServer,
  getEmailOpsSummary,
  htmlToPlainText,
  listEmailSurfaceStubs,
  listEmailTemplatesOnServer,
  sendCampaignOnServer,
  updateCampaignRecipientOnServer,
  updateEmailTemplateOnServer,
  uploadCampaignAssetOnServer,
} from "./email";
import { inviteQuestionnaireLabel, inviteTaskHref, participantTaskTypeLabel, resolveInviteBundle } from "./invites";
import { getParticipantWorkspaceSummary } from "./participants";
import {
  addCompanyTeamMembership,
  createCompanyAssignment,
  createCompany,
  createCompanyTeam,
  deleteCompany,
  getAllCompanyProjects,
  getCompanyAssignments,
  getCompanyDefaultAssignmentPlan,
  getCompanyList,
  getCompanyParticipants,
  getCompanyProjectById,
  getCompanyProjects,
  getCompanyReportAggregate,
  getCompanyTeamMemberships,
  getProjectParticipants,
  importCompanyRoster,
  resendParticipantInvitation,
  saveCompanyDefaultAssignmentPlan,
  sendParticipantInvitations,
} from "./companies";
import {
  clearQuestionnaireDefinitionCache,
  getQuestionnaireDefinition,
  getQuestionnaireResponse,
  groupQuestionnaireStubsByKey,
  listQuestionnaireDefinitionStubs,
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
    await expect(getCurrentTrainer()).resolves.toMatchObject({ role: "trainer" });
    await expect(getCurrentParticipant()).resolves.toMatchObject({ role: "participant" });
    await expect(getTrainerSession()).resolves.toMatchObject({ state: "fallback" });
    await expect(getParticipantSession()).resolves.toMatchObject({ state: "fallback" });
    expect(audienceAccessNote("invitee")).toContain("linkul securizat");
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
      "/participant/tasks/a1?access=secure&returnTo=%2Finvite%2Fabc&target=Leadership",
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

  it("enables demo fallback on localhost unless explicitly disabled", () => {
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

  it("fails closed for seeded demo data in production-like server runtimes", async () => {
    delete process.env.CODRUT_FRONTEND_DEMO_FALLBACK;
    delete process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK;

    const originalInternalApiBaseUrl = process.env.INTERNAL_API_BASE_URL;
    const originalVitest = process.env.VITEST;

    delete process.env.VITEST;
    vi.stubGlobal("window", undefined);
    vi.stubEnv("NODE_ENV", "development");
    process.env.INTERNAL_API_BASE_URL = "https://api.codrut.ro/api";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false } as Response));

    try {
      expect(isDemoFallbackEnabled()).toBe(true);
      expect(isSeededDemoFallbackEnabled()).toBe(false);
      await expect(getTrainerSession()).rejects.toThrow("Trainer authentication required");
      await expect(getParticipantSession()).rejects.toThrow("Participant authentication required");
      await expect(getQuestionnaireDefinition("boss_360")).resolves.toBeNull();
      await expect(listQuestionnaireDefinitionStubs()).resolves.toEqual([]);

      const workspace = await getParticipantWorkspaceSummary();
      expect(workspace).toMatchObject({
        participantFullName: "Participant",
        projectName: "Spațiul tău de lucru",
        tasks: [],
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
        body: JSON.stringify({
          dry_run: false,
          recipient_ids: ["recipient-1"],
          mode: "selected",
        }),
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
            scores: { be_strong: 72 },
            primary_result: "be_strong",
          },
        ],
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
      results: [expect.objectContaining({ assignmentId: "result-assignment-1" })],
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
      projectName: "Spațiul tău de lucru",
      tasks: [],
      emptyState: {
        title: "Spațiul de participant nu este încă disponibil",
        description: "Participant profile not found for this account.",
      },
    });
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
      estimatedItems: 48,
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
      landingUrl: "https://codrut.andreivacaru.ro/watch/intro?source=email&name=\"hero\"",
    });

    expect(payload).toMatchObject({
      name: "Campanie video",
      segment: "potential_customer",
      subject: "O idee pentru ${first_name}",
      video_url: "https://video.codrut.ro/watch/intro",
      thumbnail_url: "https://cdn.codrut.ro/thumb.jpg?size=large&variant=%22hero%22",
      landing_page_url: "https://codrut.andreivacaru.ro/watch/intro?source=email&name=%22hero%22",
    });
    expect(payload?.html_body).toContain('href="https://codrut.andreivacaru.ro/watch/intro?source=email&amp;name=%22hero%22"');
    expect(payload?.html_body).toContain('<img src="https://cdn.codrut.ro/thumb.jpg?size=large&amp;variant=%22hero%22"');
    expect(payload?.text_body).toContain("https://codrut.andreivacaru.ro/watch/intro?source=email&name=%22hero%22");
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
    expect(payload?.html_body).toContain('href="https://vimeo.com/123456789"');
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

  it("uploads campaign thumbnail assets as raw image bodies", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    const file = new File([new Uint8Array([137, 80, 78, 71])], "mini thumb.png", {
      type: "image/png",
    });
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        url: "https://codrut.andreivacaru.ro/api/campaign-assets/mini.png",
        file_name: "mini.png",
        content_type: "image/png",
        size_bytes: 4,
      }),
    });
    vi.stubGlobal("fetch", fetchMock);

    await expect(uploadCampaignAssetOnServer(file)).resolves.toMatchObject({
      url: "https://codrut.andreivacaru.ro/api/campaign-assets/mini.png",
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

  it("rejects incomplete or non-http video campaign URLs", () => {
    expect(buildVideoCampaignCreatePayload({
      name: "Campanie video",
      segment: "past_customer",
      subject: "Salut",
      videoUrl: "ftp://video.codrut.ro/watch/intro",
      thumbnailUrl: "https://cdn.codrut.ro/thumb.jpg",
      landingUrl: "https://codrut.andreivacaru.ro/watch/intro",
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
    })?.landing_page_url).toBeUndefined();
  });

  it("resolves invite bundle fallback states", async () => {
    await expect(resolveInviteBundle("demo-token")).resolves.toMatchObject({
      state: "valid",
      projectName: "Leadership operațional Q3",
      participantEmail: "mihai.matei@atlas-mobility.ro",
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
            href: "/participant/questionnaires/lencioni?assignmentId=assignment-1&access=secure",
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
      "/participant/tasks/assignment-1?access=secure&target=Leadership",
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

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/forms/assignments/assignment-1/response"),
      expect.objectContaining({
        cache: "no-store",
        credentials: "include",
        headers: { Cookie: "codrut_session=session-token" },
      }),
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

  it("resolves the seeded boss 360 questionnaire as a runnable fallback", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    const definition = await getQuestionnaireDefinition("boss_360");

    expect(definition).toMatchObject({
      key: "boss_360",
      title: "Feedback 360 iCARE pentru manager",
    });
    expect(definition?.schema.sections[0]?.questions).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: "icare_inspiring_developing_people" }),
      ]),
    );
  });

  it("does not fall back to demo sessions when fallback is disabled", async () => {
    process.env.CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    process.env.NEXT_PUBLIC_CODRUT_FRONTEND_DEMO_FALLBACK = "false";
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));

    await expect(getTrainerSession()).rejects.toThrow("Trainer authentication required");
    await expect(getParticipantSession()).rejects.toThrow("Participant authentication required");
  });

  it("changes password through the authenticated backend endpoint", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal("fetch", fetchMock);

    await expect(changePassword("old-password-123", "new-password-123")).resolves.toBeUndefined();

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/auth/change-password"),
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify({
          current_password: "old-password-123",
          new_password: "new-password-123",
        }),
      }),
    );
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
      driver_count: 3,
      boss_360_count: 2,
      results: expect.arrayContaining([
        expect.objectContaining({ assignment_id: "atlas-lencioni-radu" }),
        expect.objectContaining({ assignment_id: "atlas-driver-claudia" }),
      ]),
    });

    await expect(getCompanyProjects("leadership-pilot")).resolves.toEqual([
      expect.objectContaining({ id: "leadership-pilot", company_id: "leadership-pilot" }),
    ]);
    await expect(getCompanyParticipants("leadership-pilot")).resolves.toEqual([
      expect.objectContaining({ id: "andrei-vacaru", role_group: "manager", user_id: "user-andrei-vacaru" }),
      expect.objectContaining({ id: "ilinca-corbu", reports_to_name: "Andrei Vacaru", role_group: "manager" }),
      expect.objectContaining({ id: "vlad-soimu", reports_to_name: "Andrei Vacaru", role_group: "manager" }),
      expect.objectContaining({ id: "alexandra-giurca", reports_to_name: "Ilinca Corbu", role_group: "member" }),
      expect.objectContaining({ id: "member-vlad", reports_to_name: "Ilinca Corbu", role_group: "member" }),
      expect.objectContaining({ id: "member-ilinca", reports_to_name: "Vlad Soimu", role_group: "member" }),
    ]);
    await expect(getProjectParticipants("leadership-pilot", "leadership-pilot")).resolves.toHaveLength(6);

    const leadershipAssignments = await getCompanyAssignments("leadership-pilot", {}, { projectId: "leadership-pilot" });
    expect(leadershipAssignments).toHaveLength(23);
    expect(leadershipAssignments).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          id: "leadership-lencioni-andrei",
          target_type: "team",
          target_team_id: "leadership",
        }),
        expect.objectContaining({
          id: "icare-ilinca-on-andrei",
          questionnaire_key: "boss_360",
          target_person_id: "andrei-vacaru",
        }),
        expect.objectContaining({
          id: "icare-member-ilinca-on-vlad",
          questionnaire_key: "boss_360",
          target_person_id: "vlad-soimu",
        }),
      ]),
    );

    await expect(getCompanyReportAggregate("leadership-pilot", {}, { projectId: "leadership-pilot" })).resolves.toMatchObject({
      total_assigned: 23,
      total_completed: 23,
      lencioni_count: 6,
      driver_count: 3,
      boss_360_count: 11,
      results: expect.arrayContaining([
        expect.objectContaining({ assignment_id: "leadership-lencioni-andrei" }),
        expect.objectContaining({ assignment_id: "icare-ilinca-on-andrei" }),
      ]),
    });
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
        detail: [
          {
            loc: ["body", "rows", 0, "email"],
            msg: "value is not a valid email address: The part after the @-sign is a special-use or reserved name",
            type: "value_error",
          },
        ],
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
    const definition = {
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

  it("falls back to the editable campaign and evaluation catalog, not transactional placeholders", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));

    const templates = await listEmailTemplatesOnServer();
    const keys = templates.map((template) => template.baseKey);
    const report = templates.find((template) => template.baseKey === "promo_past_report_2022_2025");
    const leadershipInvite = templates.find((template) => template.baseKey === "evaluation_leadership_invite");

    expect(keys).toContain("promo_past_report_2022_2025");
    expect(keys).toContain("promo_potential_intro");
    expect(keys).toContain("evaluation_leadership_invite");
    expect(keys).not.toContain("account_setup");
    expect(keys).not.toContain("assignment_bundle");
    expect(report).toMatchObject({
      version: 9,
      lane: "campaign",
      audience: "campaign:past_customer",
    });
    expect(report?.body).toContain('data-codrut-cta="calendly"');
    expect(report?.body).toContain("A supraviețuit tranziției la freelancing");
    expect(report?.body).toContain("A livrat peste 1200 de sesiuni fără să adoarmă nimeni în sală");
    expect(report?.body).toContain("A neglijat să se reconecteze cu oameni cu care a lucrat bine");
    expect(report?.body).toContain("Aici ai calendarul meu");
    expect(report?.body).not.toContain("Link calendar");
    expect(report?.textBody).toContain("✓ A supraviețuit tranziției la freelancing");
    expect(report?.textBody).toContain("✗ A neglijat să se reconecteze");
    expect(report?.textBody).toContain("Alege un slot în Calendly: {calendly_url}");
    expect(report?.placeholders).toContain("{calendly_url}");
    expect(report?.placeholders).toContain("{thumbnail_url}");
    expect(leadershipInvite).toMatchObject({ version: 7, audience: "transactional:leadership" });
    expect(leadershipInvite?.body).toContain("Link platformă");
    expect(leadershipInvite?.textBody).toContain("Link platformă: {action_url}");
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
        '<table><tr><td style="color:#890505;">✓</td><td>A supraviețuit tranziției la freelancing.</td></tr><tr><td>✗</td><td>A neglijat reconectarea.</td></tr></table><p><a href="{calendly_url}" data-codrut-cta="calendly">Alege un slot</a></p>',
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
        '<table><tr><td style="color:#890505;">✓</td><td>A supraviețuit tranziției la freelancing.</td></tr><tr><td>✗</td><td>A neglijat reconectarea.</td></tr></table><p><a href="{calendly_url}" data-codrut-cta="calendly">Alege un slot</a></p>',
    });

    const payload = JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body));
    expect(payload.text_body).toContain("✓ A supraviețuit tranziției la freelancing.");
    expect(payload.text_body).toContain("✗ A neglijat reconectarea.");
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
});
