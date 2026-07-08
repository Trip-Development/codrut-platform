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

    expect(screen.getByText(/Ai chestionarele pregătite aici/)).toBeDefined();
    expect(screen.queryByText(/baza de date/i)).toBeNull();
    expect(screen.queryByText(/Fiecare sarcină vine din invitațiile pregătite de trainer/i)).toBeNull();
    expect(screen.getByRole("status", { name: "3 sarcini active" })).toBeDefined();
  });
});

describe("ParticipantResultsPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows distress driver feedback inline without requiring expansion", () => {
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
            primaryResult: "be_strong",
            scores: {
              be_strong: 76,
              be_perfect: 58,
              try_hard: 42,
              hurry_up: 66,
              please_people: 34,
            },
          },
        ]}
      />,
    );

    expect(screen.getByText("Fii Puternic")).toBeDefined();
    expect(screen.getByText("Fii Perfect")).toBeDefined();
    expect(screen.getByText("Străduiește-te")).toBeDefined();
    expect(screen.getByText("Mulțumește-i pe alții")).toBeDefined();
    expect(screen.getByText(/sub presiune poți simți/)).toBeDefined();
    expect(screen.getByText(/standardele înalte ajută calitatea/)).toBeDefined();
    expect(screen.queryByText(/energia de a încerca poate fi valoroasă/)).toBeNull();
    expect(screen.queryByRole("button", { name: /Fii Puternic/i })).toBeNull();
  });

  it("uses participant-facing labels and filters raw iCARE section keys", () => {
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
            primaryResult: "fear_of_conflict",
            scores: {
              fear_of_conflict: { score: 5, interpretation: "Disfuncția trebuie probabil abordată." },
            },
          },
          {
            assignmentId: "icare",
            questionnaireKey: "boss_360",
            title: "iCARE 360 pentru manager",
            targetLabel: "Manager direct",
            primaryResult: "icare_06_aduce_claritate",
            scores: {
              icare_inspiring_developing_people: { score: 4.4 },
              icare_01_dezvolta_oamenii: { score: 4.2 },
              icare_06_aduce_claritate: { score: 3.1 },
            },
          },
        ]}
      />,
    );

    expect(screen.getByText("Teama de conflict")).toBeDefined();
    expect(screen.getByText("Dezvoltă oamenii")).toBeDefined();
    expect(screen.getByText("Aduce claritate")).toBeDefined();
    expect(screen.queryByText(/Icare Inspiring Developing People/i)).toBeNull();
    expect(screen.queryByText("icare_inspiring_developing_people")).toBeNull();
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
});
