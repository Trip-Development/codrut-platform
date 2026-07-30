import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getParticipantWorkspaceSummary: vi.fn(),
}));

vi.mock("@/api/participants", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/participants")>();
  return { ...original, ...api };
});
vi.mock("@/api/auth-server", () => ({
  getParticipantSession: vi.fn(async () => ({
    state: "authenticated",
    user: { id: "user-1", name: "Ana", role: "participant" },
  })),
}));
vi.mock("@/api/participant-onboarding", () => ({
  getParticipantOnboardingState: vi.fn(async () => ({ required: false })),
}));
vi.mock("@/api/server-request", () => ({
  getServerApiRequestOptions: vi.fn(async () => ({ headers: { cookie: "session=test" } })),
}));
vi.mock("@/components/shell/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <main>{children}</main>,
}));
vi.mock("../ParticipantContextSelector", () => ({
  ParticipantContextSelector: () => <div>Selectare proiect</div>,
}));
vi.mock("../ParticipantClientWorkspace", () => ({
  ParticipantResultsPanel: ({ results }: { results: Array<{ title: string }> }) => (
    <div>{results.map((result) => <p key={result.title}>{result.title}</p>)}</div>
  ),
}));

import ParticipantResultsPage from "./page";

const baseSummary = {
  participantProfileId: "profile-1",
  participantFullName: "Ana Participant",
  projectId: "project-1",
  projectName: "Proiect Atlas",
  assessmentCycleId: "cycle-2",
  contexts: [],
  cycles: [
    { id: "cycle-1", projectId: "project-1", sequence: 1, name: "Evaluare inițială", status: "closed" },
    { id: "cycle-2", projectId: "project-1", sequence: 2, name: "Reevaluare", status: "active" },
  ],
  tasks: [],
  results: [],
  receivedFeedback: null,
  receivedFeedbackGroups: [],
  pcmBase: null,
  pcmPhase: null,
};

describe("participant result history", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getParticipantWorkspaceSummary
      .mockResolvedValueOnce(baseSummary)
      .mockResolvedValueOnce({
        ...baseSummary,
        assessmentCycleId: "cycle-1",
        results: [{ title: "Lencioni inițial" }],
      })
      .mockResolvedValueOnce({
        ...baseSummary,
        assessmentCycleId: "cycle-2",
        results: [{ title: "Lencioni reevaluare" }],
      });
  });

  it("loads and labels every cycle instead of hiding history behind a selector", async () => {
    const ui = await ParticipantResultsPage({
      searchParams: Promise.resolve({ profile: "profile-1", project: "project-1" }),
    });
    render(ui);

    expect(screen.getByRole("heading", { name: "Istoricul rezultatelor" })).toBeTruthy();
    expect(screen.getAllByText(/Ciclul 1/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Ciclul 2/).length).toBeGreaterThan(0);
    expect(screen.getByText("Lencioni inițial")).toBeTruthy();
    expect(screen.getByText("Lencioni reevaluare")).toBeTruthy();
    expect(api.getParticipantWorkspaceSummary).toHaveBeenCalledWith(
      expect.objectContaining({ cycleId: "cycle-1", projectId: "project-1" }),
    );
    expect(api.getParticipantWorkspaceSummary).toHaveBeenCalledWith(
      expect.objectContaining({ cycleId: "cycle-2", projectId: "project-1" }),
    );
  });
});
