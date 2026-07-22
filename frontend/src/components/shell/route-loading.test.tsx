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

afterEach(cleanup);

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
    },
  );

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
