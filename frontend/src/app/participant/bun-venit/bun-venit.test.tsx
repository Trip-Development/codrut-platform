/**
 * Pagina „Acasă" de bun venit — plicul 160, partea B (hotărârea lui Andrei, 27 septembrie).
 *
 * Numai omul cu 2+ proiecte o vede. Poarta: omul cu un singur proiect vede exact ce vedea.
 */

import { cleanup, render, screen } from "@testing-library/react";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));

import {
  participantHasWelcomePage,
  participantScopedNavItems,
  participantShouldOpenWelcome,
} from "../participant-context";
import { PaginaDeBunVenit } from "./PaginaDeBunVenit";
import { BUN_VENIT, CITATE, citatulZilei } from "./texte";

const DOUA = [
  {
    participantProfileId: "profil-1",
    participantFullName: "Ana Numele-Nu-Se-Vede",
    companyName: "Firma A",
    projects: [
      { id: "p-chestionare", name: "Program de leadership", projectType: "team_coaching", deadlineLabel: "—", cycles: [] },
      { id: "p-training", name: "Cody pentru lideri", projectType: "training", deadlineLabel: "—", cycles: [] },
    ],
  },
] as never;

const UNUL = [
  {
    participantProfileId: "profil-1",
    companyName: "Firma A",
    projects: [
      { id: "p-chestionare", name: "Program de leadership", projectType: "team_coaching", deadlineLabel: "—", cycles: [] },
    ],
  },
] as never;

const PARAMS = new URLSearchParams("profile=profil-1&project=p-training");

describe("pagina de bun venit — plicul 160 B", () => {
  beforeEach(() => cleanup());

  it("cu 2+ proiecte, „Acasă” duce la bun venit, din ambele meniuri", () => {
    for (const projectType of ["training", "team_coaching"]) {
      const acasa = participantScopedNavItems(PARAMS, { projectType, contexts: DOUA })
        .find((item) => item.label === "Acasă");
      expect(acasa?.href).toBe("/participant/bun-venit?profile=profil-1&project=p-training");
    }
  });

  it("POARTA: cu un singur proiect, meniul e identic cu cel de azi", () => {
    for (const projectType of ["training", "team_coaching"]) {
      expect(participantScopedNavItems(PARAMS, { projectType, contexts: UNUL })).toEqual(
        participantScopedNavItems(PARAMS, { projectType }),
      );
    }
    expect(participantHasWelcomePage(UNUL)).toBe(false);
  });

  it("POARTA: cu un singur proiect, `/participant` rămâne pagina de azi (nicio mutare)", () => {
    expect(participantShouldOpenWelcome({}, UNUL)).toBe(false);
    expect(participantShouldOpenWelcome({ profile: "profil-1" }, UNUL)).toBe(false);
  });

  it("cu 2+ proiecte: fără proiect ales (și după login) → bun venit; cu proiect ales → pagina proiectului", () => {
    expect(participantShouldOpenWelcome({}, DOUA)).toBe(true);
    expect(participantShouldOpenWelcome({ project: "p-chestionare" }, DOUA)).toBe(false);
  });

  it("pagina: citatul zilei, câte proiecte, un card pe proiect, rândul de ajutor, fără nume", () => {
    const zi = new Date("2026-09-27T09:00:00Z");
    const { container } = render(<PaginaDeBunVenit contexts={DOUA} acum={zi} />);
    const citat = citatulZilei(zi);
    expect(CITATE).toContain(citat);
    expect(screen.getByText(citat.text)).toBeTruthy();
    expect(screen.getByText(citat.autor)).toBeTruthy();
    expect(screen.getByText("Ești în 2 proiecte:")).toBeTruthy();
    expect(container.querySelectorAll("[data-proiect-bun-venit]")).toHaveLength(2);
    expect(screen.getByText(BUN_VENIT.tipTraining)).toBeTruthy();
    expect(screen.getByText(BUN_VENIT.tipAltul)).toBeTruthy();
    expect(screen.getByText(BUN_VENIT.ajutor)).toBeTruthy();
    expect(container.textContent).not.toContain("Ana");
  });

  it("„Intră în proiect”: training → Exersează; chestionare → pagina proiectului", () => {
    render(<PaginaDeBunVenit contexts={DOUA} />);
    const legaturi = screen.getAllByRole("link", { name: BUN_VENIT.buton }).map((a) => a.getAttribute("href"));
    expect(legaturi).toContain("/participant/practice?profile=profil-1&project=p-training");
    expect(legaturi).toContain("/participant?profile=profil-1&project=p-chestionare");
  });

  it("două firme: numele firmei stă lângă proiect, ca în schimbător; cele încheiate, la sfârșit", () => {
    const doua = [
      {
        participantProfileId: "profil-1",
        companyName: "Firma A",
        projects: [
          { id: "p-vechi", name: "Program încheiat", projectType: "team_coaching", historyBucket: "history", deadlineLabel: "—", cycles: [] },
        ],
      },
      {
        participantProfileId: "profil-2",
        companyName: "Firma B",
        projects: [
          { id: "p-nou", name: "Cody pentru lideri", projectType: "training", historyBucket: "current", deadlineLabel: "—", cycles: [] },
        ],
      },
    ] as never;
    const { container } = render(<PaginaDeBunVenit contexts={doua} />);
    const carduri = [...container.querySelectorAll("[data-proiect-bun-venit]")];
    expect(carduri[0].textContent).toContain("Firma B · Cody pentru lideri");
    expect(carduri[1].textContent).toContain("Firma A · Program încheiat");
    expect(carduri[1].className).toContain("opacity-60");
  });

  it("citatul se rotește după zi, prin toate trei", () => {
    const zile = [0, 1, 2].map((i) => citatulZilei(new Date(Date.UTC(2026, 8, 27 + i, 12))).autor);
    expect(new Set(zile).size).toBe(3);
  });
});
