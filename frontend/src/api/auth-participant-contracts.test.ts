import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  acceptCurrentTerms,
  confirmPasswordReset,
  dashboardHrefForRole,
  getAuthenticatedSession,
  getParticipantSession,
  loginWithPassword,
  requestPasswordReset,
} from "./auth";
import {
  exchangeInviteSession,
  inviteStatusLabel,
  inviteTaskHref,
  inviteTaskProgress,
  participantTaskTypeLabel,
  resolveInviteBundle,
  type InviteTask,
} from "./invites";
import { getParticipantWorkspaceSummary } from "./participants";

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

function task(overrides: Partial<InviteTask> = {}): InviteTask {
  return {
    id: "task-1",
    title: "Sarcină sintetică",
    status: "not_started",
    detail: "Conținut sintetic pentru testarea navigării.",
    href: "/participant/questionnaires/synthetic_pulse?assignmentId=assignment-1",
    assignmentId: "assignment-1",
    targetLabel: "Echipă sintetică",
    estimatedMinutes: 12,
    questionnaireKey: "synthetic_pulse",
    ...overrides,
  };
}

describe("auth adapter contracts", () => {
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

  it("maps a successful password login and preserves the terms state", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({
      ok: true,
      payload: {
        user_id: "trainer-1",
        email: "andrei@example.com",
        role: "trainer",
        terms_accepted_at: "2026-07-17T08:00:00Z",
        terms_version: "2026-07-01",
      },
    }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(loginWithPassword("andrei@example.com", "correct horse battery staple")).resolves.toEqual({
      state: "authenticated",
      user: {
        id: "trainer-1",
        name: "andrei",
        email: "andrei@example.com",
        role: "trainer",
        termsAcceptedAt: "2026-07-17T08:00:00Z",
        termsVersion: "2026-07-01",
      },
    });
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      email: "andrei@example.com",
      password: "correct horse battery staple",
    });
  });

  it.each([
    [response({ ok: false, status: 401, payload: { error: { message: "Date de acces invalide." } } }), "Date de acces invalide."],
    [response({ ok: false, status: 500, jsonError: new Error("invalid json") }), "Autentificarea a eșuat. Verifică emailul și parola."],
  ])("surfaces useful login failures", async (backendResponse, message) => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(backendResponse));
    await expect(loginWithPassword("andrei@example.com", "wrong password")).rejects.toThrow(message);
  });

  it("routes authenticated roles to their own workspace", () => {
    expect(dashboardHrefForRole("trainer")).toBe("/trainer");
    expect(dashboardHrefForRole("participant")).toBe("/participant");
  });

  it("returns null when the current-session payload is incomplete or unreachable", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: true, payload: { user_id: "user-1", role: "trainer" } }))
      .mockRejectedValueOnce(new TypeError("network unavailable"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getAuthenticatedSession()).resolves.toBeNull();
    await expect(getAuthenticatedSession()).resolves.toBeNull();
  });

  it("posts password-reset requests and reports the backend recovery message", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: true, payload: {} }))
      .mockResolvedValueOnce(response({ ok: false, status: 429, payload: { error: { message: "Încearcă din nou mai târziu." } } }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(requestPasswordReset("participant@example.com")).resolves.toBeUndefined();
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({ email: "participant@example.com" });
    await expect(requestPasswordReset("participant@example.com")).rejects.toThrow("Încearcă din nou mai târziu.");
  });

  it("validates reset passphrases before persistence and maps server rejection", async () => {
    const fetchMock = vi.fn().mockResolvedValue(response({
      ok: false,
      status: 410,
      payload: { error: { message: "Linkul de resetare a expirat." } },
    }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(confirmPasswordReset("token", "short")).rejects.toThrow();
    expect(fetchMock).not.toHaveBeenCalled();

    await expect(confirmPasswordReset("token", "a long private passphrase 2026")).rejects.toThrow(
      "Linkul de resetare a expirat.",
    );
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({
      token: "token",
      password: "a long private passphrase 2026",
    });
  });

  it("persists the current legal version and exposes consent failures", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: true, payload: {} }))
      .mockResolvedValueOnce(response({ ok: false, status: 403, jsonError: new Error("invalid json") }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(acceptCurrentTerms()).resolves.toBeUndefined();
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual(expect.objectContaining({
      terms_accepted: true,
      terms_version: expect.any(String),
    }));
    await expect(acceptCurrentTerms()).rejects.toThrow("Acordul nu a putut fi salvat.");
  });

  it("classifies malformed and unreachable participant sessions without fabricating login", async () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: true, payload: { user_id: "participant-1", role: "participant" } }))
      .mockRejectedValueOnce(new TypeError("offline"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getParticipantSession()).rejects.toMatchObject({
      name: "AuthSessionUnavailableError",
      context: { expectedRole: "participant", reason: "payload" },
    });
    await expect(getParticipantSession()).rejects.toMatchObject({
      name: "AuthSessionUnavailableError",
      context: { expectedRole: "participant", reason: "network" },
    });
    expect(warn).toHaveBeenCalledTimes(2);
  });
});

describe("invite and participant adapter contracts", () => {
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

  it("maps revoked links as expired and preserves the backend recovery message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      ok: false,
      status: 410,
      payload: { error: { code: "task_link_revoked", message: "Trainerul a înlocuit acest link." } },
    })));

    await expect(resolveInviteBundle("revoked-token")).resolves.toEqual({
      state: "expired",
      token: "revoked-token",
      projectName: "Proiect",
      deadlineLabel: "deadline-ul proiectului",
      message: "Trainerul a înlocuit acest link. Folosește cea mai recentă invitație.",
    });
  });

  it("uses a safe deadline label for invalid invite dates", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      ok: true,
      payload: {
        email: "participant@example.com",
        full_name: "Ana Participant",
        is_leadership: false,
        already_registered: true,
        project_name: "Pilot",
        expires_at: "not-a-date",
        tasks: [],
      },
    })));

    await expect(resolveInviteBundle("valid-token")).resolves.toMatchObject({
      state: "valid",
      deadlineLabel: "deadline-ul proiectului",
      alreadyRegistered: true,
    });
  });

  it("exchanges real invite tokens and falls back to an actionable error message", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: true, payload: {} }))
      .mockResolvedValueOnce(response({ ok: false, status: 503, jsonError: new Error("invalid json") }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(exchangeInviteSession("real-token")).resolves.toBeUndefined();
    expect(JSON.parse(String(fetchMock.mock.calls[0]?.[1]?.body))).toEqual({ token: "real-token" });
    await expect(exchangeInviteSession("real-token")).rejects.toThrow(
      "Nu am putut pregăti sesiunea invitației.",
    );
  });

  it("calculates empty and partial progress without inventing a next task", () => {
    expect(inviteTaskProgress([])).toEqual({ completed: 0, total: 0, percent: 0, nextTask: undefined });
    expect(inviteTaskProgress([
      task({ id: "done", status: "completed" }),
      task({ id: "next", status: "in_progress" }),
    ])).toEqual(expect.objectContaining({ completed: 1, total: 2, percent: 50, nextTask: expect.objectContaining({ id: "next" }) }));
    expect(inviteStatusLabel("completed")).toBe("Completat");
    expect(inviteStatusLabel("in_progress")).toBe("În progres");
    expect(inviteStatusLabel("not_started")).toBe("Neînceput");
    expect(participantTaskTypeLabel("unknown_form")).toBe("Chestionar");
  });

  it("keeps existing task query state and supports secure links without an invite token", () => {
    expect(inviteTaskHref(task({
      href: "/participant/questionnaires/synthetic_pulse?assignmentId=assignment-1&returnTo=%2Fparticipant&target=Sample%20Team",
    }), { returnTo: "/participant" })).toBe(
      "/participant/questionnaires/synthetic_pulse?assignmentId=assignment-1&returnTo=%2Fparticipant&target=Sample%20Team",
    );

    expect(inviteTaskHref(task({
      targetLabel: "",
      href: "/participant/questionnaires/synthetic_pulse?assignmentId=assignment-1&access=secure",
    }))).toBe("/participant/tasks/assignment-1?access=secure");
  });

  it("maps result privacy boundaries when feedback is hidden or absent", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({
        ok: true,
        payload: {
          participant_profile_id: "profile-1",
          participant_full_name: "Ana Participant",
          participant_email: "ana@example.com",
          company_id: "company-1",
          company_name: "Companie",
          project_id: null,
          project_name: "Pilot",
          deadline_label: "Fără termen",
          tasks: [],
          received_feedback: {
            completed_count: 1,
            minimum_completed: 2,
            visible: false,
          },
          cards: [],
          empty_state: { title: "Fără rezultate", description: "Pragul de confidențialitate nu este atins." },
        },
      }))
      .mockResolvedValueOnce(response({
        ok: true,
        payload: {
          participant_profile_id: "profile-1",
          participant_full_name: "Ana Participant",
          participant_email: "ana@example.com",
          company_id: "company-1",
          company_name: "Companie",
          project_id: null,
          project_name: "Pilot",
          deadline_label: "Fără termen",
          tasks: [],
          cards: [],
          empty_state: { title: "Fără rezultate", description: "Nu există rezultate." },
        },
      }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getParticipantWorkspaceSummary()).resolves.toMatchObject({
      results: [],
      receivedFeedback: {
        completedCount: 1,
        minimumCompleted: 2,
        visible: false,
        dimensions: [],
      },
    });
    await expect(getParticipantWorkspaceSummary()).resolves.toMatchObject({ results: [], receivedFeedback: null });
  });

  it("throws typed retryable participant errors for backend and network failures", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(response({ ok: false, status: 500, jsonError: new Error("bad payload") }))
      .mockRejectedValueOnce(new TypeError("offline"));
    vi.stubGlobal("fetch", fetchMock);

    await expect(getParticipantWorkspaceSummary()).rejects.toMatchObject({
      name: "ParticipantWorkspaceError",
      status: 500,
      code: "http_500",
    });
    await expect(getParticipantWorkspaceSummary()).rejects.toMatchObject({
      name: "ParticipantWorkspaceError",
      status: 0,
      code: "network_error",
    });
  });

  it("reserves the unassociated profile state for the explicit profile-not-found code", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(response({
      ok: false,
      status: 404,
      payload: {
        error: {
          code: "participant_profile_not_found",
          message: "Participant profile not found.",
        },
      },
    })));

    await expect(getParticipantWorkspaceSummary()).resolves.toMatchObject({
      tasks: [],
      emptyState: {
        description: "Profilul nu este încă legat de acest cont. Verifică adresa de email cu trainerul.",
      },
    });
  });
});
