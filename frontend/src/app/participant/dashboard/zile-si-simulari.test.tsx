/**
 * Tabloul: „zile la rând cu activitate” și „N simulări făcute” — plicul 201.
 *
 * Andrei, 1 oct: „Nr de zile dar trebuie să și facă ceva. simulare sau quiz sau strategie” ·
 * „Sau rămân amândouă.” 18 oct: numărul e totalul, eticheta „simulări făcute”. Eticheta
 * zilelor e textul propus de chatul aplicației, de confirmat de Andrei.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PracticeDashboardData } from "@/api/practice";

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}));

const tablou = vi.hoisted(() => ({ zile: 1, simulari: 3 }));

vi.mock("@/api/practice", async (original) => ({
  ...(await original<typeof import("@/api/practice")>()),
  getPracticeDashboard: vi.fn(async (): Promise<PracticeDashboardData> => ({
    participantName: "Participant Test",
    codyAlias: "Fox 34",
    xpToday: 0,
    xpDailyCap: 100,
    xpTotal: 0,
    streakDays: tablou.zile,
    streakBonusPct: 0,
    evidenceCeiling: 500,
    pointsToday: 0,
    pointsTotal: 40,
    sessionsCompleted: tablou.simulari,
    competencies: [{
      name: "Feedback constructiv",
      level: "APLICARE",
      levelDescription: "Începi să-l folosești.",
      color: "#1A4A7A",
      totalRoleplays: 1,
      scores70Count: 0,
      daysSpan70: 0,
      distinctDays70: 0,
      averageScore: 60,
      whyNotHigher: "",
      points: 40,
      pointsToday: 0,
      interlocutorTypes: 1,
      bestScoreToday: null,
    }],
    insightMoments: [],
    sessionSamples: [],
    emptyState: null,
  })),
}));

import { PracticeParticipantDashboard } from "./PracticeParticipantDashboard";

async function textulTabloului(zile: number, simulari: number): Promise<string> {
  tablou.zile = zile;
  tablou.simulari = simulari;
  render(<PracticeParticipantDashboard projectId="p-1" />);
  await screen.findByText("Feedback constructiv");
  return document.body.textContent ?? "";
}

describe("tabloul: zile cu activitate și simulări făcute — plicul 201", () => {
  afterEach(cleanup);

  it("la o zi și trei simulări", async () => {
    const text = await textulTabloului(1, 3);
    expect(text).toContain("zi cu activitate");
    expect(text).not.toContain("zi activă");
    expect(text).toContain("3 simulări făcute");
  });

  it("la mai multe zile și o simulare", async () => {
    const text = await textulTabloului(4, 1);
    expect(text).toContain("zile la rând cu activitate");
    expect(text).not.toContain("zile consecutive");
    expect(text).toContain("1 simulare făcută");
  });

  it("la zero simulări cartonașul se vede", async () => {
    const text = await textulTabloului(0, 0);
    expect(text).toContain("Serie de zile");
    expect(text).toContain("0 simulări făcute");
  });
});
