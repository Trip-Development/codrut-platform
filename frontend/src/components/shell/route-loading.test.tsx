import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  CompanyDetailSkeleton,
  LoadingStatus,
  ParticipantRouteLoading,
  ProjectDetailSkeleton,
  TabBarSkeleton,
  TrainerRouteLoading,
} from "./route-loading";
import { clearAppShellIdentityCache } from "./app-shell";

afterEach(() => {
  cleanup();
  clearAppShellIdentityCache();
});

describe("route loading", () => {
  it("announces workspace preparation as a busy status", () => {
    render(<LoadingStatus label="Pregătim companiile" />);

    const status = screen.getByRole("status");

    expect(status.getAttribute("aria-busy")).toBe("true");
    expect(status.textContent).toContain("Pregătim companiile");
    expect(status.textContent).toContain("Sincronizare");
  });

  it.each(["dashboard", "table", "cards", "editor", "settings"] as const)(
    "renders the trainer %s loading workspace with a derived label",
    (kind) => {
      render(<TrainerRouteLoading title="Proiecte" activeHref="/trainer/projects" kind={kind} />);

      expect(screen.getByRole("status").textContent).toContain("Pregătim proiecte");
      expect(screen.getByRole("heading", { name: "Proiecte" })).toBeTruthy();
      expect(screen.getByRole("button", { name: "Se încarcă identitatea contului" })).toBeTruthy();
      expect(document.querySelector("[data-profile-avatar]")).toBeNull();
    },
  );

  it.each(["home", "list", "results", "account"] as const)(
    "renders the participant %s loading workspace",
    (kind) => {
      render(
        <ParticipantRouteLoading
          title="Rezultate"
          activeHref="/participant/results"
          kind={kind}
          loadingLabel="Sincronizăm rezultatele"
        />,
      );

      expect(screen.getByRole("status").textContent).toContain("Sincronizăm rezultatele");
      expect(screen.getByRole("heading", { name: "Rezultate" })).toBeTruthy();
      expect(screen.getByRole("button", { name: "Se încarcă identitatea contului" })).toBeTruthy();
      expect(document.querySelector("[data-profile-avatar]")).toBeNull();
    },
  );

  it("nu arata ecranele de coaching cat timp nu se stie tipul proiectului", () => {
    // Ecranul „Pregatim spatiul participant" apare inaintea datelor. Pana la plicul
    // 33 punea cu mana meniul de coaching, iar omul de la training vedea
    // „Chestionare" si „Rezultate" la fiecare intrare.
    render(<ParticipantRouteLoading title="Acasă" activeHref="/participant" kind="home" />);

    expect(screen.queryByRole("link", { name: "Chestionare" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Rezultate" })).toBeNull();
    expect(screen.getAllByRole("link", { name: "Exersează (Cody)" }).length).toBeGreaterThan(0);
  });

  it("pastreaza meniul de coaching la un proiect care nu e de training", () => {
    render(
      <ParticipantRouteLoading
        title="Rezultate"
        activeHref="/participant/results"
        kind="results"
        projectType="coaching_echipa"
      />,
    );

    expect(screen.getAllByRole("link", { name: "Chestionare" }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("link", { name: "Rezultate" }).length).toBeGreaterThan(0);
  });

  it("renders reusable company, project, and tab skeleton frames", () => {
    const { container, rerender } = render(<TabBarSkeleton count={3} />);
    expect(screen.getByRole("navigation", { name: "Pregătim navigarea" }).children[0].children).toHaveLength(3);

    rerender(<CompanyDetailSkeleton />);
    expect(container.querySelectorAll("section")).toHaveLength(2);

    rerender(<ProjectDetailSkeleton />);
    expect(container.querySelectorAll("section").length).toBeGreaterThanOrEqual(2);

    rerender(<TabBarSkeleton />);
    expect(screen.getByRole("navigation", { name: "Pregătim navigarea" }).children[0].children).toHaveLength(5);
  });
});
