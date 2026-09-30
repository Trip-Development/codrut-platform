/**
 * Pachetul 14, ecranele — plicul 166 (cererea chatului Aplicației, 29 septembrie).
 *
 * A1 · omul cu UN proiect de training: „Acasă” și `/participant` duc la Exersează; omul cu un
 *      proiect de alt tip vede exact ce vedea (poarta de la 160).
 * A2 · textul de ajutor de pe bun venit, neutru (pe telefon meniul e sub ☰).
 * A3 · cardul lui Cody nu mai scrie de două ori „Exersează cu Cody”.
 * A4 · numele din profil peste tot, niciodată cel făcut din adresă.
 * A5 · „Tip proiect”: nimic ales dinainte, o explicație sub fiecare tip.
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const stare = vi.hoisted(() => ({ redirect: "", forma: "training" }));
vi.mock("next/navigation", () => ({
  redirect: (url: string) => {
    stare.redirect = url;
    throw new Error(`NEXT_REDIRECT:${url}`);
  },
  usePathname: () => "/participant",
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("@/api/auth-server", () => ({
  // numele contului e făcut din adresă — exact ce nu trebuie să apară (A4)
  getParticipantSession: async () => ({ user: { id: "u-1", name: "andrei.adresa", role: "participant" } }),
}));
vi.mock("@/api/server-request", () => ({ getServerApiRequestOptions: async () => ({ headers: {} }) }));
vi.mock("@/api/participant-onboarding", () => ({
  getParticipantOnboardingState: async () => ({ required: false, href: null }),
}));
vi.mock("../participant/dashboard/PracticeParticipantDashboard", () => ({
  PracticeParticipantDashboard: () => <p>tabloul</p>,
}));
vi.mock("./dashboard/PracticeParticipantDashboard", () => ({
  PracticeParticipantDashboard: () => <p>tabloul</p>,
}));

const proiect = (id: string, name: string, projectType: string) => ({
  id, name, projectType, deadlineLabel: "—", historyBucket: "current", cycles: [],
});
const sumar = (projectType: string, projectId: string | null) => ({
  participantFullName: "Ioana Profil",
  participantEmail: "adresa@exemplu-demo.example",
  deadlineLabel: "—", tasks: [], results: [], projects: [], questionnaireProjects: [],
  emptyState: { title: "Nu ai sarcini active", description: "" },
  participantProfileId: "profil-1",
  projectId,
  contexts: [{
    participantProfileId: "profil-1", participantFullName: "Ioana Profil", companyId: "c", companyName: "Firma",
    projects: [proiect("p-1", projectType === "training" ? "Exersează cu Cody" : "Program", projectType)],
  }],
});
vi.mock("@/api/participants", async (original) => ({
  ...(await original<typeof import("@/api/participants")>()),
  getParticipantWorkspaceSummary: async (opts: { projectId?: string | null } = {}) =>
    sumar(stare.forma, opts.projectId ?? null),
}));

import { ProjectTypeChoice, PROJECT_TYPE_CHOICES } from "@/components/projects/project-type-choice";
import { PaginaDeBunVenit } from "./bun-venit/PaginaDeBunVenit";
import { BUN_VENIT } from "./bun-venit/texte";
import ParticipantWorkspacePage from "./page";
import {
  participantDisplayName,
  participantScopedNavItems,
  participantSingleTrainingProject,
} from "./participant-context";
import TablouParticipantPage from "./tablou/page";

const PARAMS = new URLSearchParams("profile=profil-1&project=p-1");
type Element = { props: Record<string, unknown> };

describe("pachetul 14 — ecranele (plicul 166)", () => {
  beforeEach(() => {
    stare.redirect = "";
    stare.forma = "training";
  });
  afterEach(cleanup);

  it("A1 · un singur proiect de training: „Acasă” duce la Exersează", () => {
    const acasa = participantScopedNavItems(PARAMS, {
      projectType: "training", contexts: sumar("training", "p-1").contexts,
    }).find((i) => i.label === "Acasă");
    expect(acasa?.href).toBe("/participant/practice?profile=profil-1&project=p-1");
    expect(participantSingleTrainingProject(sumar("training", null).contexts))
      .toEqual({ profileId: "profil-1", projectId: "p-1" });
  });

  it("A1 · `/participant` fără proiect duce la Exersează; cu proiectul în adresă, nu", async () => {
    await expect(ParticipantWorkspacePage({ searchParams: Promise.resolve({}) })).rejects.toThrow("NEXT_REDIRECT");
    expect(stare.redirect).toBe("/participant/practice?profile=profil-1&project=p-1");
    stare.redirect = "";
    await ParticipantWorkspacePage({ searchParams: Promise.resolve({ project: "p-1" }) });
    expect(stare.redirect).toBe("");
  });

  it("A1 · POARTA: un singur proiect de alt tip — meniul și pagina ca înainte", async () => {
    stare.forma = "team_coaching";
    const contexts = sumar("team_coaching", "p-1").contexts;
    expect(participantScopedNavItems(PARAMS, { projectType: "team_coaching", contexts }))
      .toEqual(participantScopedNavItems(PARAMS, { projectType: "team_coaching" }));
    expect(participantSingleTrainingProject(contexts)).toBeNull();
    await ParticipantWorkspacePage({ searchParams: Promise.resolve({}) });
    expect(stare.redirect).toBe("");
  });

  it("A2 · textul de ajutor, neutru", () => {
    expect(BUN_VENIT.ajutor).toBe("Poți trece oricând de la un proiect la altul din lista de proiecte din meniu.");
  });

  it("A3 · „Exersează cu Cody” nu mai apare de două ori pe cardul lui Cody", () => {
    const { container } = render(
      <PaginaDeBunVenit contexts={[{
        participantProfileId: "profil-1", participantFullName: "Ioana Profil", companyId: "c", companyName: "Firma",
        projects: [proiect("p-1", "Exersează cu Cody", "training"), proiect("p-2", "Program de leadership", "team_coaching")],
      }] as never} />,
    );
    const carduri = [...container.querySelectorAll("[data-proiect-bun-venit]")];
    expect(carduri[0].textContent?.match(/Exersează cu Cody/g)).toHaveLength(1);
    expect(carduri[1].textContent).toContain(BUN_VENIT.tipAltul);
  });

  it("A4 · numele din profil, niciodată cel din adresă", async () => {
    expect(participantDisplayName({ participantFullName: "Ioana Profil" })).toBe("Ioana");
    expect(participantDisplayName({ participantFullName: "", contexts: [{ participantFullName: "Mihai Test" }] }))
      .toBe("Mihai");
    expect(participantDisplayName(null)).toBe("Participant");
    const el = (await TablouParticipantPage({ searchParams: Promise.resolve({ project: "p-1" }) })) as unknown as Element;
    expect(el.props.userLabel).toBe("Ioana");
    expect(el.props.title).toBe("Tabloul tău"); // Tabloul rămâne fără nume
  });

  it("A5 · „Tip proiect”: nimic ales dinainte, o explicație sub fiecare tip", () => {
    const ales = vi.fn();
    render(<ProjectTypeChoice name="t" value="" onChange={ales} />);
    const radio = screen.getAllByRole("radio") as HTMLInputElement[];
    expect(radio).toHaveLength(PROJECT_TYPE_CHOICES.length);
    expect(radio.some((r) => r.checked)).toBe(false);
    expect(screen.getByText("Exersare cu Cody. Participanții nu primesc chestionare.")).toBeTruthy();
    fireEvent.click(screen.getByLabelText(/Training/));
    expect(ales).toHaveBeenCalledWith("training");
    // un tip vechi, din afara listei, rămâne vizibil și ales
    cleanup();
    render(<ProjectTypeChoice name="t" value="cohort_program" onChange={ales} />);
    expect((screen.getByDisplayValue("cohort_program") as HTMLInputElement).checked).toBe(true);
  });
});
