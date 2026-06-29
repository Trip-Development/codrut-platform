import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { Suspense, act } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { InviteBundle } from "@/api/invites";
import { resolveInviteBundle } from "@/api/invites";
import InvitePage from "./page";

vi.mock("@/api/invites", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/invites")>();
  return {
    ...original,
    resolveInviteBundle: vi.fn(),
  };
});

const validBundle: Extract<InviteBundle, { state: "valid" }> = {
  state: "valid",
  token: "demo-token",
  projectName: "Leadership operațional Q3",
  participantEmail: "mihai.matei@atlas-mobility.ro",
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

describe("InvitePage", () => {
  beforeEach(() => {
    (globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
    window.localStorage.clear();
    window.sessionStorage.clear();
    vi.mocked(resolveInviteBundle).mockResolvedValue(validBundle);
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("uses stored consent only as a checkbox hint, not as screen authority", async () => {
    window.localStorage.setItem("codrut_invite_consent:privacy-2026-06-12:demo-token", "accepted");

    await act(async () => {
      render(
        <Suspense fallback={null}>
          <InvitePage params={Promise.resolve({ token: "demo-token" })} />
        </Suspense>,
      );
    });

    await screen.findByText("Confirmă confidențialitatea înainte de chestionare");
    expect(screen.queryByText("Sarcinile tale pentru acest proiect")).toBeNull();
    expect(screen.getByRole("checkbox")).toHaveProperty("checked", true);
    await waitFor(() => {
      expect(resolveInviteBundle).toHaveBeenCalledWith("demo-token");
    });
  });

  it("skips confidentiality only when server consent is already current", async () => {
    vi.mocked(resolveInviteBundle).mockResolvedValue({
      ...validBundle,
      termsAcceptedAt: "2026-06-27T10:00:00Z",
      termsVersion: "privacy-2026-06-12",
    });

    await act(async () => {
      render(
        <Suspense fallback={null}>
          <InvitePage params={Promise.resolve({ token: "demo-token" })} />
        </Suspense>,
      );
    });

    await screen.findByText("Sarcinile tale pentru acest proiect");
    expect(screen.queryByText("Confirmă confidențialitatea înainte de chestionare")).toBeNull();
  });
});
