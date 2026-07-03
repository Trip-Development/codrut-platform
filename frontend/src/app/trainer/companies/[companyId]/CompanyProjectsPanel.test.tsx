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

  it("renders company project cards as the same clickable cards used in projects", () => {
    render(
      <CompanyProjectsPanel
        companyId="company-1"
        initialProjects={[
          {
            id: "project-1",
            company_id: "company-1",
            company_name: "Compania Pilot",
            name: "Leadership Q3",
            description: null,
            project_type: "team_coaching",
            status: "active",
            starts_at: "2026-07-01T00:00:00.000Z",
            due_at: "2026-07-31T00:00:00.000Z",
            form_opens_at: null,
            form_closes_at: null,
            created_at: "2026-07-01T00:00:00.000Z",
            updated_at: "2026-07-01T00:00:00.000Z",
          },
        ]}
        assignments={[]}
        participantCount={0}
      />,
    );

    expect(screen.getByRole("link", { name: /Leadership Q3/ }).getAttribute("href")).toBe(
      "/trainer/projects/project-1",
    );
    expect(screen.queryByRole("link", { name: "Participanți" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Invitații" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Rezultate" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Șterge proiectul" })).toBeNull();
  });
});
