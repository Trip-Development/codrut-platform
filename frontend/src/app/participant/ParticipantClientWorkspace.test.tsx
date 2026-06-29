import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { ParticipantResultsPanel } from "./ParticipantClientWorkspace";

describe("ParticipantResultsPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows all distress driver scores and expands feedback from the matching bar", () => {
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
    expect(screen.queryByText(/sub presiune poți simți/)).toBeNull();
    expect(screen.queryByText(/standardele înalte ajută calitatea/)).toBeNull();
    expect(screen.queryByText(/energia de a încerca poate fi valoroasă/)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: /Fii Puternic/i }));
    expect(screen.getByText(/sub presiune poți simți/)).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: /Fii Perfect/i }));
    expect(screen.getByText(/standardele înalte ajută calitatea/)).toBeDefined();
    expect(screen.queryByText(/energia de a încerca poate fi valoroasă/)).toBeNull();
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
              icare_inspiring_developing_people: { score: 88 },
              icare_01_dezvolta_oamenii: { score: 83 },
              icare_06_aduce_claritate: { score: 61 },
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
