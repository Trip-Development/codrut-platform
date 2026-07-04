import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getCompanyList } from "@/api/companies";
import { CompaniesWorkspace } from "./CompaniesWorkspace";

vi.mock("@/api/companies", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/companies")>();
  return {
    ...original,
    createCompany: vi.fn(),
    getCompanyList: vi.fn().mockResolvedValue([]),
  };
});

describe("CompaniesWorkspace", () => {
  afterEach(() => {
    cleanup();
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  it("renders backend companies without refetching or resurrecting stale local companies", async () => {
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
            projectCount: 0,
            assignmentCount: 0,
            completedCount: 0,
            stage: "setup",
          },
        ]}
      />,
    );

    expect(screen.getByText("Michelin")).toBeTruthy();
    expect(screen.queryByText("Local-only client")).toBeNull();
    expect(getCompanyList).not.toHaveBeenCalled();
  });

  it("keeps destructive company actions out of the company grid", async () => {
    render(
      <CompaniesWorkspace
        initialCompanies={[
          {
            id: "backend-company",
            name: "Michelin",
            participantCount: 0,
            projectCount: 0,
            assignmentCount: 0,
            completedCount: 0,
            stage: "setup",
          },
        ]}
      />,
    );

    expect(screen.queryByRole("button", { name: /Șterge compania/i })).toBeNull();
    expect(screen.queryByText("În pregătire")).toBeNull();
    expect(screen.getByRole("link", { name: /Michelin/i }).getAttribute("href")).toBe(
      "/trainer/companies/backend-company",
    );
  });

  it("matches company search without requiring Romanian diacritics", async () => {
    render(
      <CompaniesWorkspace
        initialCompanies={[
          {
            id: "roots-company",
            name: "Rădăcini Coaching",
            participantCount: 0,
            projectCount: 0,
            assignmentCount: 0,
            completedCount: 0,
            stage: "setup",
          },
        ]}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("Caută companie..."), { target: { value: "Radacini" } });

    expect(screen.getByRole("link", { name: /Rădăcini Coaching/i })).toBeTruthy();
  });
});
