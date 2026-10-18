/**
 * Tabloul se cere pe proiectul ALES de om — plicul 143.
 *
 * Până la 143 pagina chema tabloul fără proiect, iar serverul nu avea de unde să știe competențele
 * alese de trainer: arăta lista fixă din aplicația veche.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({ getParticipantWorkspaceSummary: vi.fn() }));
const redirectari = vi.hoisted(() => ({ ultima: "" }));

// Ca în src/test/setup.ts (useRouter, useSearchParams, usePathname), plus `redirect` care aruncă.
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn(), back: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
  usePathname: () => "",
  redirect: (url: string) => {
    redirectari.ultima = url;
    throw new Error(`NEXT_REDIRECT:${url}`);
  },
}));

vi.mock("@/api/participants", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/participants")>();
  return { ...original, getParticipantWorkspaceSummary: api.getParticipantWorkspaceSummary };
});
vi.mock("@/api/auth-server", () => ({
  getParticipantSession: vi.fn(async () => ({
    state: "authenticated",
    user: { id: "user-1", name: "Andrei", role: "participant" },
  })),
}));
vi.mock("@/api/server-request", () => ({
  getServerApiRequestOptions: vi.fn(async () => ({ headers: { cookie: "session=test" } })),
}));
vi.mock("../dashboard/PracticeParticipantDashboard", () => ({
  PracticeParticipantDashboard: ({ projectId }: { projectId?: string | null }) => (
    <p>tabloul pe proiectul: {projectId ?? "niciunul"}</p>
  ),
}));

import TablouParticipantPage from "./page";

const sumar = {
  participantProfileId: "profile-1",
  participantFullName: "Andrei Participant",
  projectId: "proiect-ales",
  contexts: [],
  cycles: [],
  tasks: [],
  results: [],
  projects: [],
  questionnaireProjects: [],
  receivedFeedback: null,
  receivedFeedbackGroups: [],
  pcmBase: null,
  pcmPhase: null,
};

// Plicul 190: omul cu 2+ proiecte (un training și un program), fără proiect ales.
const sumarDouaProiecte = {
  ...sumar,
  projectId: null,
  contexts: [
    {
      participantProfileId: "profil-1",
      companyName: "Firma",
      projects: [
        { id: "p-1", name: "Exersează cu Cody", projectType: "training", deadlineLabel: "—", historyBucket: "current", cycles: [] },
        { id: "p-2", name: "Program", projectType: "team_coaching", deadlineLabel: "—", historyBucket: "current", cycles: [] },
      ],
    },
  ],
};

describe("tabloul, pe proiectul ales", () => {
  afterEach(cleanup);
  beforeEach(() => {
    redirectari.ultima = "";
  });

  it("dă tabloului proiectul ales de om", async () => {
    api.getParticipantWorkspaceSummary.mockResolvedValue(sumar);
    render(await TablouParticipantPage({ searchParams: Promise.resolve({ project: "proiect-ales" }) }));
    expect(screen.getByText("tabloul pe proiectul: proiect-ales")).toBeTruthy();
    expect(redirectari.ultima).toBe("");
  });

  it("omul cu 2+ proiecte, fără proiect în adresă, e trimis la bun venit — plicul 190", async () => {
    // Cu 184, Tabloul fără proiect arăta 0 / „Încă nu ai exersat.” omului care exersase pe un proiect.
    api.getParticipantWorkspaceSummary.mockResolvedValue(sumarDouaProiecte);
    await expect(TablouParticipantPage({ searchParams: Promise.resolve({}) })).rejects.toThrow("NEXT_REDIRECT");
    expect(redirectari.ultima.startsWith("/participant/bun-venit")).toBe(true);
  });

  it("trimis la bun venit, își păstrează profilul din adresă — plicul 190", async () => {
    api.getParticipantWorkspaceSummary.mockResolvedValue(sumarDouaProiecte);
    await expect(
      TablouParticipantPage({ searchParams: Promise.resolve({ profile: "profil-1" }) }),
    ).rejects.toThrow("NEXT_REDIRECT");
    expect(redirectari.ultima).toBe("/participant/bun-venit?profile=profil-1");
  });

  it("dacă rezumatul nu se poate citi, tabloul se deschide tot, fără proiect", async () => {
    api.getParticipantWorkspaceSummary.mockRejectedValue(new Error("pică"));
    render(await TablouParticipantPage({ searchParams: Promise.resolve({}) }));
    expect(screen.getByText("tabloul pe proiectul: niciunul")).toBeTruthy();
  });

  it("titlul e „Tabloul tău”, fără nume — plicul 165 A", async () => {
    // Lângă „Codul tău la Cody” apărea numele scos din adresa de email.
    api.getParticipantWorkspaceSummary.mockResolvedValue(sumar);
    render(await TablouParticipantPage({ searchParams: Promise.resolve({ project: "proiect-ales" }) }));
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Tabloul tău");
  });
});
