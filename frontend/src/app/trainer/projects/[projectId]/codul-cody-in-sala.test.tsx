/**
 * Corespondența cod–nume, în sala trainerului — plicul 138.
 *
 * Spre Google pleacă numai codul omului (`Fox 34`). Cine e în spatele codului o vede numai
 * trainerul, aici, într-o coloană a listei de participanți. Cine n-a exersat încă n-are cod.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { TrainingRoom as TrainingRoomData } from "@/api/practice";

import { TrainingRoom } from "./TrainingRoom";

const om = (id: string, fullName: string, codyAlias: string | null) => ({
  participantProfileId: id,
  userId: null,
  fullName,
  email: null,
  codyAlias,
  hasAccount: true,
  averageScore: 0,
  sessionsCount: 0,
  lastActivity: null,
  inactive: true,
  hasTestIn: false,
  hasTestOut: false,
  activeMembership: true,
});

const sala: TrainingRoomData = {
  projectId: "p-1",
  projectName: "Test proiect",
  projectType: "training",
  themeName: null,
  practiceConfigured: true,
  startsAt: null,
  dueAt: null,
  timelinePercent: null,
  participantsTotal: 2,
  averageScore: 0,
  sessionsTotal: 0,
  inactiveCount: 2,
  testInCompleted: 0,
  testOutCompleted: 0,
  activeCount: 0,
  recurrentCount: 0,
  testOutActive: false,
  competencies: [],
  growthRanking: [],
  quizWeakSpots: [],
  weeklyAverage: [],
  participants: [om("a", "Ionela Testescu", "Fox 34"), om("b", "Radu Probescu", null)],
};

describe("sala trainerului arată codul lui Cody lângă nume", () => {
  afterEach(cleanup);

  it("are coloana și codul fiecăruia; cine n-a exersat încă are o linie", () => {
    render(<TrainingRoom room={sala} basePath="/trainer/projects/p-1" />);
    expect(screen.getByRole("columnheader", { name: "Cod Cody" })).toBeTruthy();
    const randIonela = screen.getByText("Ionela Testescu").closest("tr");
    expect(randIonela?.textContent).toContain("Fox 34");
    const randRadu = screen.getByText("Radu Probescu").closest("tr");
    expect(randRadu?.textContent).not.toContain("Fox 34");
    expect(randRadu?.textContent).toContain("—");
  });
});
