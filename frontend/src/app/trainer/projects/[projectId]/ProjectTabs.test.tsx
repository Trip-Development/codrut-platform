import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectTabs } from "./ProjectTabs";

const navigationState = vi.hoisted(() => ({
  pathname: "/trainer/projects/project-1/participants",
  search: "",
}));

vi.mock("next/navigation", () => ({
  usePathname: () => navigationState.pathname,
  useSearchParams: () => new URLSearchParams(navigationState.search),
}));

describe("ProjectTabs", () => {
  afterEach(() => {
    cleanup();
    navigationState.pathname = "/trainer/projects/project-1/participants";
    navigationState.search = "";
  });

  it("derives the selected tab from the live client pathname", () => {
    render(<ProjectTabs basePath="/trainer/projects/project-1" />);

    expect(screen.getByRole("link", { name: "Participanți" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Sumar" }).getAttribute("aria-current")).toBeNull();
  });

  it("keeps the participant tab selected on a nested participant route", () => {
    navigationState.pathname = "/trainer/projects/project-1/participants/participant-1";
    render(<ProjectTabs basePath="/trainer/projects/project-1" />);

    expect(screen.getByRole("link", { name: "Participanți" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Sumar" }).getAttribute("aria-current")).toBeNull();
  });

  it("removes the duplicate project teams presentation route", () => {
    navigationState.pathname = "/trainer/projects/project-1/org-chart";
    render(<ProjectTabs basePath="/trainer/projects/project-1" />);

    expect(screen.queryByRole("link", { name: "Echipe" })).toBeNull();
    expect(screen.getByRole("link", { name: "Organigramă" }).getAttribute("aria-current")).toBe("page");
  });

  it("preserves the selected assessment cycle across project tools", () => {
    navigationState.search = "cycle=cycle-2";
    render(<ProjectTabs basePath="/trainer/projects/project-1" />);

    expect(screen.getByRole("link", { name: "Rezultate" }).getAttribute("href")).toBe(
      "/trainer/projects/project-1/reports?cycle=cycle-2",
    );
  });

  it("preserves comparison parameters only for the results workspace", () => {
    navigationState.search = "cycle=cycle-2&baseline=cycle-1&compare=dimensions";
    render(<ProjectTabs basePath="/trainer/projects/project-1" />);

    expect(screen.getByRole("link", { name: "Rezultate" }).getAttribute("href")).toBe(
      "/trainer/projects/project-1/reports?cycle=cycle-2&baseline=cycle-1&compare=dimensions",
    );
    expect(screen.getByRole("link", { name: "Participanți" }).getAttribute("href")).toBe(
      "/trainer/projects/project-1/participants?cycle=cycle-2",
    );
  });
});
