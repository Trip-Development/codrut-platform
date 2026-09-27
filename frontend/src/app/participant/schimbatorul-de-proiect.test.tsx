/**
 * Schimbătorul de proiect stă în meniu, pe toate paginile participantului — plicul 160, partea A.
 *
 * Andrei, 27 septembrie: lista „Proiect" stătea în corpul paginii, și numai pe unele pagini; la
 * alegere se schimba meniul, dar omul rămânea pe aceeași pagină (pe „Exersează" cu un proiect de
 * chestionare, de pildă).
 */

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import React from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const rute = vi.hoisted(() => ({
  replace: vi.fn(),
  push: vi.fn(),
  pathname: "/participant/results",
  searchParams: new URLSearchParams("cycle=c1&baseline=c0&compare=c1"),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => rute.pathname,
  useRouter: () => ({ replace: rute.replace, push: rute.push }),
  useSearchParams: () => rute.searchParams,
}));
vi.mock("next/link", () => ({
  default: ({ href, children, ...props }: React.AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) => (
    <a href={href} {...props}>{children}</a>
  ),
}));
vi.mock("@/api/http", () => ({ apiFetch: vi.fn(), ensureCsrfToken: vi.fn() }));
vi.mock("@/components/ui/searchable-combobox", () => ({
  SearchableCombobox: ({
    value,
    options,
    onValueChange,
  }: {
    value: string;
    options: { value: string; label: string }[];
    onValueChange: (value: string) => void;
  }) => (
    <div data-testid="lista-proiect">
      ales: {value || "(niciunul)"}
      {options.map((option) => (
        <button key={option.value} type="button" onClick={() => onValueChange(option.value)}>
          {option.label}
        </button>
      ))}
    </div>
  ),
}));
vi.mock("@/components/reports/CycleComparisonToolbar", () => ({
  CycleComparisonToolbar: () => <div />,
}));

import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems, participantTrainingNavItems } from "@/components/shell/nav";
import { SidebarStateContext } from "@/components/shell/sidebar-state";
import { ParticipantContextSelector } from "./ParticipantContextSelector";
import {
  participantActiveProjectType,
  participantScopedNavItems,
} from "./participant-context";

// Ca contul A: un proiect de chestionare și unul de training, în aceeași firmă.
const DOUA = [
  {
    participantProfileId: "profil-1",
    companyName: "Firma A",
    projects: [
      { id: "p-chestionare", name: "Program de leadership", projectType: "team_coaching", deadlineLabel: "—", cycles: [] },
      { id: "p-training", name: "Exersează cu Cody", projectType: "training", deadlineLabel: "—", cycles: [] },
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

function inMeniu(element: React.ReactNode, { collapsed = false, mobile = false } = {}) {
  return (
    <SidebarStateContext.Provider value={{ inSidebar: true, collapsed, mobile }}>
      {element}
    </SidebarStateContext.Provider>
  );
}

describe("schimbătorul de proiect — plicul 160", () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("stă în meniul lateral și în meniul de pe telefon", () => {
    const { container } = render(
      <AppShell
        audience="participant"
        title="Rezultate"
        navItems={participantNavItems}
        activeHref="/participant/results"
        sidebarTop={<span>SCHIMBĂTORUL</span>}
      >
        <p>corpul paginii</p>
      </AppShell>,
    );
    expect(container.querySelector("aside [data-sidebar-top]")?.textContent).toBe("SCHIMBĂTORUL");
    expect(container.querySelector("main")?.textContent).not.toContain("SCHIMBĂTORUL");

    fireEvent.click(screen.getByLabelText("Deschide meniul de navigare"));
    expect(container.querySelector("[data-mobile-sidebar-top]")?.textContent).toBe("SCHIMBĂTORUL");
  });

  it("trainerul nu are schimbător", () => {
    const { container } = render(
      <AppShell audience="trainer" title="Acasă" navItems={[]} activeHref="/trainer">
        <p>trainer</p>
      </AppShell>,
    );
    expect(container.querySelector("[data-sidebar-top]")).toBeNull();
  });

  it("toate paginile participantului îl dau în meniu, niciuna în corp; paginile trainerului nu-l dau", () => {
    const radacina = join(process.cwd(), "src/app");
    const paginiParticipant = [
      "participant/ParticipantClientWorkspace.tsx",
      "participant/questionnaires/page.tsx",
      "participant/results/page.tsx",
      "participant/tablou/page.tsx",
      "participant/practice/page.tsx",
      "participant/chat/page.tsx",
      "participant/final-evaluation/page.tsx",
      "participant/account/page.tsx",
    ];
    for (const pagina of paginiParticipant) {
      const sursa = readFileSync(join(radacina, pagina), "utf8");
      const bucati = sursa.split("<ParticipantContextSelector").slice(1);
      expect(bucati.length, pagina).toBeGreaterThan(0);
      expect(sursa, pagina).toContain("sidebarTop={");
      for (const [i, dupa] of bucati.entries()) {
        const inainte = sursa.split("<ParticipantContextSelector").slice(0, i + 1).join("").slice(-80);
        const bloc = dupa.slice(0, dupa.indexOf("/>"));
        // în meniu, sau în previzualizarea trainerului (care n-are meniu), cu pagina păstrată
        expect(inainte.includes("sidebarTop={") || bloc.includes("keepPage"), pagina).toBe(true);
      }
    }
    const paginiTrainer = [
      "trainer/page.tsx",
      "trainer/companies/page.tsx",
      "trainer/projects/page.tsx",
      "trainer/settings/page.tsx",
    ];
    for (const pagina of paginiTrainer) {
      expect(readFileSync(join(radacina, pagina), "utf8"), pagina).not.toContain("sidebarTop");
    }
  });

  it("cu un singur proiect, în meniu se vede numai numele, fără listă", () => {
    render(inMeniu(<ParticipantContextSelector contexts={UNUL} selectedProjectId="p-chestionare" />));
    expect(screen.getByText("Program de leadership")).toBeTruthy();
    expect(screen.queryByTestId("lista-proiect")).toBeNull();
  });

  it("ales un proiect de training → la „Exersează”", () => {
    render(inMeniu(<ParticipantContextSelector contexts={DOUA} selectedProjectId="p-chestionare" />));
    fireEvent.click(screen.getByRole("button", { name: "Exersează cu Cody" }));
    const unde = rute.push.mock.calls[0][0] as string;
    expect(unde.startsWith("/participant/practice?")).toBe(true);
    expect(unde).toContain("project=p-training");
    expect(unde).toContain("profile=profil-1");
    expect(unde).not.toMatch(/cycle=|baseline=|compare=/);
  });

  it("ales alt proiect → la pagina proiectului", () => {
    rute.pathname = "/participant/practice";
    render(inMeniu(<ParticipantContextSelector contexts={DOUA} selectedProjectId="p-training" />));
    fireEvent.click(screen.getByRole("button", { name: "Program de leadership" }));
    const unde = rute.push.mock.calls[0][0] as string;
    expect(unde.startsWith("/participant?")).toBe(true);
    expect(unde).toContain("project=p-chestionare");
  });

  it("nimic ales, 2+ proiecte → „Alege proiectul” roșu; ales → dispare", () => {
    const { container, rerender } = render(
      inMeniu(<ParticipantContextSelector contexts={DOUA} selectedProjectId={null} />),
    );
    const rosu = container.querySelector("[data-participant-project-required]");
    expect(rosu?.textContent).toBe("Alege proiectul");
    expect(rosu?.className).toContain("text-destructive");

    rerender(inMeniu(<ParticipantContextSelector contexts={DOUA} selectedProjectId="p-training" />));
    expect(container.querySelector("[data-participant-project-required]")).toBeNull();
  });

  it("meniul strâns: o iconiță, cu numele proiectului la trecerea cu mouse-ul", () => {
    const { container } = render(
      inMeniu(<ParticipantContextSelector contexts={DOUA} selectedProjectId="p-training" />, { collapsed: true }),
    );
    expect(container.querySelector("[data-participant-project-collapsed]")?.getAttribute("title")).toBe(
      "Exersează cu Cody",
    );
    expect(screen.queryByTestId("lista-proiect")).toBeNull();
  });

  it("copia din meniul de pe telefon nu mută omul a doua oară", () => {
    window.localStorage.setItem("codrut:proiect:profil-1", "p-training");
    render(inMeniu(<ParticipantContextSelector contexts={DOUA} selectedProjectId={null} />, { mobile: true }));
    expect(rute.replace).not.toHaveBeenCalled();
  });

  it("meniul urmează proiectul ales, pentru un om cu amândouă proiectele", () => {
    function meniulDupaAlegere(nume: string) {
      cleanup();
      rute.push.mockClear();
      render(inMeniu(<ParticipantContextSelector contexts={DOUA} selectedProjectId={null} />));
      fireEvent.click(screen.getByRole("button", { name: nume }));
      const params = new URL(`http://x${rute.push.mock.calls[0][0] as string}`).searchParams;
      const summary = { projectId: params.get("project"), projects: [], contexts: DOUA as never };
      return participantScopedNavItems(params, {
        projectType: participantActiveProjectType(summary),
      }).map((item) => item.label);
    }
    expect(meniulDupaAlegere("Exersează cu Cody")).toEqual(
      participantTrainingNavItems.map((item) => item.label),
    );
    expect(meniulDupaAlegere("Program de leadership")).toEqual(
      participantNavItems.map((item) => item.label),
    );
  });
});
