import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createCompanyProject } from "@/api/companies";
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
      />,
    );

    expect(screen.getByRole("heading", { name: "Proiecte" })).toBeTruthy();
    expect(screen.getAllByRole("button", { name: "Proiect nou" }).some((button) => !button.hasAttribute("disabled"))).toBe(true);
  });

  it("renders company project rows as links to the project workspace", () => {
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
      />,
    );

    expect(screen.getByRole("link", { name: /Leadership Q3/ }).getAttribute("href")).toBe(
      "/trainer/projects/project-1",
    );
    expect(screen.getByRole("columnheader", { name: "Status" })).toBeTruthy();
    expect(screen.getByRole("columnheader", { name: "Calendar" })).toBeTruthy();
    expect(screen.getByRole("combobox", { name: "Status proiecte" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Șterge proiectul" })).toBeNull();
  });

  it("shows project-scoped completion and an operational next step", () => {
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
        assignments={[
          {
            id: "assignment-1",
            company_id: "company-1",
            project_id: "project-1",
            respondent_profile_id: "participant-1",
            questionnaire_key: "boss_360",
            target_type: "self",
            target_person_id: null,
            target_team_id: null,
            status: "started",
            submitted_at: null,
            scored_at: null,
          },
        ]}
      />,
    );

    expect(screen.getByText("0/1")).toBeTruthy();
    expect(screen.getByRole("link", { name: /Urmărește progresul/i })).toBeTruthy();
  });

  it("searches the status options before applying the company project filter", () => {
    render(
      <CompanyProjectsPanel
        companyId="company-1"
        initialProjects={[
          {
            id: "project-active",
            company_id: "company-1",
            name: "Leadership activ",
            description: null,
            project_type: "leadership_program",
            status: "active",
            starts_at: null,
            due_at: null,
            form_opens_at: null,
            form_closes_at: null,
            created_at: "2026-07-01T00:00:00.000Z",
            updated_at: "2026-07-01T00:00:00.000Z",
          },
          {
            id: "project-draft",
            company_id: "company-1",
            name: "Cohortă nouă",
            description: null,
            project_type: "cohort_program",
            status: "draft",
            starts_at: null,
            due_at: null,
            form_opens_at: null,
            form_closes_at: null,
            created_at: "2026-07-01T00:00:00.000Z",
            updated_at: "2026-07-01T00:00:00.000Z",
          },
        ]}
        assignments={[]}
      />,
    );

    fireEvent.click(screen.getByRole("combobox", { name: "Status proiecte" }));
    const optionSearch = screen.getByRole("searchbox", { name: "Caută în status proiecte" });
    expect(document.activeElement).toBe(optionSearch);
    fireEvent.change(optionSearch, { target: { value: "pregatire" } });
    fireEvent.click(screen.getByRole("option", { name: "În pregătire · 1" }));

    expect(screen.getByText("Cohortă nouă")).toBeTruthy();
    expect(screen.queryByText("Leadership activ")).toBeNull();
  });

  it("shows a full pending surface while creating a project", async () => {
    let resolveCreate!: (value: Awaited<ReturnType<typeof createCompanyProject>>) => void;
    vi.mocked(createCompanyProject).mockImplementation(
      () => new Promise((resolve) => {
        resolveCreate = resolve;
      }),
    );

    render(
      <CompanyProjectsPanel
        companyId="company-1"
        initialProjects={[]}
        assignments={[]}
      />,
    );

    const openButton = screen
      .getAllByRole("button", { name: "Proiect nou" })
      .find((button) => !button.hasAttribute("disabled"));
    expect(openButton).toBeTruthy();
    fireEvent.click(openButton!);
    expect(screen.getByLabelText("Tip proiect").getAttribute("data-slot")).toBe("select");
    expect(screen.getByLabelText("Notițe interne").getAttribute("data-slot")).toBe("textarea");
    fireEvent.change(screen.getByPlaceholderText("Ex: Leadership Q3 2026"), {
      target: { value: "Leadership Q4" },
    });
    const createForm = screen.getByPlaceholderText("Ex: Leadership Q3 2026").closest("form");
    expect(createForm).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Salvează proiectul" }));
    fireEvent.submit(createForm!);

    expect((await screen.findAllByText("Creăm proiectul")).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByPlaceholderText("Ex: Leadership Q3 2026").hasAttribute("disabled")).toBe(true);
    expect(createCompanyProject).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveCreate({
        id: "project-2",
        company_id: "company-1",
        company_name: "Compania Pilot",
        name: "Leadership Q4",
        description: null,
        project_type: "team_coaching",
        status: "draft",
        starts_at: null,
        due_at: null,
        form_opens_at: null,
        form_closes_at: null,
        created_at: "2026-07-14T00:00:00.000Z",
        updated_at: "2026-07-14T00:00:00.000Z",
      });
    });

    expect(await screen.findByText("Proiectul a fost salvat.")).toBeTruthy();
  });
});
