import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { CompanyProjectsPanel } from "./CompanyProjectsPanel";

vi.mock("@/api/companies", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/companies")>();
  return {
    ...original,
    createCompanyProject: vi.fn(),
    deleteCompanyProject: vi.fn(),
    updateCompanyProject: vi.fn(),
  };
});

describe("CompanyProjectsPanel", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("allows project creation before the company roster has participants", () => {
    render(
      <CompanyProjectsPanel
        companyId="company-1"
        initialProjects={[]}
        assignments={[]}
        participantCount={0}
      />,
    );

    expect(screen.getByText(/Creează proiectul, apoi adaugă rosterul/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Adaugă proiect" }).hasAttribute("disabled")).toBe(false);
  });
});
