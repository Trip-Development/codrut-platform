import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { InviteTask } from "@/api/invites";

import { ParticipantClientWorkspace, ParticipantResultsPanel } from "./ParticipantClientWorkspace";
import { ParticipantTaskList } from "./ParticipantTaskList";
import { groupParticipantTasks } from "./task-display";

describe("ParticipantClientWorkspace", () => {
  afterEach(() => {
    cleanup();
  });

  it("keeps the participant home copy focused and shows active work as a compact status", () => {
    render(
      <ParticipantClientWorkspace
        session={{
          state: "authenticated",
          user: {
            id: "participant-1",
            name: "Mihai Matei",
            email: "mihai.matei@example.com",
            role: "participant",
          },
        }}
        summaryData={{
          projectName: "Leadership operațional Q3",
          companyName: "Atlas Mobility",
          participantFullName: "Mihai Matei",
          anonymousName: "SignalHarbor5271",
          participantEmail: "mihai.matei@example.com",
          deadlineLabel: "Fără termen",
          pcmBase: null,
          pcmPhase: null,
          results: [],
          tasks: [
            {
              id: "drivers-self",
              title: "Driveri de stres TA",
              status: "not_started",
              detail: "Autoevaluare.",
              href: "/participant/questionnaires/distress_drivers?assignmentId=drivers-self",
              assignmentId: "drivers-self",
              targetLabel: "Autoevaluare",
              estimatedMinutes: 8,
              questionnaireKey: "distress_drivers",
            },
            {
              id: "team-feedback",
              title: "Feedback pentru echipă",
              status: "not_started",
              detail: "Răspunde pentru echipă.",
              href: "/participant/questionnaires/lencioni?assignmentId=team-feedback",
              assignmentId: "team-feedback",
              targetLabel: "Echipa operațională Atlas",
              estimatedMinutes: 12,
              questionnaireKey: "lencioni",
            },
            {
              id: "boss-360",
              title: "Feedback confidențial",
              status: "in_progress",
              detail: "Feedback de completat.",
              href: "/participant/questionnaires/boss_360?assignmentId=boss-360",
              assignmentId: "boss-360",
              targetLabel: "Bianca Pavel",
              estimatedMinutes: 10,
              questionnaireKey: "boss_360",
            },
          ],
        }}
      />,
    );

    expect(screen.queryByText(/Ai chestionarele pregătite aici/)).toBeNull();
    expect(screen.getByRole("heading", { name: "De completat" })).toBeDefined();
    expect(screen.queryByText(/baza de date/i)).toBeNull();
    expect(screen.queryByText(/Fiecare sarcină vine din invitațiile pregătite de trainer/i)).toBeNull();
    expect(screen.getByRole("status", { name: "3 sarcini active" })).toBeDefined();
    expect(screen.getByRole("heading", { name: "Bună, Mihai" })).toBeDefined();
    expect(screen.queryByText("Bună, SignalHarbor5271")).toBeNull();
  });

  it("shows the backend recovery state instead of generic workspace filler", () => {
    render(
      <ParticipantClientWorkspace
        session={{
          state: "authenticated",
          user: { id: "participant-1", name: "Participant", role: "participant" },
        }}
        summaryData={{
          projectName: "Niciun proiect activ",
          companyName: "Neasociată",
          participantEmail: "participant@example.com",
          deadlineLabel: "Fără termen",
          results: [],
          tasks: [],
          emptyState: {
            title: "Spațiul nu este disponibil",
            description: "Verifică adresa de email cu trainerul.",
          },
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Spațiul nu este disponibil" })).toBeDefined();
    expect(screen.getByText("Verifică adresa de email cu trainerul.")).toBeDefined();
    expect(screen.queryByText("Spațiul tău de lucru")).toBeNull();
  });

  it("shows separate progress and deadlines when a participant belongs to multiple projects", () => {
    render(
      <ParticipantClientWorkspace
        session={{ state: "authenticated", user: { id: "participant-1", name: "Mihai", role: "participant" } }}
        summaryData={{
          projectName: "Pilot principal",
          projects: [
            { id: "project-a", name: "Pilot principal", deadlineLabel: "31 iul." },
            { id: "project-b", name: "Atelier secundar", deadlineLabel: "15 aug." },
          ],
          companyName: "Companie sintetică",
          participantEmail: "participant@example.com",
          deadlineLabel: "31 iul.",
          results: [],
          tasks: [
            {
              id: "task-a",
              assignmentId: "task-a",
              title: "Activitate A",
              status: "completed",
              detail: "Mostră",
              href: "/participant/tasks/task-a",
              targetLabel: "Autoevaluare",
              estimatedMinutes: 5,
              questionnaireKey: "synthetic_a",
              projectId: "project-a",
              projectName: "Pilot principal",
            },
            {
              id: "task-b",
              assignmentId: "task-b",
              title: "Activitate B",
              status: "not_started",
              detail: "Mostră",
              href: "/participant/tasks/task-b",
              targetLabel: "Autoevaluare",
              estimatedMinutes: 5,
              questionnaireKey: "synthetic_b",
              projectId: "project-b",
              projectName: "Atelier secundar",
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("2 proiecte active")).toBeDefined();
    expect(screen.getByText("1/1 finalizate · 31 iul.")).toBeDefined();
    expect(screen.getByText("0/1 finalizate · 15 aug.")).toBeDefined();
    expect(screen.queryByText("Termen")).toBeNull();
  });
});

describe("ParticipantResultsPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows only participant-approved labels and guidance returned by the backend", () => {
    render(
      <ParticipantResultsPanel
        pcmBase="thinker"
        pcmPhase="persister"
        results={[
          {
            assignmentId: "drivers",
            questionnaireKey: "distress_drivers",
            title: "Driveri de stres TA",
            targetLabel: "Autoevaluare",
            primaryResult: "work_signal_a",
            scores: {
              work_signal_a: {
                score: 76,
                label: "Semnal de lucru A",
                interpretation: "Observă acest tipar în situațiile cu presiune.",
              },
              work_signal_b: { score: 58, label: "Semnal de lucru B" },
              work_signal_c: { score: 42, label: "Semnal de lucru C" },
            },
          },
        ]}
      />,
    );

    expect(screen.getAllByText("Semnal de lucru A")).toHaveLength(2);
    expect(screen.getByText("Semnal de lucru B")).toBeDefined();
    expect(screen.getByText("Semnal de lucru C")).toBeDefined();
    expect(screen.getByText(/Observă acest tipar/)).toBeDefined();
    expect(screen.queryByText("work_signal_a")).toBeNull();
  });

  it("uses participant-facing labels from the protected result contract", () => {
    render(
      <ParticipantResultsPanel
        pcmBase="thinker"
        pcmPhase="persister"
        results={[
          {
            assignmentId: "lencioni",
            questionnaireKey: "lencioni",
            title: "Lencioni - evaluare echipă",
            targetLabel: "Echipa de direcție",
            primaryResult: "team_signal_a",
            scores: {
              team_signal_a: { score: 5, label: "Semnal de echipă", interpretation: "Subiect de discutat în echipă." },
            },
          },
          {
            assignmentId: "icare",
            questionnaireKey: "boss_360",
            title: "iCARE 360 pentru manager",
            targetLabel: "Manager direct",
            primaryResult: "feedback_signal_b",
            scores: {
              feedback_signal_a: { score: 82, label: "Claritate" },
              feedback_signal_b: { score: 53, label: "Sprijin" },
            },
          },
        ]}
      />,
    );

    expect(screen.getAllByText("Semnal de echipă")).toHaveLength(2);
    expect(screen.getByText("Claritate")).toBeDefined();
    expect(screen.getAllByText("Sprijin")).toHaveLength(2);
    expect(screen.queryByText("feedback_signal_a")).toBeNull();
  });

  it("shows anonymous received iCARE averages after the privacy threshold", () => {
    render(
      <ParticipantResultsPanel
        pcmBase="thinker"
        pcmPhase="persister"
        results={[]}
        receivedFeedback={{
          completedCount: 2,
          minimumCompleted: 2,
          visible: true,
          overallAverage: 80,
          dimensions: [
            { id: "feedback_signal_a", label: "Claritate", averageScore: 92, completedCount: 2 },
            { id: "feedback_signal_b", label: "Sprijin", averageScore: 68, completedCount: 2 },
          ],
        }}
      />,
    );

    expect(screen.getByText("Feedback primit")).toBeDefined();
    expect(screen.getByText(/Mediile sunt anonime/)).toBeDefined();
    expect(screen.getByText("Feedbackuri")).toBeDefined();
    expect(screen.getByText("2")).toBeDefined();
    expect(screen.getByText("Claritate")).toBeDefined();
    expect(screen.getByText("Sprijin")).toBeDefined();
    expect(screen.getByText("92")).toBeDefined();
    expect(screen.getByText("68")).toBeDefined();
    expect(screen.getByRole("meter", { name: "Scor Claritate" }).getAttribute("aria-valuemax")).toBe("100");
    expect(screen.queryByText(/Reviewer One/i)).toBeNull();
    expect(screen.queryByText(/reviewer-one@example\.com/i)).toBeNull();
    expect(screen.queryByText("Nu există scoruri calculate încă")).toBeNull();
  });

  it("hides received iCARE averages below the privacy threshold", () => {
    render(
      <ParticipantResultsPanel
        pcmBase="thinker"
        pcmPhase="persister"
        results={[]}
        receivedFeedback={{
          completedCount: 1,
          minimumCompleted: 2,
          visible: false,
          overallAverage: null,
          dimensions: [],
        }}
      />,
    );

    expect(screen.getByText("Feedback primit")).toBeDefined();
    expect(screen.getByText("1")).toBeDefined();
    expect(screen.getByText(/Media apare după minimum 2 feedbackuri completate/)).toBeDefined();
    expect(screen.queryByText("Claritate")).toBeNull();
    expect(screen.queryByText("4.5")).toBeNull();
  });

  it("renders iCARE averages against the questionnaire scale instead of a percentage", () => {
    render(
      <ParticipantResultsPanel
        pcmBase={null}
        pcmPhase={null}
        results={[]}
        receivedFeedback={{
          assignmentRoundId: "round-1",
          questionnaireKey: "boss_360",
          questionnaireTitle: "Feedback iCARE",
          completedCount: 3,
          minimumCompleted: 2,
          scaleMax: 5,
          visible: true,
          overallAverage: 4.2,
          dimensions: [
            { id: "clarity", label: "Claritate", averageScore: 4.5, completedCount: 3 },
          ],
        }}
      />,
    );

    expect(screen.getByText("4.5")).toBeDefined();
    expect(screen.getByRole("meter", { name: "Scor Claritate" }).getAttribute("aria-valuemax")).toBe("5");
    expect(screen.getByRole("meter", { name: "Scor Claritate" }).getAttribute("aria-valuenow")).toBe("4.5");
  });
});

describe("ParticipantTaskList", () => {
  afterEach(() => {
    cleanup();
  });

  it("groups 360 tasks as one review entry with progress and a safe action link", () => {
    const tasks: InviteTask[] = [
      {
        id: "drivers-self",
        title: "Driveri de stres TA",
        status: "completed",
        detail: "Autoevaluare finalizată.",
        href: "/participant/questionnaires/distress_drivers?assignmentId=drivers-self",
        assignmentId: "drivers-self",
        targetLabel: "Autoevaluare",
        estimatedMinutes: 8,
        questionnaireKey: "distress_drivers",
      },
      {
        id: "boss-360-complete",
        title: "Feedback confidențial",
        status: "completed",
        detail: "Feedback finalizat.",
        href: "/participant/questionnaires/boss_360?assignmentId=boss-360-complete",
        assignmentId: "boss-360-complete",
        targetLabel: "Adriana Ionescu",
        estimatedMinutes: 10,
        questionnaireKey: "boss_360",
      },
      {
        id: "boss-360-pending",
        title: "Feedback confidențial",
        status: "not_started",
        detail: "Feedback de completat.",
        href: "/participant/questionnaires/boss_360?assignmentId=boss-360-pending",
        assignmentId: "boss-360-pending",
        targetLabel: "bianca.pavel@example.com",
        estimatedMinutes: 10,
        questionnaireKey: "boss_360",
      },
    ];

    render(
      <ParticipantTaskList
        groups={groupParticipantTasks(tasks)}
        returnTo="/participant/questionnaires"
        emptyTitle="Nu ai sarcini"
        emptyDescription="Lista este goală."
      />,
    );

    expect(screen.getByRole("heading", { name: "Review 360" })).toBeDefined();
    expect(screen.getByText("2 persoane de evaluat")).toBeDefined();
    expect(screen.getByText("1/2 finalizate")).toBeDefined();
    expect(screen.queryByText(/bianca\.pavel@example\.com/i)).toBeNull();

    const reviewLink = screen.getByRole("link", { name: /Continuă review-ul/i });
    expect(reviewLink.getAttribute("href")).toContain("assignmentId=boss-360-pending");
    expect(reviewLink.getAttribute("href")).not.toContain("bianca.pavel%40example.com");
  });

  it("keeps separate 360 rounds in the same project as separate review entries", () => {
    const common = {
      title: "Feedback confidențial",
      status: "not_started" as const,
      detail: "Feedback de completat.",
      estimatedMinutes: 10,
      questionnaireKey: "boss_360",
      projectId: "project-1",
      projectName: "Leadership Q3",
    };
    const tasks: InviteTask[] = [
      {
        ...common,
        id: "round-one-task",
        assignmentId: "round-one-task",
        assignmentRoundId: "round-1",
        href: "/participant/questionnaires/boss_360?assignmentId=round-one-task",
        targetLabel: "Bianca Pavel",
      },
      {
        ...common,
        id: "round-two-task",
        assignmentId: "round-two-task",
        assignmentRoundId: "round-2",
        href: "/participant/questionnaires/boss_360?assignmentId=round-two-task",
        targetLabel: "Darius Neagu",
      },
    ];

    render(
      <ParticipantTaskList
        groups={groupParticipantTasks(tasks)}
        returnTo="/participant/questionnaires"
        emptyTitle="Nu ai sarcini"
        emptyDescription="Lista este goală."
      />,
    );

    expect(screen.getAllByRole("heading", { name: "Review 360" })).toHaveLength(2);
    expect(screen.getAllByText("Leadership Q3")).toHaveLength(2);
  });
});
