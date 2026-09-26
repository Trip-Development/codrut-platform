/**
 * Proiectul ales e ținut minte — plicul 129, partea A.
 *
 * Andrei, 22 septembrie: a ieșit la rezultate, s-a întors, și butonul „Începe conversația" era
 * gri. Cauza, măsurată la plicul 128: proiectul trăia NUMAI în adresa din bară. Se întâmplă numai
 * la oamenii cu două proiecte — deci la orice lider Michelin cu 360 și training.
 */

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const rute = vi.hoisted(() => ({
  replace: vi.fn(),
  push: vi.fn(),
  pathname: "/participant/practice",
  searchParams: new URLSearchParams(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => rute.pathname,
  useRouter: () => ({ replace: rute.replace, push: rute.push }),
  useSearchParams: () => rute.searchParams,
}));
vi.mock("@/components/ui/searchable-combobox", () => ({
  SearchableCombobox: ({ value }: { value: string }) => <div>ales: {value || "(niciunul)"}</div>,
}));
vi.mock("@/components/reports/CycleComparisonToolbar", () => ({
  CycleComparisonToolbar: () => <div />,
}));

import { ParticipantContextSelector } from "./ParticipantContextSelector";

const CONTEXTE = [
  {
    participantProfileId: "profil-1",
    companyName: "test",
    projects: [
      { id: "proiect-A", name: "Repetiție Michelin 28 sept", deadlineLabel: "—", cycles: [] },
      { id: "proiect-B", name: "Test proiect", deadlineLabel: "—", cycles: [] },
    ],
  },
] as never;

const CHEIA = "codrut:proiect:profil-1";

describe("proiectul ales e ținut minte", () => {
  beforeEach(() => {
    cleanup();
    vi.clearAllMocks();
    window.localStorage.clear();
  });
  afterEach(() => vi.unstubAllGlobals());

  it("alegerea se scrie în browser când vine din adresă", () => {
    render(
      <ParticipantContextSelector
        contexts={CONTEXTE}
        selectedProfileId="profil-1"
        selectedProjectId="proiect-A"
      />,
    );
    expect(window.localStorage.getItem(CHEIA)).toBe("proiect-A");
    expect(rute.replace).not.toHaveBeenCalled();
  });

  it("fără proiect în adresă, cel ținut minte e folosit", () => {
    window.localStorage.setItem(CHEIA, "proiect-A");

    render(<ParticipantContextSelector contexts={CONTEXTE} selectedProjectId={null} />);

    expect(rute.replace).toHaveBeenCalledTimes(1);
    const unde = rute.replace.mock.calls[0][0] as string;
    expect(unde).toContain("project=proiect-A");
    expect(unde).toContain("profile=profil-1");
  });

  it("ținut minte, dar scos din lista lui: se uită și nu duce nicăieri", () => {
    window.localStorage.setItem(CHEIA, "proiect-care-nu-mai-e");

    render(<ParticipantContextSelector contexts={CONTEXTE} selectedProjectId={null} />);

    expect(rute.replace).not.toHaveBeenCalled();
    expect(window.localStorage.getItem(CHEIA)).toBeNull();
  });

  it("browserul refuză memoria: pagina merge mai departe, fără să crape", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => {
        throw new Error("blocat");
      },
      setItem: () => {
        throw new Error("blocat");
      },
      removeItem: () => {
        throw new Error("blocat");
      },
    });

    expect(() =>
      render(
        <ParticipantContextSelector
          contexts={CONTEXTE}
          selectedProfileId="profil-1"
          selectedProjectId="proiect-A"
        />,
      ),
    ).not.toThrow();
    expect(screen.getByText(/ales:/)).toBeTruthy();
  });

  it("cu un singur proiect nu se schimbă nimic — selectorul nici nu se arată", () => {
    const unSingur = [
      {
        participantProfileId: "profil-1",
        companyName: "test",
        projects: [{ id: "proiect-A", name: "Unul", deadlineLabel: "—", cycles: [] }],
      },
    ] as never;

    const { container } = render(
      <ParticipantContextSelector contexts={unSingur} selectedProjectId="proiect-A" />,
    );
    expect(container.textContent).toBe("");
    expect(rute.replace).not.toHaveBeenCalled();
  });
});
