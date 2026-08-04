import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { createCompany, getCompanyList } from "@/api/companies";
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

    expect(screen.getAllByText("Michelin").length).toBeGreaterThan(0);
    expect(screen.queryByText("Local-only client")).toBeNull();
    expect(getCompanyList).not.toHaveBeenCalled();
    expect(screen.getByRole("complementary", { name: "Contextul fluxului" }).textContent).toContain(
      "1 companie în listă",
    );
    expect(screen.getByRole("button", { name: "Companie nouă" })).toBeTruthy();
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
    expect(screen.getByRole("link", { name: "Setări" }).getAttribute("href")).toBe(
      "/trainer/companies/backend-company/settings",
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

    fireEvent.change(screen.getByPlaceholderText("Caută după denumire, cod, status sau etapă"), {
      target: { value: "Radacini" },
    });

    expect(screen.getByRole("link", { name: /Rădăcini Coaching/i })).toBeTruthy();
  });

  it("matches company search by displayed company code", async () => {
    render(
      <CompaniesWorkspace
        initialCompanies={[
          {
            id: "atlas-mobility",
            name: "Atlas Mobility",
            participantCount: 0,
            projectCount: 0,
            assignmentCount: 0,
            completedCount: 0,
            stage: "setup",
          },
        ]}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("Caută după denumire, cod, status sau etapă"), {
      target: { value: "ID ATLASMO" },
    });

    expect(screen.getByRole("link", { name: /Atlas Mobility/i })).toBeTruthy();
  });

  it("filters operational status and exposes selection actions only after selection", async () => {
    render(
      <CompaniesWorkspace
        initialCompanies={[
          {
            id: "attention-company",
            name: "Atlas Mobility",
            participantCount: 8,
            projectCount: 1,
            assignmentCount: 8,
            completedCount: 4,
            stage: "completion",
          },
          {
            id: "active-company",
            name: "Clinica Meridian",
            participantCount: 3,
            projectCount: 1,
            assignmentCount: 3,
            completedCount: 3,
            stage: "reporting",
          },
        ]}
      />,
    );

    expect(screen.queryByRole("button", { name: "Exportă selecția" })).toBeNull();
    fireEvent.click(screen.getByRole("combobox", { name: "Status" }));
    fireEvent.click(await screen.findByRole("option", { name: "Necesită acțiune" }));
    expect(screen.getByRole("link", { name: /Atlas Mobility/i })).toBeTruthy();
    expect(screen.queryByRole("link", { name: /Clinica Meridian/i })).toBeNull();

    fireEvent.click(screen.getByLabelText("Selectează Atlas Mobility"));
    expect(screen.getByRole("button", { name: "Exportă selecția" })).toBeTruthy();
    expect(screen.getByText("1 selectată")).toBeTruthy();
  });

  it("shows a full pending surface while creating the first company", async () => {
    let resolveCreate!: (value: Awaited<ReturnType<typeof createCompany>>) => void;
    vi.mocked(createCompany).mockImplementation(
      () => new Promise((resolve) => {
        resolveCreate = resolve;
      }),
    );

    render(<CompaniesWorkspace initialCompanies={[]} />);

    fireEvent.click(screen.getAllByRole("button", { name: "Companie nouă" })[0]);
    const companyNameInput = await screen.findByLabelText("Nume companie");
    fireEvent.change(companyNameInput, {
      target: { value: "Compania nouă" },
    });
    const createForm = companyNameInput.closest("form");
    expect(createForm).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Salvează compania" }));
    fireEvent.submit(createForm!);

    expect(await screen.findByText("Creăm spațiul companiei")).toBeTruthy();
    expect(companyNameInput.hasAttribute("disabled")).toBe(true);
    expect(createCompany).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveCreate({ id: "compania-noua", name: "Compania nouă" });
    });

    expect(await screen.findByText("Compania a fost creată și salvată.")).toBeTruthy();
  });

  it("uses an accessible pagination marker instead of raw ellipsis copy", async () => {
    render(
      <CompaniesWorkspace
        initialCompanies={Array.from({ length: 61 }, (_, index) => ({
          id: `company-${index + 1}`,
          name: `Compania ${String(index + 1).padStart(2, "0")}`,
          participantCount: 0,
          projectCount: 0,
          assignmentCount: 0,
          completedCount: 0,
          stage: "setup",
        }))}
      />,
    );

    expect(screen.getByLabelText("Pagini intermediare")).toBeTruthy();
    expect(screen.queryByText("...")).toBeNull();
  });
});
