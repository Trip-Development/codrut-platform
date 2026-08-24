import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { SessionState } from "@/api/auth";
import type { ParticipantWorkspaceSummary } from "@/api/participants";
import { ParticipantClientWorkspace } from "@/app/participant/ParticipantClientWorkspace";
import { ParticipantPreviewView } from "./ParticipantPreviewView";

const mockSummaryData: ParticipantWorkspaceSummary = {
  companyName: "Acme Corp",
  projectName: "Proiect Leadership 2026",
  projectId: "proj-123",
  participantProfileId: "prof-456",
  participantFullName: "Ion Popescu",
  anonymousName: "SignalHarbor123",
  participantEmail: "ion.popescu@example.com",
  deadlineLabel: "15 septembrie 2026",
  contextSelectionRequired: false,
  contexts: [],
  cycles: [],
  projects: [],
  questionnaireProjects: [],
  cards: [],
  emptyState: {
    title: "Nu ai chestionare disponibile",
    description: "Deschide linkul unei invitații noi.",
  },
  receivedFeedbackGroups: [],
  tasks: [
    {
      id: "task-1",
      title: "PCM Profil Personal",
      status: "not_started",
      detail: "Chestionar PCM de completat",
      href: "/participant/questionnaires/pcm?assignmentId=task-1",
      assignmentId: "task-1",
      targetLabel: "Autoevaluare",
      estimatedMinutes: 25,
      questionnaireKey: "pcm",
      projectId: "proj-123",
      projectName: "Proiect Leadership 2026",
    },
  ],
  results: [
    {
      assignmentId: "res-1",
      questionnaireKey: "lencioni",
      title: "Cele 5 disfuncții ale unei echipe",
      targetLabel: "Echipa Alpha",
      scores: {
        trust: { score: 85, label: "Încredere" },
      },
    },
  ],
  pcmBase: "Thinker",
  pcmPhase: "Persister",
};

describe("ParticipantPreviewView (C1, C2, S4, S5)", () => {
  afterEach(() => {
    cleanup();
  });

  it("renders the permanent sticky banner S4 with participant identity and strict read-only indicator", () => {
    render(
      <ParticipantPreviewView
        companyId="comp-1"
        projectId="proj-123"
        summaryData={mockSummaryData}
      />,
    );

    const banner = screen.getByRole("complementary", {
      name: /Notificare mod vizualizare participant/i,
    });
    expect(banner).toBeDefined();
    expect(screen.getAllByText("Ion Popescu").length).toBeGreaterThan(0);
    expect(screen.getByText("Mod STRICT READ-ONLY")).toBeDefined();
    expect(
      screen.getByText(
        /\(Nicio acțiune nu poate fi efectuată în numele participantului\)/i,
      ),
    ).toBeDefined();
  });

  it("renders the clear exit button S5 linking back to trainer participants list", () => {
    render(
      <ParticipantPreviewView
        companyId="comp-1"
        projectId="proj-123"
        summaryData={mockSummaryData}
      />,
    );

    const exitLink = screen.getByRole("link", {
      name: /Înapoi la participanți/i,
    });
    expect(exitLink).toBeDefined();
    expect(exitLink.getAttribute("href")).toBe(
      "/trainer/projects/proj-123/participants",
    );
  });

  it("renders the exit button pointing to company participants when projectId is not provided", () => {
    render(
      <ParticipantPreviewView
        companyId="comp-1"
        summaryData={mockSummaryData}
      />,
    );

    const exitLink = screen.getByRole("link", {
      name: /Înapoi la participanți/i,
    });
    expect(exitLink.getAttribute("href")).toBe("/trainer/companies/comp-1");
  });

  it("renders the C2 exclusion explanation in Romanian explaining why questionnaires, consent, and account settings are omitted", () => {
    render(
      <ParticipantPreviewView
        companyId="comp-1"
        projectId="proj-123"
        summaryData={mockSummaryData}
      />,
    );

    const exclusionSection = screen.getByRole("region", {
      name: /Informații de confidențialitate și excluderi/i,
    });
    expect(exclusionSection).toBeDefined();
    expect(
      screen.getByText(
        /Ecranele de completare a chestionarelor, consimțământul și setările de cont NU sunt disponibile în această vedere/i,
      ),
    ).toBeDefined();
    expect(
      screen.getByText(
        /pentru că ar expune răspunsurile pe care participantul le-a dat despre alți oameni, respectiv date personale de cont/i,
      ),
    ).toBeDefined();
  });

  it("demonstrates that trainer preview view and participant workspace render the same underlying ParticipantClientWorkspace component on the same data", () => {
    // 1. Render preview view
    render(
      <ParticipantPreviewView
        companyId="comp-1"
        projectId="proj-123"
        summaryData={mockSummaryData}
      />,
    );

    // In preview view, ParticipantClientWorkspace is rendered with readOnly=true
    expect(screen.getAllByText("Proiect Leadership 2026").length).toBeGreaterThan(0);
    expect(screen.getByText("Cele 5 disfuncții ale unei echipe")).toBeDefined();

    // Verify readOnly mode has no form completion links
    expect(
      screen.queryByRole("link", { name: /Deschide|Continuă|Completează/i }),
    ).toBeNull();

    cleanup();

    // 2. Render participant workspace directly with participant session
    const participantSession: SessionState = {
      state: "authenticated",
      user: {
        id: "prof-456",
        name: "Ion Popescu",
        email: "ion.popescu@example.com",
        role: "participant",
      },
    };

    render(
      <ParticipantClientWorkspace
        session={participantSession}
        summaryData={mockSummaryData}
        readOnly={false}
      />,
    );

    // In normal participant view, the same project and task are rendered, but with active link
    expect(screen.getAllByText("Proiect Leadership 2026").length).toBeGreaterThan(0);
    const activeTaskLink = screen.getByRole("link", {
      name: /Deschide/i,
    });
    expect(activeTaskLink).toBeDefined();
    expect(activeTaskLink.getAttribute("href")).toContain(
      "/participant/questionnaires/pcm?assignmentId=task-1",
    );
  });
});
