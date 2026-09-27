/**
 * Bun venit și schimbătorul, la omul cu profiluri în mai multe firme — plicul 162.
 *
 * Găsit la audit, pe probă, pe contul gmail al lui Andrei (2 profiluri: unul cu 4 proiecte, unul cu
 * 1): cu `?profile=` în adresă, sumarul serverului se restrânge la profilul acela. Bun venit număra
 * deci 1 proiect și îl trimitea înapoi pe pagina veche; „Acasă” nu mai ducea la bun venit, iar
 * schimbătorul arăta numai proiectele acelui profil. Cei 19 de la Michelin (un profil) nu sunt
 * atinși: restrânsul la profilul lor păstrează toate proiectele.
 *
 * Testul cheamă paginile de server cu API-ul simulat exact așa: fără profil — tot contul; cu profil
 * — un singur context.
 */

import { beforeEach, describe, expect, it, vi } from "vitest";

const redirectari = vi.hoisted(() => ({ ultima: "" }));
vi.mock("next/navigation", () => ({
  redirect: (url: string) => {
    redirectari.ultima = url;
    throw new Error(`NEXT_REDIRECT:${url}`);
  },
}));
vi.mock("@/api/auth-server", () => ({
  getParticipantSession: async () => ({ user: { id: "u-1", name: "Andrei", role: "participant" } }),
}));
vi.mock("@/api/server-request", () => ({
  getServerApiRequestOptions: async () => ({ headers: {} }),
}));
vi.mock("@/api/participant-onboarding", () => ({
  getParticipantOnboardingState: async () => ({ required: false, href: null }),
}));

const proiect = (id: string, name: string, projectType: string) => ({
  id, name, projectType, deadlineLabel: "—", historyBucket: "current", cycles: [],
});
const FIRMA_1 = {
  participantProfileId: "profil-1",
  companyName: "Firma unu",
  projects: [
    proiect("p-a", "Exersează cu Cody — demo", "training"),
    proiect("p-b", "Program de leadership — demo", "leadership_program"),
    proiect("p-c", "Repetiție Michelin 28 sept", "training"),
    proiect("p-d", "Test proiect", "training"),
  ],
};
const FIRMA_2 = {
  participantProfileId: "profil-2",
  companyName: "Firma test — B",
  projects: [proiect("p-e", "Exersează cu Cody", "training")],
};
const baza = {
  participantFullName: "Andrei Test B",
  participantEmail: "b@exemplu-demo.example",
  deadlineLabel: "—",
  tasks: [],
  results: [],
  projects: [],
  questionnaireProjects: [],
  emptyState: { title: "Nu ai sarcini active", description: "" },
};

const cereri = vi.hoisted(() => ({ lista: [] as Array<Record<string, unknown>>, forma: "doua-firme" }));
// Forma contului A și a celor 19: UN profil, două proiecte (chestionare + Cody) — sau unul singur.
const UN_PROFIL = {
  participantProfileId: "profil-a",
  companyName: "Firma A",
  projects: [proiect("p-q", "Program de leadership", "team_coaching"), proiect("p-t", "Exersează cu Cody", "training")],
};
vi.mock("@/api/participants", async (original) => ({
  ...(await original<typeof import("@/api/participants")>()),
  getParticipantWorkspaceSummary: async (opts: Record<string, unknown> = {}) => {
    cereri.lista.push(opts);
    if (cereri.forma === "un-profil") {
      return { ...baza, contexts: [UN_PROFIL], participantProfileId: "profil-a", projectId: opts.projectId ?? null };
    }
    if (cereri.forma === "un-proiect") {
      return { ...baza, contexts: [{ ...UN_PROFIL, projects: [UN_PROFIL.projects[1]] }], participantProfileId: "profil-a", projectId: "p-t" };
    }
    if (opts.participantProfileId === "profil-2") {
      return { ...baza, contexts: [FIRMA_2], participantProfileId: "profil-2", projectId: "p-e" };
    }
    return { ...baza, contexts: [FIRMA_1, FIRMA_2], contextSelectionRequired: true, projectId: null };
  },
}));

import ParticipantWelcomePage from "./bun-venit/page";
import ParticipantWorkspacePage from "./page";
import ParticipantPracticePage from "./practice/page";

type Element = { props: Record<string, never> & { children?: unknown } };
const nrProiecte = (contexts: Array<{ projects: unknown[] }>) =>
  contexts.reduce((n, c) => n + c.projects.length, 0);

describe("omul din mai multe firme — plicul 162", () => {
  beforeEach(() => {
    redirectari.ultima = "";
    cereri.lista = [];
    cereri.forma = "doua-firme";
  });

  it("bun venit, cu ?profile= în adresă, rămâne pe bun venit și arată toate cele 5 proiecte", async () => {
    const el = (await ParticipantWelcomePage({
      searchParams: Promise.resolve({ profile: "profil-2", project: "p-e" }),
    })) as unknown as Element;
    expect(redirectari.ultima).toBe("");
    const pagina = el.props.children as Element;
    expect(nrProiecte(pagina.props.contexts as never)).toBe(5);
  });

  it("`/participant?profile=…` fără proiect duce la bun venit, ca fără profil", async () => {
    await expect(
      ParticipantWorkspacePage({ searchParams: Promise.resolve({ profile: "profil-2" }) }),
    ).rejects.toThrow("NEXT_REDIRECT");
    expect(redirectari.ultima.startsWith("/participant/bun-venit")).toBe(true);
  });

  it("pe „Exersează”, cu ?profile=: „Acasă” duce la bun venit, iar schimbătorul are toate proiectele", async () => {
    const el = (await ParticipantPracticePage({
      searchParams: Promise.resolve({ profile: "profil-2", project: "p-e" }),
    })) as unknown as Element;
    const acasa = (el.props.navItems as Array<{ label: string; href: string }>).find((i) => i.label === "Acasă");
    expect(acasa?.href.startsWith("/participant/bun-venit?")).toBe(true);
    const schimbatorul = el.props.sidebarTop as Element;
    expect(nrProiecte(schimbatorul.props.contexts as never)).toBe(5);
    // proiectul ales rămâne cel din adresă
    expect(schimbatorul.props.selectedProjectId).toBe("p-e");
  });

  it("fără ?profile= în adresă nu se face nicio cerere în plus", async () => {
    await ParticipantWelcomePage({ searchParams: Promise.resolve({}) });
    expect(cereri.lista).toHaveLength(1);
  });

  it("POARTA — un profil cu două proiecte (contul A, cei 19): aceeași listă, același bun venit", async () => {
    cereri.forma = "un-profil";
    const el = (await ParticipantPracticePage({
      searchParams: Promise.resolve({ profile: "profil-a", project: "p-t" }),
    })) as unknown as Element;
    const schimbatorul = el.props.sidebarTop as Element;
    expect(schimbatorul.props.contexts).toEqual([UN_PROFIL]);
    const acasa = (el.props.navItems as Array<{ label: string; href: string }>).find((i) => i.label === "Acasă");
    expect(acasa?.href.startsWith("/participant/bun-venit?")).toBe(true);
  });

  it("POARTA — un singur proiect: bun venit îl trimite tot la pagina veche, ca înainte", async () => {
    cereri.forma = "un-proiect";
    await expect(
      ParticipantWelcomePage({ searchParams: Promise.resolve({ profile: "profil-a" }) }),
    ).rejects.toThrow("NEXT_REDIRECT");
    expect(redirectari.ultima).toBe("/participant?profile=profil-a");
  });
});
