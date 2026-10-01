/**
 * Mesajul (a) pe Tablou — plicul 177, text propus (Andrei îl vede pe probă, `[culori-texte-noi]`).
 *
 * Apare numai când nota de azi la competență e între 50 și 59 ȘI competența n-are încă niciun punct
 * (corecția 1 a controlorului: „până la primele puncte” ar minți la cine are deja puncte din alte zile).
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}));

const date = vi.hoisted(() => ({ tablou: null as unknown }));

const competenta = (name: string, bestScoreToday: number | null, points = 0) => ({
  name,
  level: "CONȘTIENTIZARE",
  levelDescription: "descriere",
  color: "#E24B4A",
  totalRoleplays: 1,
  scores70Count: 0,
  daysSpan70: 0,
  distinctDays70: 0,
  averageScore: 50,
  whyNotHigher: "Pentru Aplicare: îți mai trebuie 100 puncte.",
  points,
  pointsToday: 0,
  interlocutorTypes: 0,
  bestScoreToday,
});

const tablou = (competencies: ReturnType<typeof competenta>[], emptyState: unknown = null) => ({
  participantName: "Om",
  codyAlias: null,
  xpToday: 0,
  xpDailyCap: 100,
  xpTotal: 0,
  streakDays: 1,
  streakBonusPct: 0,
  evidenceCeiling: 500,
  pointsToday: 0,
  pointsTotal: 0,
  competencies,
  insightMoments: [],
  sessionSamples: [],
  emptyState,
});

vi.mock("@/api/practice", async (original) => ({
  ...(await original<typeof import("@/api/practice")>()),
  getPracticeDashboard: vi.fn(async () => date.tablou),
}));

import { PracticeParticipantDashboard } from "./PracticeParticipantDashboard";

async function deschide(t: unknown, asteptat: string) {
  date.tablou = t;
  render(<PracticeParticipantDashboard projectId="p-1" />);
  await screen.findByText(asteptat, { selector: "h4, div, p" });
}

describe("Tabloul — mesajul notei de azi (plicul 177, a)", () => {
  afterEach(cleanup);

  it("nota 55 azi, fără puncte → textul exact; 59 → „încă 1”; în rest nimic", async () => {
    await deschide(tablou([
      competenta("Ascultare activă", 55),
      competenta("Feedback", 59),
      competenta("Delegare", 60),
      competenta("Negociere", 75),
      competenta("Coaching", 49),
      competenta("Empatie", null),
      competenta("Claritate", 55, 120),
    ]), "Claritate");
    const mesaje = screen.getAllByRole("status").map((e) => e.textContent);
    expect(mesaje).toEqual([
      "Ascultare activă: nota 55 azi — încă 5 până la primele puncte",
      "Feedback: nota 59 azi — încă 1 până la primele puncte",
    ]);
    const unul = screen.getAllByRole("status")[0];
    expect(unul.className).toContain("bg-gold-soft");
    expect(unul.className).toContain("text-nudge-ink");
    expect(unul.querySelector("strong")?.textContent).toBe("nota 55");
  });

  it("tablou gol: nimic nou, rămân textele plicului 98", async () => {
    await deschide(
      tablou([], { kind: "neexersat", title: "Încă n-ai exersat", description: "Începe o simulare." }),
      "Încă n-ai exersat",
    );
    expect(screen.queryByRole("status")).toBeNull();
    expect(document.body.textContent).not.toContain("până la primele puncte");
  });
});
