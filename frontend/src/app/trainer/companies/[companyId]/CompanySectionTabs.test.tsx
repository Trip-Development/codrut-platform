import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CompanySectionTabs } from "./CompanySectionTabs";

const navigationState = vi.hoisted(() => ({
  pathname: "/trainer/companies/company-1/participants",
}));

vi.mock("next/navigation", () => ({
  usePathname: () => navigationState.pathname,
}));

describe("CompanySectionTabs", () => {
  afterEach(() => cleanup());

  it("marks the company participant route as the selected view", () => {
    render(<CompanySectionTabs basePath="/trainer/companies/company-1" />);

    expect(screen.getByRole("link", { name: "Participanți" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Proiecte" }).getAttribute("aria-current")).toBeNull();
    expect(screen.getByRole("link", { name: "Echipe" }).getAttribute("href")).toBe(
      "/trainer/companies/company-1/teams",
    );
    expect(screen.getByRole("link", { name: "Invitații" }).getAttribute("href")).toBe(
      "/trainer/companies/company-1/invitations",
    );
  });
});
