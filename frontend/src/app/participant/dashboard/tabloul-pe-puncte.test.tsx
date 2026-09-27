/**
 * Tabloul pe punctajul nou — plicul 165, partea B (hotărârea lui Andrei, 27 septembrie).
 *
 * „Puncte azi” fără „/ 100” și fără „Plafon zilnic”; seria fără bonus de XP; totalul = suma
 * punctelor (fără „Prag dovezi proiect”); pe fiecare competență: nivelul, punctele ei, simulările,
 * media, tipurile de interlocutor și „De ce nu e mai sus?”.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}));
vi.mock("@/api/practice", async (original) => ({
  ...(await original<typeof import("@/api/practice")>()),
  getPracticeDashboard: vi.fn(async () => ({
    participantName: "Andrei Test",
    codyAlias: "Fox 34",
    xpToday: 7,
    xpDailyCap: 100,
    xpTotal: 999,
    streakDays: 4,
    streakBonusPct: 5,
    evidenceCeiling: 500,
    pointsToday: 55,
    pointsTotal: 435,
    competencies: [{
      name: "Feedback asertiv",
      level: "CONSOLIDARE",
      levelDescription: "Îl aplici consistent în majoritatea situațiilor.",
      color: "#1A4A7A",
      totalRoleplays: 9,
      scores70Count: 0,
      daysSpan70: 0,
      distinctDays70: 0,
      averageScore: 81.5,
      whyNotHigher: "Pentru Integrare: îți mai trebuie 565 puncte.",
      points: 435,
      pointsToday: 55,
      interlocutorTypes: 2,
    }],
    insightMoments: [],
    sessionSamples: [],
  })),
}));

import { PracticeParticipantDashboard } from "./PracticeParticipantDashboard";

describe("tabloul pe puncte — plicul 165", () => {
  afterEach(cleanup);

  it("arată punctele, fără plafon, fără bonus, fără prag de dovezi", async () => {
    render(<PracticeParticipantDashboard projectId="p-1" />);
    await screen.findByText("Feedback asertiv");
    const tot = document.body.textContent ?? "";
    expect(screen.getByText("55")).toBeTruthy();
    expect(tot).toContain("435 puncte");
    expect(tot).not.toMatch(/\/ ?100/);
    expect(tot).not.toContain("Plafon zilnic");
    expect(tot).not.toContain("Bonus XP");
    expect(tot).not.toContain("Prag dovezi");
    expect(tot).not.toContain("999");
    expect(tot).toContain("4");
    expect(tot).toContain("2 tipuri de interlocutor");
    expect(tot).toContain("9 simulări în rol");
    expect(tot).toContain("Medie: 81.5%");
    expect(tot).toContain("Pentru Integrare: îți mai trebuie 565 puncte.");
    expect(tot).not.toContain("scoruri ≥ 70%");
  });
});
