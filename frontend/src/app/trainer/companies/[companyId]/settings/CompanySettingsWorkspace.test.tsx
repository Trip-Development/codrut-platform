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

    expect(screen.queryByRole("button", { name: "Șterge compania" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Configurează ștergerea" }));

    const deleteButton = screen.getByRole("button", { name: "Șterge compania" }) as HTMLButtonElement;
    expect(deleteButton.disabled).toBe(true);

    fireEvent.change(screen.getByPlaceholderText("Michelin"), { target: { value: "Michelin" } });
    fireEvent.click(deleteButton);

    await waitFor(() => expect(deleteCompany).toHaveBeenCalledWith("company-1"));
    expect(routerPush).toHaveBeenCalledWith("/trainer/companies");
    expect(routerRefresh).toHaveBeenCalled();
  });
});
