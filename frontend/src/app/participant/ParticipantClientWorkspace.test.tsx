import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { InviteTask } from "@/api/invites";

import {
  ParticipantClientWorkspace,
  ParticipantResultsHistory,
  ParticipantResultsPanel,
} from "./ParticipantClientWorkspace";
import { ParticipantTaskList } from "./ParticipantTaskList";
import {
  groupParticipantTasksByProject,
} from "./task-display";

describe("ParticipantClientWorkspace", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
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
    expect(screen.queryByText("Recomandare: continuă cu primul chestionar disponibil.")).toBeNull();
    expect(screen.queryByRole("complementary", { name: "Contextul fluxului" })).toBeNull();
  });

  it("makes ready results the primary action after every questionnaire is complete", () => {
    render(
      <ParticipantClientWorkspace
        session={{ state: "authenticated", user: { id: "participant-1", name: "Mihai", role: "participant" } }}
        summaryData={{
          projectName: "Leadership operațional Q3",
          companyName: "Atlas Mobility",
          participantFullName: "Mihai Matei",
          participantEmail: "mihai.matei@example.com",
          deadlineLabel: "31 iul.",
          tasks: [
            {
              id: "drivers-self",
              assignmentId: "drivers-self",
              title: "Driveri de stres TA",
              status: "completed",
              detail: "Autoevaluare finalizată.",
              href: "/participant/questionnaires/distress_drivers?assignmentId=drivers-self",
              targetLabel: "Autoevaluare",
              estimatedMinutes: 8,
              questionnaireKey: "distress_drivers",
            },
          ],
          results: [
            {
              assignmentId: "drivers-self",
              questionnaireKey: "distress_drivers",
              title: "Driveri de stres TA",
              targetLabel: "Autoevaluare",
              scores: { fii_puternic: { score: 72, label: "Fii puternic" } },
            },
          ],
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Rezultatele tale sunt disponibile." })).toBeDefined();
    expect(screen.getByText("Toate chestionarele sunt finalizate")).toBeDefined();
    expect(screen.getByText("1 rezultat este pregătit.")).toBeDefined();
    expect(screen.getByRole("link", { name: /Deschide rezultatele/i }).getAttribute("href")).toBe(
      "/participant/results",
    );
    expect(screen.queryByRole("status", { name: /sarcini active/i })).toBeNull();
  });

  it("keeps the completion state in processing until feedback is actually visible", () => {
    render(
      <ParticipantClientWorkspace
        session={{ state: "authenticated", user: { id: "participant-1", name: "Mihai", role: "participant" } }}
        summaryData={{
          projectName: "Leadership operațional Q3",
          companyName: "Atlas Mobility",
          participantFullName: "Mihai Matei",
          participantEmail: "mihai.matei@example.com",
          deadlineLabel: "31 iul.",
          tasks: [
            {
              id: "feedback-1",
              assignmentId: "feedback-1",
              title: "Feedback confidențial",
              status: "completed",
              detail: "Feedback finalizat.",
              href: "/participant/questionnaires/boss_360?assignmentId=feedback-1",
              targetLabel: "Manager",
              estimatedMinutes: 10,
              questionnaireKey: "boss_360",
            },
          ],
          results: [],
          receivedFeedbackGroups: [
            {
              assignmentRoundId: "round-1",
              cohort: "direct_team",
              completedCount: 1,
              minimumCompleted: 2,
              visible: false,
              dimensions: [],
            },
          ],
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Răspunsurile au fost trimise." })).toBeDefined();
    expect(screen.getByText("Rezultatele vor apărea aici când sunt disponibile.")).toBeDefined();
    expect(screen.queryByRole("link", { name: /Deschide rezultatele/i })).toBeNull();
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

    expect(screen.getByText("2 proiecte în desfășurare")).toBeDefined();
    expect(screen.getByText("1/1 finalizate · 31 iul.")).toBeDefined();
    expect(screen.getByText("0/1 finalizate · 15 aug.")).toBeDefined();
    expect(screen.queryByText("Termen")).toBeNull();
  });

  it("separates current projects from history and excludes history from active progress", () => {
    render(
      <ParticipantClientWorkspace
        session={{ state: "authenticated", user: { id: "participant-1", name: "Mihai", role: "participant" } }}
        summaryData={{
          projectName: "Pilot principal",
          projects: [
            {
              id: "project-current",
              name: "Pilot principal",
              status: "active",
              historyBucket: "current",
              deadlineLabel: "31 iul.",
            },
            {
              id: "project-history",
              name: "Atelier încheiat",
              status: "completed",
              historyBucket: "history",
              deadlineLabel: "Finalizat",
            },
          ],
          companyName: "Companie sintetică",
          participantEmail: "participant@example.com",
          deadlineLabel: "31 iul.",
          results: [],
          tasks: [
            {
              id: "task-current",
              assignmentId: "task-current",
              title: "Activitate curentă",
              status: "not_started",
              detail: "Mostră",
              href: "/participant/tasks/task-current",
              targetLabel: "Autoevaluare",
              estimatedMinutes: 5,
              questionnaireKey: "synthetic_current",
              projectId: "project-current",
              projectName: "Pilot principal",
            },
            {
              id: "task-history",
              assignmentId: "task-history",
              title: "Activitate veche",
              status: "not_started",
              detail: "Mostră",
              href: "/participant/tasks/task-history",
              targetLabel: "Autoevaluare",
              estimatedMinutes: 5,
              questionnaireKey: "synthetic_history",
              projectId: "project-history",
              projectName: "Atelier încheiat",
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("1 în desfășurare · 1 în istoric")).toBeDefined();
    expect(screen.getByRole("status", { name: "1 sarcină activă" })).toBeDefined();
    expect(screen.getByRole("progressbar", { name: "Progresul sarcinilor" }).getAttribute("aria-valuenow")).toBe("0");
    expect(screen.getAllByText("0/1 finalizate").length).toBeGreaterThan(0);
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
                feedback: "Textul de lucru păstrat din definiția chestionarului.",
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
    const guidance = screen.getByText("Textul de lucru păstrat din definiția chestionarului.");
    expect(guidance).toBeDefined();
    expect(guidance.closest(".grid")?.textContent).toContain("Semnal de lucru A");
    expect(screen.getAllByText("De urmărit").length).toBeGreaterThan(0);
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
          {
            assignmentId: "drivers",
            questionnaireKey: "distress_drivers",
            title: "TA Drivers",
            targetLabel: "Autoevaluare",
            scores: {
              hurry_up: { score: 44, label: "Grăbește-te" },
            },
          },
        ]}
      />,
    );

    expect(screen.getAllByText("Semnal de echipă")).toHaveLength(2);
    expect(screen.getByText("Claritate")).toBeDefined();
    expect(screen.getAllByText("Sprijin")).toHaveLength(2);
    const lencioniHeading = screen.getByRole("heading", { name: "Lencioni" });
    const icareHeading = screen.getByRole("heading", { name: "iCARE" });
    const taHeading = screen.getByRole("heading", { name: "TA Drivers", level: 2 });
    expect(lencioniHeading.compareDocumentPosition(icareHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(icareHeading.compareDocumentPosition(taHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByText("feedback_signal_a")).toBeNull();
    expect(screen.queryByText("01")).toBeNull();
    expect(lencioniHeading.parentElement?.querySelector("[data-slot='card']")).toBeTruthy();
  });

  it("keeps iCARE dimensions in the same canonical order across perspectives", () => {
    render(
      <ParticipantResultsPanel
        results={[{
          assignmentId: "icare-self",
          questionnaireKey: "boss_360",
          title: "Autoevaluare iCARE",
          targetLabel: "Cum te evaluezi",
          scores: {
            icare_02_claritate: { score: 92, label: "Claritate" },
            icare_01_dezvoltare: { score: 54, label: "Dezvoltare" },
          },
        }]}
        receivedFeedbackGroups={[{
          cohort: "direct_team",
          completedCount: 2,
          minimumCompleted: 2,
          visible: true,
          dimensions: [
            { id: "icare_02_claritate", label: "Claritate", averageScore: 70, completedCount: 2 },
            { id: "icare_01_dezvoltare", label: "Dezvoltare", averageScore: 88, completedCount: 2 },
          ],
        }]}
      />,
    );

    const teamPerspective = screen.getByRole("group", { name: /Cum te vede echipa ta/ });
    const selfPerspective = screen.getByRole("group", { name: /Cum te evaluezi/ });
    const visibleDimensionLabels = (container: HTMLElement) => (
      [...container.querySelectorAll("h4")].map((heading) => heading.textContent)
    );

    expect(visibleDimensionLabels(teamPerspective)).toEqual(["Dezvoltare", "Claritate"]);
    expect(visibleDimensionLabels(selfPerspective)).toEqual(["Dezvoltare", "Claritate"]);
  });

  it("uses the pinned Lencioni sum range for labels and bars", () => {
    render(
      <ParticipantResultsPanel
        pcmBase={null}
        pcmPhase={null}
        results={[{
          assignmentId: "lencioni",
          questionnaireKey: "lencioni",
          title: "Lencioni",
          targetLabel: "Echipa ta",
          scores: {
            trust: { score: 6, label: "Încredere" },
          },
          scoreUnit: "score",
          scaleMin: 3,
          scaleMax: 9,
          scoreScaleCompatible: true,
        }]}
      />,
    );

    expect(screen.getByText("3-9")).toBeTruthy();
    expect(screen.getAllByText("6 / 9")).toHaveLength(2);
    const meter = screen.getByRole("meter", { name: "Scor Încredere" });
    expect(meter.getAttribute("aria-valuemin")).toBe("3");
    expect(meter.getAttribute("aria-valuemax")).toBe("9");
    expect(meter.firstElementChild?.getAttribute("style")).toContain("width: 50%");
  });

  it("does not guess a participant scale when the published groups are incompatible", () => {
    render(
      <ParticipantResultsPanel
        pcmBase={null}
        pcmPhase={null}
        results={[{
          assignmentId: "lencioni",
          questionnaireKey: "lencioni",
          title: "Lencioni",
          targetLabel: "Echipa ta",
          scores: { trust: { score: 6, label: "Încredere" } },
          scoreScaleCompatible: false,
          unavailableReason: "incompatible_score_scales",
        }]}
      />,
    );

    expect(screen.getByText(/dimensiuni cu scale diferite/)).toBeTruthy();
    expect(screen.queryByRole("meter")).toBeNull();
    expect(screen.queryByText("0-10")).toBeNull();
  });

  it("shows anonymous received iCARE averages after the privacy threshold", () => {
    render(
      <ParticipantResultsPanel
        pcmBase="thinker"
        pcmPhase="persister"
        results={[]}
        receivedFeedback={{
          cohort: "direct_team",
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

    expect(screen.getByText("Cum te vede echipa ta")).toBeDefined();
    expect(screen.getByText(/Vezi doar media grupului/)).toBeDefined();
    expect(screen.getByText("Feedbackuri")).toBeDefined();
    expect(screen.getByText("2")).toBeDefined();
    expect(screen.getByText("Claritate")).toBeDefined();
    expect(screen.getByText("Sprijin")).toBeDefined();
    expect(screen.getByText("92%")).toBeDefined();
    expect(screen.getByText("68%")).toBeDefined();
    expect(screen.getByRole("meter", { name: "Scor Claritate" }).getAttribute("aria-valuemax")).toBe("100");
    expect(
      screen.getByRole("meter", { name: "Scor Claritate" }).firstElementChild?.getAttribute("style"),
    ).toContain("width: 92%");
    expect(
      screen.getByRole("meter", { name: "Scor Sprijin" }).firstElementChild?.getAttribute("style"),
    ).toContain("width: 68%");
    expect(screen.queryByText(/Reviewer One/i)).toBeNull();
    expect(screen.queryByText(/reviewer-one@example\.com/i)).toBeNull();
    expect(screen.queryByText("Nu există scoruri calculate încă")).toBeNull();
    expect(screen.getByRole("region", { name: "Perspective iCARE" })).toBeDefined();
  });

  it("hides received iCARE averages below the privacy threshold", () => {
    render(
      <ParticipantResultsPanel
        pcmBase="thinker"
        pcmPhase="persister"
        results={[]}
        receivedFeedback={{
          cohort: "direct_team",
          completedCount: 1,
          minimumCompleted: 2,
          unavailableReason: "privacy_threshold",
          visible: false,
          overallAverage: null,
          dimensions: [],
        }}
      />,
    );

    expect(screen.getByText("Cum te vede echipa ta")).toBeDefined();
    expect(screen.getByText("1")).toBeDefined();
    expect(screen.getByText(/Pentru confidențialitate, mai avem nevoie de cel puțin 1 răspuns/)).toBeDefined();
    expect(screen.queryByText("Claritate")).toBeNull();
    expect(screen.queryByText("4.5")).toBeNull();
  });

  it.each([
    ["no_eligible_dimensions" as const, "Acest chestionar nu are încă dimensiuni care pot fi afișate în rezultat."],
    ["scoring_unavailable" as const, "Răspunsurile au fost trimise, dar rezultatul nu este disponibil momentan. Nu trebuie completate din nou."],
  ])("explains unavailable iCARE feedback without presenting it as a privacy threshold", (unavailableReason, copy) => {
    render(
      <ParticipantResultsPanel
        results={[]}
        receivedFeedback={{
          cohort: "leadership_peers",
          completedCount: 2,
          minimumCompleted: 2,
          unavailableReason,
          visible: false,
          overallAverage: null,
          dimensions: [],
        }}
      />,
    );

    expect(screen.getByText(copy)).toBeDefined();
    expect(screen.queryByText(/Pentru confidențialitate/)).toBeNull();
  });

  it("renders iCARE averages against the questionnaire scale instead of a percentage", () => {
    render(
      <ParticipantResultsPanel
        pcmBase={null}
        pcmPhase={null}
        results={[]}
        receivedFeedback={{
          assignmentRoundId: "round-1",
          cohort: "leadership_peers",
          questionnaireKey: "boss_360",
          questionnaireTitle: "Feedback iCARE",
          completedCount: 3,
          minimumCompleted: 2,
          scoreUnit: "grade_1_to_5",
          scaleMin: 1,
          scaleMax: 5,
          visible: true,
          overallAverage: 4.2,
          dimensions: [
            { id: "clarity", label: "Claritate", averageScore: 4.5, completedCount: 3 },
          ],
        }}
      />,
    );

    expect(screen.getByText("4.5 din 5")).toBeDefined();
    expect(screen.getByRole("meter", { name: "Scor Claritate" }).getAttribute("aria-valuemin")).toBe("1");
    expect(screen.getByRole("meter", { name: "Scor Claritate" }).getAttribute("aria-valuemax")).toBe("5");
    expect(screen.getByRole("meter", { name: "Scor Claritate" }).getAttribute("aria-valuenow")).toBe("4.5");
    expect(
      screen.getByRole("meter", { name: "Scor Claritate" }).firstElementChild?.getAttribute("style"),
    ).toContain("width: 87.5%");
  });

  it("renders the participant's own iCARE result against its published scale", () => {
    render(
      <ParticipantResultsPanel
        results={[
          {
            assignmentId: "icare-self",
            questionnaireKey: "boss_360",
            title: "Autoevaluare iCARE",
            targetLabel: "Autoevaluare",
            scoreUnit: "grade_1_to_5",
            scaleMin: 1,
            scaleMax: 5,
            scores: {
              clarity: { score: 4.5, label: "Claritate" },
            },
          },
        ]}
      />,
    );

    expect(screen.getAllByText("4.5 din 5")).toHaveLength(2);
    expect(screen.getByText("1-5")).toBeDefined();
    const clarity = screen.getByRole("meter", { name: "Scor Claritate" });
    expect(clarity.getAttribute("aria-valuemin")).toBe("1");
    expect(clarity.getAttribute("aria-valuemax")).toBe("5");
    expect(clarity.firstElementChild?.getAttribute("style")).toContain("width: 87.5%");
  });

  it("defends against a stale raw scale when feedback scores are percentages", () => {
    render(
      <ParticipantResultsPanel
        pcmBase={null}
        pcmPhase={null}
        results={[]}
        receivedFeedback={{
          cohort: "leadership_peers",
          completedCount: 2,
          minimumCompleted: 2,
          scaleMax: 5,
          visible: true,
          overallAverage: 44.4,
          dimensions: [
            { id: "modesty", label: "Modestie", averageScore: 72.2, completedCount: 2 },
            { id: "openness", label: "Deschis către lume", averageScore: 16.6, completedCount: 2 },
          ],
        }}
      />,
    );

    const modesty = screen.getByRole("meter", { name: "Scor Modestie" });
    const openness = screen.getByRole("meter", { name: "Scor Deschis către lume" });
    expect(modesty.getAttribute("aria-valuemax")).toBe("100");
    expect(modesty.firstElementChild?.getAttribute("style")).toContain("width: 72.2%");
    expect(openness.firstElementChild?.getAttribute("style")).toContain("width: 16.6%");
  });

  it("treats the backend visibility decision as authoritative", () => {
    render(
      <ParticipantResultsPanel
        results={[]}
        receivedFeedback={{
          cohort: "leadership_peers",
          completedCount: 2,
          minimumCompleted: 2,
          visible: true,
          overallAverage: 4.1,
          dimensions: [],
        }}
      />,
    );

    expect(screen.getByText("4.1 din 5")).toBeDefined();
    expect(screen.queryByText(/Mai avem nevoie de cel puțin/)).toBeNull();
  });

  it("merges legacy and grouped feedback without duplicating the same round", () => {
    const feedback = {
      assignmentRoundId: "round-shared",
      cohort: "leadership_peers" as const,
      projectId: "project-a",
      questionnaireKey: "boss_360",
      completedCount: 2,
      minimumCompleted: 2,
      visible: true,
      overallAverage: 4,
      dimensions: [{ id: "clarity", label: "Claritate", averageScore: 4, completedCount: 2 }],
    };
    render(
      <ParticipantResultsPanel
        results={[]}
        receivedFeedback={feedback}
        receivedFeedbackGroups={[
          feedback,
          {
            ...feedback,
            assignmentRoundId: "round-other",
            projectId: "project-b",
            projectName: "Al doilea proiect",
          },
        ]}
      />,
    );

    expect(screen.getAllByText("Cum te văd colegii din leadership")).toHaveLength(2);
    expect(screen.getByRole("heading", { name: "2 rezultate disponibile" })).toBeDefined();
  });

  it("shows a clear waiting state when all tasks are complete but no result is publishable", () => {
    render(
      <ParticipantResultsPanel
        results={[]}
        hasTasks
        allTasksComplete
      />,
    );

    expect(screen.getByText("Răspunsurile au fost trimise")).toBeDefined();
    expect(screen.getByText("Rezultatele vor apărea aici după procesare.")).toBeDefined();
    expect(screen.getByText("Răspunsurile au fost trimise").closest("[data-slot='empty']")).toBeTruthy();
    expect(screen.queryByText("Disponibile acum")).toBeNull();
  });

  it("does not show an empty result message when the PCM profile is available", () => {
    render(
      <ParticipantResultsPanel
        results={[]}
        pcmBase="thinker"
        pcmPhase="persister"
      />,
    );

    expect(screen.getByRole("heading", { name: "1 rezultat disponibil" })).toBeDefined();
    expect(screen.getByText("Profil personal")).toBeDefined();
    expect(screen.getByRole("heading", { name: "PCM" }).closest("[data-slot='card']")).toBeTruthy();
    expect(screen.queryByText("Nu există rezultate disponibile încă")).toBeNull();
  });
});

describe("ParticipantResultsHistory", () => {
  afterEach(cleanup);

  it("aligns cycles once and keeps all three iCARE perspectives side by side", () => {
    render(
      <ParticipantResultsHistory
        cycles={[
          {
            cycle: { id: "cycle-1", projectId: "project-1", sequence: 1, name: "Evaluare inițială", status: "closed" },
            pcmBase: "thinker",
            pcmPhase: "persister",
            results: [
              {
                assignmentId: "ta-1",
                questionnaireKey: "distress_drivers",
                title: "TA",
                targetLabel: "Autoevaluare",
                scoreUnit: "percent",
                scaleMin: 0,
                scaleMax: 100,
                scores: {
                  perfect: { score: 62, label: "Fii perfect", feedback: "Acceptă și o variantă suficient de bună." },
                  strong: { score: 50, label: "Fii puternic", feedback: "Acest text nu trebuie afișat la prag." },
                },
              },
              {
                assignmentId: "self-1",
                questionnaireKey: "boss_360",
                title: "iCARE",
                targetLabel: "Autoevaluare",
                scoreUnit: "percent",
                scaleMin: 0,
                scaleMax: 100,
                scores: { clarity: { score: 70, label: "Claritate" } },
              },
            ],
            receivedFeedbackGroups: [{
              cohort: "direct_team",
              completedCount: 2,
              minimumCompleted: 2,
              visible: true,
              scoreUnit: "percent",
              scaleMin: 0,
              scaleMax: 100,
              overallAverage: 74,
              dimensions: [{ id: "clarity", label: "Claritate", averageScore: 74, completedCount: 2 }],
            }],
          },
          {
            cycle: { id: "cycle-2", projectId: "project-1", sequence: 2, name: "Reevaluare", status: "active" },
            pcmBase: "thinker",
            pcmPhase: "promoter",
            results: [{
              assignmentId: "ta-2",
              questionnaireKey: "distress_drivers",
              title: "TA",
              targetLabel: "Autoevaluare",
              scoreUnit: "percent",
              scaleMin: 0,
              scaleMax: 100,
              scores: { perfect: { score: 55, label: "Fii perfect", feedback: "Acceptă și o variantă suficient de bună." } },
            }],
            receivedFeedbackGroups: [{
              cohort: "leadership_peers",
              completedCount: 2,
              minimumCompleted: 2,
              visible: true,
              scoreUnit: "percent",
              scaleMin: 0,
              scaleMax: 100,
              overallAverage: 76,
              dimensions: [{ id: "clarity", label: "Claritate", averageScore: 76, completedCount: 2 }],
            }],
          },
        ]}
      />,
    );

    expect(screen.getByRole("region", { name: "Comparația rezultatelor" })).toBeTruthy();
    expect(screen.getAllByText("Evaluare inițială").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Reevaluare").length).toBeGreaterThan(0);
    expect(screen.getByText("Profil schimbat")).toBeDefined();
    expect(screen.getByText("Fără schimbare")).toBeDefined();
    expect(screen.getByRole("group", { name: /Cum te vede echipa ta/ })).toBeTruthy();
    expect(screen.getByRole("group", { name: /Cum te văd colegii din leadership/ })).toBeTruthy();
    expect(screen.getByRole("group", { name: /Cum te evaluezi/ })).toBeTruthy();
    expect(screen.getByText("Acceptă și o variantă suficient de bună.")).toBeTruthy();
    expect(screen.queryByText("Acest text nu trebuie afișat la prag.")).toBeNull();
  });

  it("uses raw points instead of percentage points for a 1-to-5 iCARE scale", () => {
    render(
      <ParticipantResultsHistory
        cycles={[
          {
            cycle: { id: "cycle-1", projectId: "project-1", sequence: 1, name: "Evaluare inițială", status: "closed" },
            results: [{
              assignmentId: "icare-1",
              questionnaireKey: "boss_360",
              title: "iCARE",
              targetLabel: "Autoevaluare",
              scoreUnit: "grade_1_to_5",
              scaleMin: 1,
              scaleMax: 5,
              scores: { clarity: { score: 3, label: "Claritate" } },
            }],
          },
          {
            cycle: { id: "cycle-2", projectId: "project-1", sequence: 2, name: "Reevaluare", status: "active" },
            results: [{
              assignmentId: "icare-2",
              questionnaireKey: "boss_360",
              title: "iCARE",
              targetLabel: "Autoevaluare",
              scoreUnit: "grade_1_to_5",
              scaleMin: 1,
              scaleMax: 5,
              scores: { clarity: { score: 4, label: "Claritate" } },
            }],
          },
        ]}
      />,
    );

    expect(screen.getByText("+1 punct")).toBeTruthy();
    expect(screen.queryByText("+1 pp")).toBeNull();
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
        projects={groupParticipantTasksByProject(tasks)}
        persistenceIdentityKey="participant-1"
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
        projects={groupParticipantTasksByProject(tasks)}
        persistenceIdentityKey="participant-1"
        returnTo="/participant/questionnaires"
        emptyTitle="Nu ai sarcini"
        emptyDescription="Lista este goală."
      />,
    );

    expect(screen.getAllByRole("heading", { name: "Review 360" })).toHaveLength(2);
    expect(screen.getAllByText("Leadership Q3")).toHaveLength(1);
  });

  it("expands pending projects, collapses completed projects, and remembers choices per identity", () => {
    const pendingTask: InviteTask = {
      id: "pending-task",
      assignmentId: "pending-task",
      title: "iCARE",
      status: "not_started",
      detail: "De completat",
      href: "/participant/tasks/pending-task",
      targetLabel: "Autoevaluare",
      estimatedMinutes: 8,
      questionnaireKey: "icare",
      projectId: "project-pending",
      projectName: "Proiect Atlas",
      cycleName: "Reevaluare",
      cycleSequence: 2,
      deadlineLabel: "31 august 2026",
    };
    const completedTask: InviteTask = {
      ...pendingTask,
      id: "completed-task",
      assignmentId: "completed-task",
      status: "completed",
      href: "/participant/tasks/completed-task",
      projectId: "project-complete",
      projectName: "Proiect Orion",
    };
    const projects = groupParticipantTasksByProject(
      [pendingTask, completedTask],
      [
        {
          id: "project-pending",
          name: "Proiect Atlas",
          deadlineLabel: "31 august 2026",
        },
        {
          id: "project-complete",
          name: "Proiect Orion",
          status: "completed",
          historyBucket: "history",
          deadlineLabel: "Finalizat",
        },
      ],
    );

    const { unmount } = render(
      <ParticipantTaskList
        projects={projects}
        persistenceIdentityKey="participant-a"
        returnTo="/participant/questionnaires"
        emptyTitle="Nu ai sarcini"
        emptyDescription="Lista este goală."
      />,
    );

    const atlas = screen.getByRole("button", { name: /Proiect Atlas/i });
    const orion = screen.getByRole("button", { name: /Proiect Orion/i });
    expect(atlas.getAttribute("aria-expanded")).toBe("true");
    expect(orion.getAttribute("aria-expanded")).toBe("false");
    expect(screen.getByText("Ciclul 2, Reevaluare")).toBeDefined();
    expect(screen.getByText("31 august 2026")).toBeDefined();

    fireEvent.click(atlas);
    expect(atlas.getAttribute("aria-expanded")).toBe("false");
    unmount();

    render(
      <ParticipantTaskList
        projects={projects}
        persistenceIdentityKey="participant-a"
        returnTo="/participant/questionnaires"
        emptyTitle="Nu ai sarcini"
        emptyDescription="Lista este goală."
      />,
    );
    expect(
      screen
        .getByRole("button", { name: /Proiect Atlas/i })
        .getAttribute("aria-expanded"),
    ).toBe("false");

    cleanup();
    render(
      <ParticipantTaskList
        projects={projects}
        persistenceIdentityKey="participant-b"
        returnTo="/participant/questionnaires"
        emptyTitle="Nu ai sarcini"
        emptyDescription="Lista este goală."
      />,
    );
    expect(
      screen
        .getByRole("button", { name: /Proiect Atlas/i })
        .getAttribute("aria-expanded"),
    ).toBe("true");
  });

  it("keeps unfinished questionnaires in historical projects read-only", () => {
    const historicalTask: InviteTask = {
      id: "historical-task",
      assignmentId: "historical-task",
      title: "iCARE",
      status: "in_progress",
      detail: "Început înainte de închiderea proiectului",
      href: "/participant/tasks/historical-task",
      targetLabel: "Autoevaluare",
      estimatedMinutes: 8,
      questionnaireKey: "icare",
      projectId: "project-history",
      projectName: "Proiect încheiat",
    };
    const projects = groupParticipantTasksByProject(
      [historicalTask],
      [{
        id: "project-history",
        name: "Proiect încheiat",
        status: "completed",
        historyBucket: "history",
        deadlineLabel: "Finalizat",
      }],
    );

    render(
      <ParticipantTaskList
        projects={projects}
        persistenceIdentityKey="participant-history"
        returnTo="/participant/questionnaires"
        emptyTitle="Nu ai sarcini"
        emptyDescription="Lista este goală."
      />,
    );

    const projectButton = screen.getByRole("button", { name: /Proiect încheiat/i });
    expect(projectButton.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(projectButton);

    expect(screen.getByText("Închis")).toBeDefined();
    expect(screen.getAllByText("Proiect încheiat").length).toBeGreaterThan(1);
    expect(screen.queryByRole("link", { name: /Continuă review-ul/i })).toBeNull();
    expect(screen.queryByRole("link", { name: /Deschide|Continuă/i })).toBeNull();
  });
});
