import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ProjectTabs } from "./ProjectTabs";

const navigationState = vi.hoisted(() => ({
  pathname: "/trainer/projects/project-1/participants",
}));

vi.mock("next/navigation", () => ({
  usePathname: () => navigationState.pathname,
}));

describe("ProjectTabs", () => {
  afterEach(() => {
    cleanup();
    navigationState.pathname = "/trainer/projects/project-1/participants";
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

  it("keeps the preserved project teams workspace discoverable", () => {
    navigationState.pathname = "/trainer/projects/project-1/teams";
    render(<ProjectTabs basePath="/trainer/projects/project-1" />);

    expect(screen.getByRole("link", { name: "Echipe" }).getAttribute("aria-current")).toBe("page");
  });

  it("places teams immediately after the organization chart", () => {
    render(<ProjectTabs basePath="/trainer/projects/project-1" />);

    const labels = screen.getAllByRole("link").map((link) => link.textContent);
    expect(labels.indexOf("Echipe")).toBe(labels.indexOf("Organigramă") + 1);
  });
});
