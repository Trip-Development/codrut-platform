import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { deleteCompany, getCompanyList } from "@/api/companies";
import { CompaniesWorkspace } from "./CompaniesWorkspace";

vi.mock("@/api/companies", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/companies")>();
  return {
    ...original,
    createCompany: vi.fn(),
    deleteCompany: vi.fn().mockResolvedValue(undefined),
    getCompanyList: vi.fn().mockResolvedValue([]),
  };
});

describe("CompaniesWorkspace", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  it("renders backend companies without resurrecting stale local companies", async () => {
    window.localStorage.setItem(
      "codrut_local_companies",
      JSON.stringify([{ id: "local-company", name: "Local-only client" }]),
    );

    render(
      <CompaniesWorkspace
        initialCompanies={[
          {
            id: "backend-company",
            name: "Michelin",
            participantCount: 0,
            assignmentCount: 0,
            completedCount: 0,
            stage: "setup",
          },
        ]}
      />,
    );

    await waitFor(() => expect(getCompanyList).toHaveBeenCalled());

    expect(screen.getByText("Michelin")).toBeTruthy();
    expect(screen.queryByText("Local-only client")).toBeNull();
  });

  it("deletes companies only after backend confirmation", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

    render(
      <CompaniesWorkspace
        initialCompanies={[
          {
            id: "backend-company",
            name: "Michelin",
            participantCount: 0,
            assignmentCount: 0,
            completedCount: 0,
            stage: "setup",
          },
        ]}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Șterge compania Michelin" }));

    await waitFor(() => expect(deleteCompany).toHaveBeenCalledWith("backend-company"));
    await waitFor(() => expect(screen.queryByText("Michelin")).toBeNull());
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining("Michelin"));
    confirmSpy.mockRestore();
  });
});
