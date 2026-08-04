import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { restoreCompanyProject, type CompanyProject } from "@/api/companies";

import { ProjectsWorkspace } from "./ProjectsWorkspace";

const routerRefresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    refresh: routerRefresh,
  }),
  usePathname: () => "/trainer/projects",
  useSearchParams: () => new URLSearchParams(window.location.search),
}));

vi.mock("@/api/companies", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/companies")>();
  return {
    ...original,
    restoreCompanyProject: vi.fn().mockResolvedValue(undefined),
  };
});

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
  beforeEach(() => {
    window.history.replaceState(null, "", "/trainer/projects");
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
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

  it("collapses mobile filters behind one trigger and reports active state", () => {
    render(
      <ProjectsWorkspace
        projects={projects}
        initialFilters={{}}
        companies={[["company-1", "Atlas Mobility"]]}
        projectTypes={["leadership"]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Filtre" }));
    const dialog = screen.getByRole("dialog", { name: "Filtre" });
    fireEvent.click(within(dialog).getByRole("combobox", { name: "Status" }));
    fireEvent.click(screen.getByRole("option", { name: "Active" }));
    fireEvent.click(screen.getByRole("button", { name: "Gata" }));

    expect(screen.getByRole("button", { name: "Filtre, 1 active" })).toBeTruthy();
    expect(screen.getByText("Leadership operațional Q3")).toBeTruthy();
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

    fireEvent.change(screen.getByPlaceholderText("Caută proiecte"), {
      target: { value: "operational" },
    });

    expect(screen.getByText("Leadership operațional Q3")).toBeTruthy();
    expect(screen.queryByText("Cohortă retail arhivată")).toBeNull();
  });

  it("restores an archived project from the archive list", async () => {
    render(
      <ProjectsWorkspace
        projects={projects}
        initialFilters={{ status: "active" }}
        companies={[
          ["company-1", "Atlas Mobility"],
          ["company-2", "Nova Retail Group"],
        ]}
        projectTypes={["leadership", "intake"]}
        archivedMode
      />,
    );

    expect(screen.queryByRole("combobox", { name: "Status" })).toBeNull();
    expect(screen.queryByText("Leadership operațional Q3")).toBeNull();
    expect(screen.getByText("Cohortă retail arhivată")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Restaurează" }));

    await waitFor(() => {
      expect(restoreCompanyProject).toHaveBeenCalledWith("company-2", "project-archived");
    });
    expect(routerRefresh).toHaveBeenCalledTimes(1);
  });

  it("keeps the archived project visible and reports a restore failure", async () => {
    vi.mocked(restoreCompanyProject).mockRejectedValueOnce(new Error("Restaurarea a eșuat."));

    render(
      <ProjectsWorkspace
        projects={projects}
        initialFilters={{}}
        companies={[
          ["company-1", "Atlas Mobility"],
          ["company-2", "Nova Retail Group"],
        ]}
        projectTypes={["leadership", "intake"]}
        archivedMode
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Restaurează" }));

    expect(await screen.findByText("Restaurarea a eșuat.")).toBeTruthy();
    expect(screen.getByText("Cohortă retail arhivată")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Restaurează" })).toHaveProperty("disabled", false);
    expect(routerRefresh).not.toHaveBeenCalled();
  });

  it("distinguishes empty current and archived project views", () => {
    const { rerender } = render(
      <ProjectsWorkspace
        projects={[]}
        initialFilters={{}}
        companies={[]}
        projectTypes={[]}
      />,
    );

    expect(screen.getByText("Nu există proiecte încă")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Deschide companii" })).toBeTruthy();

    rerender(
      <ProjectsWorkspace
        projects={[]}
        initialFilters={{}}
        companies={[]}
        projectTypes={[]}
        archivedMode
      />,
    );

    expect(screen.getByText("Arhiva este goală")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Vezi proiectele curente" })).toBeTruthy();
  });

  it("shows the correct next action for draft and completed projects", () => {
    render(
      <ProjectsWorkspace
        projects={[
          {
            ...projects[0],
            id: "project-draft",
            name: "Proiect în pregătire",
            status: "draft",
          },
          {
            ...projects[0],
            id: "project-completed",
            name: "Proiect finalizat",
            status: "completed",
          },
        ]}
        initialFilters={{}}
        companies={[["company-1", "Atlas Mobility"]]}
        projectTypes={["leadership"]}
      />,
    );

    expect(screen.getByRole("link", { name: /Continuă configurarea/i })).toBeTruthy();
    expect(screen.getByRole("link", { name: /Deschide raportul/i })).toBeTruthy();
  });

  it("resets an archive search without leaving the archive view", async () => {
    window.history.replaceState(null, "", "/trainer/projects?view=archived&q=inexistent");

    render(
      <ProjectsWorkspace
        projects={projects}
        initialFilters={{ q: "inexistent" }}
        companies={[
          ["company-1", "Atlas Mobility"],
          ["company-2", "Nova Retail Group"],
        ]}
        projectTypes={["leadership", "intake"]}
        archivedMode
      />,
    );

    expect(await screen.findByText("Niciun proiect găsit")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Resetează filtrele" }));

    expect(await screen.findByText("Cohortă retail arhivată")).toBeTruthy();
    expect(window.location.search).toBe("?view=archived");
  });
});
