import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { deleteCompany } from "@/api/companies";
import { CompanySettingsWorkspace } from "./CompanySettingsWorkspace";

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
    deleteCompany: vi.fn().mockResolvedValue(undefined),
  };
});

describe("CompanySettingsWorkspace", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("requires typed confirmation before deleting a company", async () => {
    render(
      <CompanySettingsWorkspace
        company={{
          id: "company-1",
          name: "Michelin",
          stats: {
            totalParticipants: 3,
            totalAssignments: 6,
            completedAssignments: 2,
            completionRate: 33,
          },
        }}
      />,
    );

    expect(screen.queryByRole("button", { name: "Șterge definitiv" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Șterge compania" }));

    const deleteButton = screen.getByRole("button", { name: "Șterge definitiv" }) as HTMLButtonElement;
    expect(deleteButton.disabled).toBe(true);

    fireEvent.change(screen.getByPlaceholderText("Michelin"), { target: { value: "Michelin" } });
    const deleteForm = deleteButton.closest("form");
    expect(deleteForm).not.toBeNull();
    fireEvent.submit(deleteForm!);
    fireEvent.submit(deleteForm!);

    await waitFor(() => expect(deleteCompany).toHaveBeenCalledWith("company-1"));
    expect(deleteCompany).toHaveBeenCalledTimes(1);
    expect(routerPush).toHaveBeenCalledWith("/trainer/companies");
    expect(routerRefresh).toHaveBeenCalled();
  });

  it("shows progress while deleting a company", async () => {
    let finishDelete: () => void = () => undefined;
    vi.mocked(deleteCompany).mockReturnValueOnce(new Promise((resolve) => {
      finishDelete = () => resolve(undefined);
    }));

    render(
      <CompanySettingsWorkspace
        company={{
          id: "company-1",
          name: "Michelin",
          stats: {
            totalParticipants: 3,
            totalAssignments: 6,
            completedAssignments: 2,
            completionRate: 33,
          },
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Șterge compania" }));
    fireEvent.change(screen.getByPlaceholderText("Michelin"), { target: { value: "Michelin" } });
    const deleteButton = screen.getByRole("button", { name: "Șterge definitiv" });
    const deleteForm = deleteButton.closest("form");
    expect(deleteForm).not.toBeNull();
    fireEvent.submit(deleteForm!);
    fireEvent.submit(deleteForm!);

    expect((await screen.findAllByText("Ștergem compania")).length).toBeGreaterThanOrEqual(1);
    expect(deleteCompany).toHaveBeenCalledTimes(1);
    expect(screen.getByText("în lucru")).toBeTruthy();
    expect(screen.getByPlaceholderText("Michelin").hasAttribute("disabled")).toBe(true);
    expect((screen.getByRole("button", { name: "Anulează" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Ștergem compania" }) as HTMLButtonElement).disabled).toBe(true);

    finishDelete();
    await waitFor(() => expect(routerPush).toHaveBeenCalledWith("/trainer/companies"));
  });
});
