import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { deleteCompanyProject, updateCompanyProject } from "@/api/companies";
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
    const confirmSpy = vi.spyOn(window, "confirm");
    let finishDelete: () => void = () => undefined;
    vi.mocked(deleteCompanyProject).mockReturnValueOnce(new Promise((resolve) => {
      finishDelete = () => resolve(undefined);
    }));

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

    expect(screen.getByLabelText("Status").getAttribute("data-slot")).toBe("select");
    expect(screen.getByLabelText("Notițe").getAttribute("data-slot")).toBe("textarea");

    const deleteButton = screen.getByRole("button", { name: "Șterge proiectul" }) as HTMLButtonElement;
    expect(deleteButton.disabled).toBe(true);

    fireEvent.change(screen.getByPlaceholderText("Leadership Septembrie"), {
      target: { value: "Leadership Septembrie" },
    });
    const deleteForm = deleteButton.closest("form");
    expect(deleteForm).not.toBeNull();

    fireEvent.submit(deleteForm!);
    fireEvent.submit(deleteForm!);

    expect(await screen.findAllByText("Ștergem proiectul")).toHaveLength(2);
    expect(deleteCompanyProject).toHaveBeenCalledTimes(1);
    expect(screen.getByLabelText("Scrie numele proiectului pentru confirmare")).toHaveProperty("disabled", true);
    expect(screen.getByRole("button", { name: "Salvează setările" })).toHaveProperty("disabled", true);

    await act(async () => {
      finishDelete();
    });

    await waitFor(() => expect(deleteCompanyProject).toHaveBeenCalledWith("company-1", "project-1"));
    expect(confirmSpy).not.toHaveBeenCalled();
    expect(routerPush).toHaveBeenCalledWith("/trainer/projects");
    expect(routerRefresh).toHaveBeenCalled();
  });

  it("formats project dates in the app timezone before hydration", () => {
    render(
      <ProjectSettingsForm
        project={{
          id: "project-1",
          company_id: "company-1",
          name: "Leadership Septembrie",
          description: null,
          project_type: "team_coaching",
          status: "active",
          starts_at: "2026-07-31T21:00:00.000Z",
          due_at: "2026-07-31T21:00:00.000Z",
          form_opens_at: null,
          form_closes_at: null,
          created_at: "2026-06-11T09:00:00Z",
          updated_at: "2026-07-31T21:00:00.000Z",
        }}
      />,
    );

    expect(screen.getAllByText("01 aug. 2026").length).toBeGreaterThanOrEqual(2);
    expect((screen.getByLabelText("Final proiect") as HTMLInputElement).value).toBe("2026-08-01");
  });

  it("shows a visible in-progress state while saving settings", async () => {
    let finishSave: () => void = () => undefined;
    vi.mocked(updateCompanyProject).mockReturnValueOnce(new Promise((resolve) => {
      finishSave = () => resolve({
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
      });
    }));

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

    const saveButton = screen.getByRole("button", { name: "Salvează setările" });
    const saveForm = saveButton.closest("form");
    expect(saveForm).not.toBeNull();

    fireEvent.submit(saveForm!);
    fireEvent.submit(saveForm!);

    expect(await screen.findByText("Salvăm setările proiectului")).toBeTruthy();
    expect(updateCompanyProject).toHaveBeenCalledTimes(1);
    expect(screen.getByText("în lucru")).toBeTruthy();
    expect(screen.getByLabelText("Nume proiect")).toHaveProperty("disabled", true);
    expect(screen.getByLabelText("Status")).toHaveProperty("disabled", true);
    expect(screen.getByLabelText("Notițe")).toHaveProperty("disabled", true);
    expect(screen.getByLabelText("Scrie numele proiectului pentru confirmare")).toHaveProperty("disabled", true);
    expect(screen.getByRole("button", { name: "Șterge proiectul" })).toHaveProperty("disabled", true);

    await act(async () => {
      finishSave();
    });
    await waitFor(() => expect(screen.queryByText("Salvăm setările proiectului")).toBeNull());
  });
});
