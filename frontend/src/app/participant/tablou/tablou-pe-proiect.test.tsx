/**
 * Tabloul se cere pe proiectul ALES de om — plicul 143.
 *
 * Până la 143 pagina chema tabloul fără proiect, iar serverul nu avea de unde să știe competențele
 * alese de trainer: arăta lista fixă din aplicația veche.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ getParticipantWorkspaceSummary: vi.fn() }));

vi.mock("@/api/participants", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/participants")>();
  return { ...original, getParticipantWorkspaceSummary: api.getParticipantWorkspaceSummary };
});
vi.mock("@/api/auth-server", () => ({
  getParticipantSession: vi.fn(async () => ({
    state: "authenticated",
    user: { id: "user-1", name: "Andrei", role: "participant" },
  })),
}));
vi.mock("@/api/server-request", () => ({
  getServerApiRequestOptions: vi.fn(async () => ({ headers: { cookie: "session=test" } })),
}));
vi.mock("../dashboard/PracticeParticipantDashboard", () => ({
  PracticeParticipantDashboard: ({ projectId }: { projectId?: string | null }) => (
    <p>tabloul pe proiectul: {projectId ?? "niciunul"}</p>
  ),
}));

import TablouParticipantPage from "./page";

const sumar = {
  participantProfileId: "profile-1",
  participantFullName: "Andrei Participant",
  projectId: "proiect-ales",
  contexts: [],
  cycles: [],
  tasks: [],
  results: [],
  projects: [],
  questionnaireProjects: [],
  receivedFeedback: null,
  receivedFeedbackGroups: [],
  pcmBase: null,
  pcmPhase: null,
};

describe("tabloul, pe proiectul ales", () => {
  afterEach(cleanup);

  it("dă tabloului proiectul ales de om", async () => {
    api.getParticipantWorkspaceSummary.mockResolvedValue(sumar);
    render(await TablouParticipantPage({ searchParams: Promise.resolve({ project: "proiect-ales" }) }));
    expect(screen.getByText("tabloul pe proiectul: proiect-ales")).toBeTruthy();
  });

  it("dacă rezumatul nu se poate citi, tabloul se deschide tot, fără proiect", async () => {
    api.getParticipantWorkspaceSummary.mockRejectedValue(new Error("pică"));
    render(await TablouParticipantPage({ searchParams: Promise.resolve({}) }));
    expect(screen.getByText("tabloul pe proiectul: niciunul")).toBeTruthy();
  });
});
