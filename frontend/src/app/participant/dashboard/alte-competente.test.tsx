/**
 * „Alte competențe exersate” pe Tablou — plicul 178 (H4), texte propuse (Andrei le vede pe probă).
 * Competențele exersate care nu sunt în lista programului apar dedesubt, cu același card, și intră în total.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}));

const date = vi.hoisted(() => ({ tablou: null as unknown }));

const competenta = (name: string, points: number) => ({
  name, level: "CONȘTIENTIZARE", levelDescription: "descriere", color: "#E24B4A", totalRoleplays: 2,
  scores70Count: 0, daysSpan70: 0, distinctDays70: 0, averageScore: 60, whyNotHigher: "",
  points, pointsToday: 0, interlocutorTypes: 1, bestScoreToday: null,
});

const tablou = (otherCompetencies: ReturnType<typeof competenta>[]) => ({
  participantName: "Om", codyAlias: null, xpToday: 0, xpDailyCap: 100, xpTotal: 0, streakDays: 0,
  streakBonusPct: 0, evidenceCeiling: 500, pointsToday: 0, pointsTotal: 260,
  competencies: [competenta("Ascultare activă", 50), competenta("Feedback constructiv", 40), competenta("Delegare", 0)],
  otherCompetencies, insightMoments: [], sessionSamples: [], emptyState: null,
});

vi.mock("@/api/practice", async (original) => ({
  ...(await original<typeof import("@/api/practice")>()),
  getPracticeDashboard: vi.fn(async () => date.tablou),
}));

import { PracticeParticipantDashboard } from "./PracticeParticipantDashboard";
import { DESCRIERE_ALTE_COMPETENTE, TITLU_ALTE_COMPETENTE } from "../texte-178";

async function deschide(t: unknown) {
  date.tablou = t;
  render(<PracticeParticipantDashboard projectId="p-1" />);
  await screen.findByText("Ascultare activă", { selector: "h4" });
}

describe("Tabloul — alte competențe exersate (plicul 178)", () => {
  afterEach(cleanup);

  it("o competență din afara listei: titlul, descrierea și cardul ei", async () => {
    await deschide(tablou([competenta("Rezolvarea colaborativă a conflictelor", 50)]));
    expect(screen.getByText(TITLU_ALTE_COMPETENTE)).toBeTruthy();
    expect(screen.getByText(DESCRIERE_ALTE_COMPETENTE)).toBeTruthy();
    expect(screen.getByText("Rezolvarea colaborativă a conflictelor", { selector: "h4" })).toBeTruthy();
    // radarul rămâne pe lista proiectului: 3 vârfuri, fără competența din afara listei
    expect(document.querySelectorAll('svg circle[r="4.5"]')).toHaveLength(3);
    // „{n} competențe evaluate” numără lista proiectului
    expect(screen.getByText("3 competențe evaluate")).toBeTruthy();
  });

  it("fără competențe din afara listei: nimic nou", async () => {
    await deschide(tablou([]));
    expect(screen.queryByText(TITLU_ALTE_COMPETENTE)).toBeNull();
    expect(screen.queryByText(DESCRIERE_ALTE_COMPETENTE)).toBeNull();
  });
});
