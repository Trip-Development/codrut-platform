/**
 * Tabloul în paleta A — plicul 175.
 *
 * Eticheta nivelului ia culoarea după nivel (jetoane), nu după `color` venit de la server; pe fiecare
 * competență intră bara spre pragul următor, fără niciun cuvânt nou. Textele noi (T1/T2) nu sunt aici.
 */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children }: { href: string; children: React.ReactNode }) => <a href={href}>{children}</a>,
}));

const competenta = (name: string, level: string, points: number) => ({
  name,
  level,
  levelDescription: "descriere",
  color: "#ff00ff",
  totalRoleplays: 1,
  scores70Count: 0,
  daysSpan70: 0,
  distinctDays70: 0,
  averageScore: 70,
  whyNotHigher: "",
  points,
  pointsToday: 10,
  interlocutorTypes: 1,
});

vi.mock("@/api/practice", async (original) => ({
  ...(await original<typeof import("@/api/practice")>()),
  getPracticeDashboard: vi.fn(async () => ({
    participantName: "Om",
    codyAlias: null,
    xpToday: 0,
    xpDailyCap: 100,
    xpTotal: 0,
    streakDays: 3,
    streakBonusPct: 0,
    evidenceCeiling: 500,
    pointsToday: 40,
    pointsTotal: 2000,
    competencies: [
      competenta("Ascultare", "CONȘTIENTIZARE", 50),
      competenta("Feedback", "APLICARE", 250),
      competenta("Delegare", "INTEGRARE", 1200),
      competenta("Negociere", "APLICARE", 500),
      competenta("Coaching", "CONSOLIDARE", 600),
    ],
    insightMoments: [],
    sessionSamples: [{ id: "s", realWeak: "slab", realImproved: "bun" }],
  })),
}));

import { PracticeParticipantDashboard } from "./PracticeParticipantDashboard";

async function deschide() {
  render(<PracticeParticipantDashboard projectId="p-1" />);
  await screen.findByText("Delegare", { selector: "h4" });
}

describe("Tabloul în paleta A — plicul 175", () => {
  afterEach(cleanup);

  it("eticheta nivelului folosește culorile paletei, nu culoarea venită de la server", async () => {
    await deschide();
    const html = document.body.innerHTML;
    expect(html).not.toMatch(/#ff00ff|rgb\(255, 0, 255\)/i);
    const eticheta = (nivel: string) => screen.getAllByText(nivel).find((e) => e.tagName === "SPAN" && e.className.includes("rounded-full"))!;
    expect(eticheta("CONȘTIENTIZARE").className).toContain("bg-track");
    expect(eticheta("APLICARE").className).toContain("bg-gold-soft");
    expect(eticheta("CONSOLIDARE").className).toContain("bg-burgundy-soft");
    expect(eticheta("INTEGRARE").className).toContain("bg-success-soft");
    expect(eticheta("INTEGRARE").className).not.toContain("text-white");
  });

  it("bara: 50 la Conștientizare → 50%, 250 la Aplicare → 62,5%, 1.200 la Integrare → 100%, 500 la Aplicare → 100%", async () => {
    await deschide();
    const bare = [...document.querySelectorAll<HTMLElement>("[data-bara-puncte]")];
    const latimi = Object.fromEntries(bare.map((b) => [b.dataset.baraPuncte, b.style.width]));
    expect(latimi).toMatchObject({ Ascultare: "50%", Feedback: "62.5%", Delegare: "100%", Negociere: "100%", Coaching: "60%" });
    for (const b of bare) expect(b.closest("[aria-hidden='true']")).not.toBeNull();
  });

  it("nicio culoare Tailwind scrisă de mână pe Tablou și niciun text nou", async () => {
    await deschide();
    const html = document.body.innerHTML;
    expect(html).not.toMatch(/(text|bg|border)-(amber|orange|rose|emerald)-\d/);
    expect(html).not.toMatch(/#1A4A7A|#639922|#BA7517|#E24B4A/i);
    const tot = document.body.textContent ?? "";
    expect(tot).not.toContain("puncte azi la");
    expect(tot).not.toContain("Cel mai aproape");
  });
});
