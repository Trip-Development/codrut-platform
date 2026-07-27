import { cleanup, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getParticipantSession } from "@/api/auth-server";
import { getParticipantOnboardingState } from "@/api/participant-onboarding";
import { getParticipantWorkspaceSummary } from "@/api/participants";
import ParticipantAccountPage from "./page";

vi.mock("@/api/auth-server", () => ({
  getParticipantSession: vi.fn(),
}));

vi.mock("@/api/participant-onboarding", () => ({
  getParticipantOnboardingState: vi.fn(),
}));

vi.mock("@/api/participants", () => ({
  getParticipantWorkspaceSummary: vi.fn(),
}));

vi.mock("@/api/server-request", () => ({
  getServerApiRequestOptions: vi.fn().mockResolvedValue({ headers: { cookie: "session=test" } }),
}));

vi.mock("@/components/shell/app-shell", () => ({
  AppShell: ({ children, title }: { children: ReactNode; title: string }) => (
    <main>
      <h1>{title}</h1>
      {children}
    </main>
  ),
}));

vi.mock("../ParticipantContextSelector", () => ({
  ParticipantContextSelector: () => <div>Context participant</div>,
}));

vi.mock("./AccountWorkspace", () => ({
  AccountWorkspace: () => <div>Setări cont participant</div>,
}));

describe("ParticipantAccountPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("keeps account settings accessible while questionnaire onboarding is still required", async () => {
    vi.mocked(getParticipantSession).mockResolvedValue({
      state: "authenticated",
      user: {
        id: "participant-user-1",
        name: "Andrei Vacaru",
        email: "participant@example.com",
        role: "participant",
      },
    });
    vi.mocked(getParticipantWorkspaceSummary).mockResolvedValue({
      participantProfileId: "participant-profile-1",
      participantFullName: "Andrei Vacaru",
      participantEmail: "participant@example.com",
      projectId: "project-1",
      projectName: "Leadership Mockup",
      deadlineLabel: "31 august",
      tasks: [],
      results: [],
      receivedFeedback: null,
      receivedFeedbackGroups: [],
      cards: [],
      contexts: [],
      cycles: [],
      projects: [],
      contextSelectionRequired: false,
      companyName: "Test de control",
      emptyState: { title: "", description: "" },
    });
    vi.mocked(getParticipantOnboardingState).mockResolvedValue({
      required: true,
      questionnaire_key: "pcm_base",
      assignment_id: "assignment-1",
      href: "/participant/questionnaires/pcm_base?assignmentId=assignment-1",
    });

    const ui = await ParticipantAccountPage({
      searchParams: Promise.resolve({
        profile: "participant-profile-1",
        project: "project-1",
      }),
    });

    render(ui);

    expect(screen.getByRole("heading", { name: "Contul tău" })).toBeDefined();
    expect(screen.getByText("Setări cont participant")).toBeDefined();
    expect(getParticipantOnboardingState).not.toHaveBeenCalled();
  });
});
