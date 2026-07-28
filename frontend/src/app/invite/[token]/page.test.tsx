import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { acceptCurrentTerms, getAuthenticatedSession } from "@/api/auth";
import {
  exchangeInviteSession,
  resolveInviteBundle,
  type InviteBundle,
} from "@/api/invites";
import InvitePage from "./page";

const routerReplace = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: routerReplace }),
}));

vi.mock("@/api/auth", () => ({
  acceptCurrentTerms: vi.fn(),
  getAuthenticatedSession: vi.fn(),
}));

vi.mock("@/api/invites", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/invites")>();
  return {
    ...original,
    exchangeInviteSession: vi.fn(),
    resolveInviteBundle: vi.fn(),
  };
});

const validBundle: Extract<InviteBundle, { state: "valid" }> = {
  state: "valid",
  token: "demo-token",
  projectName: "Leadership operațional Q3",
  participantEmail: "participant.demo@example.com",
  participantFullName: "Mihai Matei",
  anonymousName: "SignalHarbor5271",
  isLeadership: false,
  alreadyRegistered: false,
  deadlineLabel: "15 iulie 2026",
  tasks: [
    {
      id: "task-1",
      title: "Feedback pentru echipă",
      status: "not_started",
      detail: "Răspunde pentru echipa indicată în această sarcină.",
      href: "/participant/tasks/a1?access=secure&returnTo=%2Finvite%2Fdemo-token",
      assignmentId: "a1",
      targetLabel: "Leadership",
      estimatedMinutes: 12,
      questionnaireKey: "lencioni",
    },
  ],
};

async function renderInvitePage(token = "demo-token") {
  const ui = await InvitePage({ params: Promise.resolve({ token }) });
  let result!: ReturnType<typeof render>;
  await act(async () => {
    result = render(ui);
    await Promise.resolve();
  });
  return result;
}

describe("InvitePage", () => {
  beforeEach(() => {
    (globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    window.localStorage.clear();
    window.sessionStorage.clear();
    vi.mocked(acceptCurrentTerms).mockResolvedValue();
    vi.mocked(getAuthenticatedSession).mockResolvedValue({
      state: "authenticated",
      user: {
        id: "trainer-1",
        name: "trainer",
        email: "trainer@example.com",
        role: "trainer",
      },
    });
    vi.mocked(exchangeInviteSession).mockResolvedValue({
      action: "secure_link_ready",
      destination: "/invite/demo-token",
      participantProfileId: "participant-1",
    });
    vi.mocked(resolveInviteBundle).mockResolvedValue(validBundle);
    routerReplace.mockReset();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    vi.useRealTimers();
  });

  it("uses stored consent only as a checkbox hint, not as screen authority", async () => {
    window.localStorage.setItem("codrut_invite_consent:privacy-2026-07-16:demo-token", "accepted");

    await renderInvitePage();

    await screen.findByText("Confirmă confidențialitatea înainte de chestionare");
    expect(screen.queryByText("Chestionarele tale")).toBeNull();
    await waitFor(() => {
      expect(screen.getByRole("checkbox").getAttribute("aria-checked")).toBe("true");
    });
    await waitFor(() => {
      expect(resolveInviteBundle).toHaveBeenCalledWith("demo-token");
    });
  });

  it("skips confidentiality only when server consent is already current", async () => {
    vi.mocked(resolveInviteBundle).mockResolvedValue({
      ...validBundle,
      termsAcceptedAt: "2026-06-27T10:00:00Z",
      termsVersion: "privacy-2026-07-16",
    });

    await renderInvitePage();

    await screen.findByText("Chestionarele tale");
    expect(screen.queryByText("Confirmă confidențialitatea înainte de chestionare")).toBeNull();
    await waitFor(() => {
      expect(exchangeInviteSession).toHaveBeenCalledWith("demo-token");
    });
  });

  it("requires explicit account switching without replacing the active session", async () => {
    vi.mocked(resolveInviteBundle).mockResolvedValue({
      ...validBundle,
      termsAcceptedAt: "2026-06-27T10:00:00Z",
      termsVersion: "privacy-2026-07-16",
    });
    vi.mocked(exchangeInviteSession).mockResolvedValueOnce({
      action: "account_switch_required",
      destination: "/login?returnTo=%2Finvite%2Fdemo-token",
      participantProfileId: "participant-1",
    });

    await renderInvitePage();

    expect(await screen.findByText("Schimbă sesiunea activă?")).toBeTruthy();
    expect(screen.getByText(/trainer@example\.com/)).toBeTruthy();
    expect(screen.getByText(/participant\.demo@example\.com/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Intră cu contul invitat" })).toBeTruthy();
    expect(exchangeInviteSession).toHaveBeenCalledTimes(1);
    expect(exchangeInviteSession).toHaveBeenCalledWith("demo-token");
  });

  it("persists anonymous invite consent before showing secure tasks", async () => {
    await renderInvitePage();

    await screen.findByText("Confirmă confidențialitatea înainte de chestionare");
    vi.useFakeTimers();
    fireEvent.click(screen.getByRole("checkbox"));
    const consentButton = screen.getByRole("button", { name: "Continuă la chestionare" });
    fireEvent.click(consentButton);
    fireEvent.click(consentButton);

    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(screen.getByText("Pregătim accesul securizat")).toBeTruthy();
    expect(screen.getByRole("checkbox")).toHaveProperty("disabled", true);
    expect(vi.getTimerCount()).toBe(1);

    await act(async () => {
      vi.advanceTimersByTime(450);
    });
    vi.useRealTimers();

    await screen.findByText("Chestionarele tale");
    expect(exchangeInviteSession).toHaveBeenCalledTimes(1);
    expect(exchangeInviteSession).toHaveBeenCalledWith("demo-token");
    expect(acceptCurrentTerms).toHaveBeenCalledTimes(1);
    expect(window.localStorage.getItem("codrut_invite_consent:privacy-2026-07-16:demo-token")).toBe("accepted");
  });

  it("routes a matching permanent participant directly to the invited dashboard context", async () => {
    vi.mocked(resolveInviteBundle).mockResolvedValue({
      ...validBundle,
      alreadyRegistered: true,
      accountDashboardAvailable: true,
    });
    vi.mocked(exchangeInviteSession).mockResolvedValue({
      action: "dashboard_ready",
      destination: "/participant?profile=participant-1&project=project-1&cycle=cycle-1",
      participantProfileId: "participant-1",
      projectId: "project-1",
      assessmentCycleId: "cycle-1",
    });
    await renderInvitePage();

    await waitFor(() => {
      expect(routerReplace).toHaveBeenCalledWith(
        "/participant?profile=participant-1&project=project-1&cycle=cycle-1",
      );
    });
    expect(screen.queryByRole("checkbox")).toBeNull();
    expect(acceptCurrentTerms).not.toHaveBeenCalled();
    expect(exchangeInviteSession).toHaveBeenCalledWith("demo-token");
  });

  it("keeps the consent screen and exposes retry when persistence fails", async () => {
    vi.mocked(acceptCurrentTerms).mockRejectedValueOnce(new Error("Conexiunea a fost întreruptă."));

    await renderInvitePage();
    await screen.findByText("Confirmă confidențialitatea înainte de chestionare");
    fireEvent.click(screen.getByRole("checkbox"));
    fireEvent.click(screen.getByRole("button", { name: "Continuă la chestionare" }));

    expect(await screen.findByText("Acordul nu a fost salvat")).toBeTruthy();
    expect(screen.getByText("Conexiunea a fost întreruptă.")).toBeTruthy();
    expect(screen.getByRole("checkbox").getAttribute("aria-checked")).toBe("true");
    expect(screen.queryByText("Chestionarele tale")).toBeNull();
    expect(window.localStorage.getItem("codrut_invite_consent:privacy-2026-07-16:demo-token")).toBeNull();
  });

  it("lets an invite-only leadership participant stay guest and optionally register", async () => {
    vi.mocked(resolveInviteBundle).mockResolvedValue({
      ...validBundle,
      isLeadership: true,
      termsAcceptedAt: "2026-07-16T10:00:00Z",
      termsVersion: "privacy-2026-07-16",
    });

    await renderInvitePage();

    await screen.findByRole("heading", { name: "Chestionarele tale" });
    await waitFor(() => {
      expect(window.sessionStorage.getItem("codrut_invite")).toContain("participant.demo@example.com");
    });
    expect(screen.getByRole("link", { name: /Creează cont permanent/ }).getAttribute("href")).toBe("/register");
    expect(exchangeInviteSession).toHaveBeenCalledWith("demo-token");
  });

  it("does not expose an account-like review target in the secure task list or link", async () => {
    vi.mocked(resolveInviteBundle).mockResolvedValue({
      ...validBundle,
      termsAcceptedAt: "2026-07-16T10:00:00Z",
      termsVersion: "privacy-2026-07-16",
      tasks: [
        {
          ...validBundle.tasks[0],
          id: "review-1",
          assignmentId: "review-1",
          questionnaireKey: "boss_360",
          targetLabel: "bianca.pavel@example.com",
        },
      ],
    });

    await renderInvitePage();

    expect(await screen.findByText("1 persoană de evaluat · 12 min")).toBeDefined();
    expect(screen.queryByText(/bianca\.pavel@example\.com/i)).toBeNull();
    expect(screen.getByRole("link", { name: /Deschide/i }).getAttribute("href")).not.toContain("bianca.pavel");
  });

  it("uses recovery copy instead of exposing unexpected invite lookup failures", async () => {
    vi.mocked(resolveInviteBundle).mockRejectedValueOnce(new Error("Invitația a expirat."));
    await renderInvitePage("expired-token");
    expect(await screen.findByRole("heading", { name: "Invitație nevalidă" })).toBeTruthy();
    expect(
      screen.getByText("Nu am putut verifica invitația. Reîncearcă sau cere un link nou de la trainer."),
    ).toBeTruthy();

    cleanup();
    vi.mocked(resolveInviteBundle).mockRejectedValueOnce({ reason: "unknown" });
    await renderInvitePage("unknown-token");
    expect(
      await screen.findByText("Nu am putut verifica invitația. Reîncearcă sau cere un link nou de la trainer."),
    ).toBeTruthy();
  });

  it("shows a recovery action for an invalid invite with empty backend copy", async () => {
    vi.mocked(resolveInviteBundle).mockResolvedValue({
      state: "expired",
      token: "expired",
      projectName: "Program pilot",
      deadlineLabel: "Termen indisponibil",
      message: "",
    });
    await renderInvitePage("expired");

    expect(await screen.findByText("Nu am putut valida această invitație. Cere un link nou de la trainer.")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Mergi la Cody/ }).getAttribute("href")).toBe("/");
  });

  it("requires login before a logged-out registered account can claim the invite", async () => {
    vi.mocked(resolveInviteBundle).mockResolvedValue({
      ...validBundle,
      isLeadership: true,
      alreadyRegistered: true,
      accountDashboardAvailable: true,
      termsAcceptedAt: "2026-07-16T10:00:00Z",
      termsVersion: "privacy-2026-07-16",
    });
    vi.mocked(exchangeInviteSession).mockResolvedValue({
      action: "login_required",
      destination: "/login?returnTo=%2Finvite%2Fdemo-token&email=participant.demo%40example.com",
      participantProfileId: "participant-1",
      projectId: "project-1",
      assessmentCycleId: "cycle-1",
    });
    await renderInvitePage();

    await waitFor(() => {
      expect(exchangeInviteSession).toHaveBeenCalledWith("demo-token");
      expect(routerReplace).toHaveBeenCalledWith(
        "/login?returnTo=%2Finvite%2Fdemo-token&email=participant.demo%40example.com",
      );
    });
    expect(screen.queryByRole("checkbox")).toBeNull();
  });

  it("adds participant access to a matching trainer account instead of using a guest flow", async () => {
    vi.mocked(resolveInviteBundle).mockResolvedValue({
      ...validBundle,
      alreadyRegistered: true,
      accountDashboardAvailable: false,
      termsAcceptedAt: "2026-07-16T10:00:00Z",
      termsVersion: "privacy-2026-07-16",
    });
    vi.mocked(exchangeInviteSession).mockResolvedValue({
      action: "dashboard_ready",
      destination: "/participant?profile=participant-1&project=project-1",
      participantProfileId: "participant-1",
      projectId: "project-1",
    });
    await renderInvitePage();

    await waitFor(() => {
      expect(routerReplace).toHaveBeenCalledWith("/participant?profile=participant-1&project=project-1");
    });
    expect(screen.queryByRole("heading", { name: "Chestionarele tale" })).toBeNull();
  });

  it("renders the empty secure queue after current server consent", async () => {
    vi.mocked(resolveInviteBundle).mockResolvedValue({
      ...validBundle,
      tasks: [],
      anonymousName: null,
      termsAcceptedAt: "2026-07-16T10:00:00Z",
      termsVersion: "privacy-2026-07-16",
    });
    await renderInvitePage();

    expect(await screen.findByText("Nu ai chestionare disponibile")).toBeTruthy();
    expect(screen.getByText(/participant anonim/i)).toBeTruthy();
    expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("0");
  });

  it("renders completed, active, named, and redacted review targets", async () => {
    vi.mocked(resolveInviteBundle).mockResolvedValue({
      ...validBundle,
      termsAcceptedAt: "2026-07-16T10:00:00Z",
      termsVersion: "privacy-2026-07-16",
      tasks: [
        { ...validBundle.tasks[0], id: "done", assignmentId: "done", title: "Finalizat echipă", status: "completed", targetLabel: "Echipa Nord" },
        { ...validBundle.tasks[0], id: "regular", assignmentId: "regular", title: "Evaluare regulată", targetLabel: "" },
        { ...validBundle.tasks[0], id: "named", assignmentId: "named", title: "Evaluare numită", questionnaireKey: "icare", targetLabel: "Bianca Pavel" },
        { ...validBundle.tasks[0], id: "uuid", assignmentId: "uuid", title: "Evaluare anonimizată", questionnaireKey: "boss_360_en", targetLabel: "94620fe8-bd46-4f37-a813-5f80d9ac54b1" },
      ],
    });
    await renderInvitePage();

    expect(await screen.findByText("Finalizat")).toBeTruthy();
    expect(screen.getAllByText(/Echipa ta · 12 min/)).toHaveLength(2);
    expect(screen.queryByText(/Echipa Nord/)).toBeNull();
    expect(screen.getByRole("heading", { name: "Evaluare regulată" }).closest("article")?.textContent).toContain("12 min");
    expect(screen.getByRole("heading", { name: "Review 360" })).toBeTruthy();
    expect(screen.getByText(/2 persoane de evaluat · 24 min/)).toBeTruthy();
    expect(screen.getByText("0/2 review-uri finalizate")).toBeTruthy();
    expect(screen.queryByText(/Bianca Pavel/)).toBeNull();
    expect(screen.queryByText(/94620fe8/)).toBeNull();
    expect(screen.getAllByRole("link", { name: /Deschide/i })).toHaveLength(2);
  });

  it("groups several 360 assignments into one review queue", async () => {
    vi.mocked(resolveInviteBundle).mockResolvedValue({
      ...validBundle,
      termsAcceptedAt: "2026-07-16T10:00:00Z",
      termsVersion: "privacy-2026-07-16",
      tasks: ["Ana", "Bogdan", "Corina"].map((targetLabel, index) => ({
        ...validBundle.tasks[0],
        id: `review-${index}`,
        assignmentId: `review-${index}`,
        questionnaireKey: "boss_360",
        targetLabel,
      })),
    });

    await renderInvitePage();

    expect(await screen.findAllByRole("heading", { name: "Review 360" })).toHaveLength(1);
    expect(screen.getByText("3 persoane de evaluat · 36 min")).toBeTruthy();
    expect(screen.getByText("0/3 review-uri finalizate")).toBeTruthy();
    expect(screen.getAllByRole("link", { name: /Deschide/i })).toHaveLength(1);
  });
});
