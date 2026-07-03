import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { deleteCompanyProject } from "@/api/companies";
import { ProjectSettingsForm } from "./ProjectSettingsForm";

const routerPush = vi.fn();
const routerRefresh = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    push: routerPush,
    refresh: routerRefresh,
  }),
}));

vi.mock("@/api/companies", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/companies")>();
  return {
    ...original,
    deleteCompanyProject: vi.fn().mockResolvedValue(undefined),
    updateCompanyProject: vi.fn().mockResolvedValue(undefined),
  };
});

describe("ProjectSettingsForm", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.clearAllMocks();
  });

  it("requires typed confirmation before deleting a project", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <ProjectSettingsForm
        project={{
          id: "project-1",
          company_id: "company-1",
          name: "Leadership Septembrie",
          description: null,
          project_type: "team_coaching",
          status: "active",
          starts_at: null,
          due_at: null,
          form_opens_at: null,
          form_closes_at: null,
          created_at: "2026-06-11T09:00:00Z",
          updated_at: "2026-06-11T09:00:00Z",
        }}
      />,
    );

    const deleteButton = screen.getByRole("button", { name: "Șterge proiectul" }) as HTMLButtonElement;
    expect(deleteButton.disabled).toBe(true);

    fireEvent.change(screen.getByPlaceholderText("Leadership Septembrie"), {
      target: { value: "Leadership Septembrie" },
    });
    fireEvent.click(deleteButton);

    await waitFor(() => expect(deleteCompanyProject).toHaveBeenCalledWith("company-1", "project-1"));
    expect(confirmSpy).toHaveBeenCalled();
    expect(routerPush).toHaveBeenCalledWith("/trainer/projects");
    expect(routerRefresh).toHaveBeenCalled();
  });
});
