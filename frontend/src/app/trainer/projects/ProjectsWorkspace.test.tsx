import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { CompanyProject } from "@/api/companies";

import { ProjectsWorkspace } from "./ProjectsWorkspace";

const projects: CompanyProject[] = [
  {
    id: "project-active",
    company_id: "company-1",
    company_name: "Atlas Mobility",
    name: "Leadership operațional Q3",
    description: "Program pentru echipa de management.",
    project_type: "leadership",
    status: "active",
    starts_at: "2026-07-01T00:00:00.000Z",
    due_at: "2026-07-31T00:00:00.000Z",
    form_opens_at: null,
    form_closes_at: null,
    created_at: "2026-06-01T00:00:00.000Z",
    updated_at: "2026-07-02T00:00:00.000Z",
  },
  {
    id: "project-archived",
    company_id: "company-2",
    company_name: "Nova Retail Group",
    name: "Cohortă retail arhivată",
    description: null,
    project_type: "intake",
    status: "archived",
    starts_at: null,
    due_at: null,
    form_opens_at: null,
    form_closes_at: null,
    created_at: "2026-06-01T00:00:00.000Z",
    updated_at: "2026-06-02T00:00:00.000Z",
  },
];

describe("ProjectsWorkspace", () => {
  afterEach(() => {
    cleanup();
  });

  it("uses searchable project filters and keeps project filtering local", () => {
    render(
      <ProjectsWorkspace
        projects={projects}
        initialFilters={{}}
        companies={[
          ["company-1", "Atlas Mobility"],
          ["company-2", "Nova Retail Group"],
        ]}
        projectTypes={["leadership", "intake"]}
      />,
    );

    expect(screen.getByRole("combobox", { name: "Companie" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "Status" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "Tip proiect" })).toBeTruthy();

    fireEvent.click(screen.getByRole("combobox", { name: "Status" }));
    const optionSearch = screen.getByRole("searchbox", { name: "Caută în status" });
    expect(document.activeElement).toBe(optionSearch);
    fireEvent.change(optionSearch, { target: { value: "active" } });
    fireEvent.click(screen.getByRole("option", { name: "Active" }));

    expect(screen.getByText("Leadership operațional Q3")).toBeDefined();
    expect(screen.queryByText("Cohortă retail arhivată")).toBeNull();
  });

  it("keeps the operational next step in the project table and searches without diacritics", () => {
    render(
      <ProjectsWorkspace
        projects={projects}
        initialFilters={{}}
        companies={[
          ["company-1", "Atlas Mobility"],
          ["company-2", "Nova Retail Group"],
        ]}
        projectTypes={["leadership", "intake"]}
      />,
    );

    expect(screen.getByRole("columnheader", { name: "Următorul pas" })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Urmărește progresul/i })).toBeTruthy();

    fireEvent.change(screen.getByPlaceholderText("Caută proiect sau companie"), {
      target: { value: "operational" },
    });

    expect(screen.getByText("Leadership operațional Q3")).toBeTruthy();
    expect(screen.queryByText("Cohortă retail arhivată")).toBeNull();
  });
});
