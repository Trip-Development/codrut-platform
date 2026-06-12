import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { importCompanyRoster, sendParticipantInvitations } from "@/api/companies";
import { RosterImporter } from "./roster-importer";

const router = vi.hoisted(() => ({
  push: vi.fn(),
  refresh: vi.fn(),
}));
const workbookState = vi.hoisted(() => ({
  rows: [
    ["Name", "email", "Reports To", "Position", "Location", "Profil PCM"],
    ["Ana Pop", "ana@example.com", "", "Manager", "București", "PCM rebel"],
  ] as unknown[][],
  sheet: {} as Record<string, unknown>,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

vi.mock("xlsx", () => ({
  read: vi.fn(() => ({
    SheetNames: ["Roster"],
    Sheets: { Roster: workbookState.sheet },
  })),
  utils: {
    sheet_to_json: vi.fn(() => workbookState.rows),
    encode_cell: vi.fn(({ r, c }: { r: number; c: number }) => `${String.fromCharCode(65 + c)}${r + 1}`),
  },
}));

vi.mock("@/api/companies", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/companies")>();
  return {
    ...original,
    createCompany: vi.fn(),
    importCompanyRoster: vi.fn(),
    sendParticipantInvitations: vi.fn(),
  };
});

describe("RosterImporter", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    workbookState.rows = [
      ["Name", "email", "Reports To", "Position", "Location", "Profil PCM"],
      ["Ana Pop", "ana@example.com", "", "Manager", "București", "PCM rebel"],
    ];
    workbookState.sheet = {};
  });

  it("imports the roster first, then explicitly generates secure links for imported participants", async () => {
    vi.mocked(importCompanyRoster).mockResolvedValue({
      participants: [
        {
          id: "participant-1",
          full_name: "Ana Pop",
          email: "ana@example.com",
          reports_to_name: null,
          position: "Manager",
          location: "București",
          role_group: null,
          pcm_profile: "PCM rebel",
          user_id: null,
        },
      ],
      email_results: [],
      total_imported: 1,
      emails_sent: 0,
      emails_failed: 0,
    });
    vi.mocked(sendParticipantInvitations).mockResolvedValue({
      results: [
        {
          participant_id: "participant-1",
          full_name: "Ana Pop",
          email: "ana@example.com",
          delivery_mode: "secure_links",
          email_sent: false,
          error: null,
          invite_url: "https://app.example.com/invite/token",
        },
      ],
      total: 1,
      emails_sent: 0,
      emails_failed: 0,
      links_generated: 1,
    });

    const { container } = render(
      <RosterImporter
        companies={[{ id: "company-1", name: "Michelin" }]}
        defaultCompanyId="company-1"
        lockCompany
      />,
    );

    const fileInput = container.querySelector('input[type="file"]');
    expect(fileInput).not.toBeNull();
    fireEvent.change(fileInput as HTMLInputElement, {
      target: {
        files: [new File(["fake"], "roster.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" })],
      },
    });

    expect(await screen.findByText(/Am încărcat 1 rânduri/)).not.toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Salvează participanții" }));

    await waitFor(() => expect(importCompanyRoster).toHaveBeenCalledTimes(1));
    expect(importCompanyRoster).toHaveBeenCalledWith(
      "company-1",
      [
        {
          Name: "Ana Pop",
          "Reports To": "",
          Position: "Manager",
          Location: "București",
          email: "ana@example.com",
          "Profil PCM": "",
          "PCM Bază": "",
          "PCM Fază": "",
        },
      ],
    );

    expect(await screen.findByText("Participanți salvați. Alege cum le dai acces.")).not.toBeNull();
    expect(sendParticipantInvitations).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Generează linkuri securizate" }));

    await waitFor(() => expect(sendParticipantInvitations).toHaveBeenCalledTimes(1));
    expect(sendParticipantInvitations).toHaveBeenCalledWith("company-1", {
      participantIds: ["participant-1"],
      projectId: null,
      mode: "secure_links",
    });
    expect(await screen.findByText("1/1 linkuri securizate generate.")).not.toBeNull();
    expect(screen.getByText("Link securizat pregătit")).not.toBeNull();
  });

  it("blocks company workspace import until a destination project exists", async () => {
    const { container } = render(
      <RosterImporter
        companies={[{ id: "company-1", name: "Michelin" }]}
        defaultCompanyId="company-1"
        requireProject
        lockCompany
      />,
    );

    fireEvent.change(container.querySelector('input[type="file"]') as HTMLInputElement, {
      target: {
        files: [new File(["fake"], "roster.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" })],
      },
    });

    expect(await screen.findByText("Am încărcat 1 rânduri. Vă rugăm să validați maparea coloanelor și corectitudinea datelor.")).not.toBeNull();
    expect(await screen.findByText(/Creează un proiect înainte de import/)).not.toBeNull();
    const importButton = screen.getByRole("button", { name: "Salvează participanții" }) as HTMLButtonElement;
    expect(importButton.disabled).toBe(true);
    fireEvent.click(importButton);
    expect(importCompanyRoster).not.toHaveBeenCalled();
  });

  it("warns before submit when an uploaded email already exists in the company", async () => {
    const { container } = render(
      <RosterImporter
        companies={[{ id: "company-1", name: "Michelin" }]}
        defaultCompanyId="company-1"
        existingParticipants={[
          {
            id: "participant-existing",
            full_name: "Ana Pop",
            email: "ana@example.com",
          },
        ]}
        lockCompany
      />,
    );

    const fileInput = container.querySelector('input[type="file"]');
    expect(fileInput).not.toBeNull();
    fireEvent.change(fileInput as HTMLInputElement, {
      target: {
        files: [new File(["fake"], "roster.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" })],
      },
    });

    expect(await screen.findByText(/participant cu acest email în companie/)).not.toBeNull();
    const importButton = screen.getByRole("button", { name: "Salvează participanții" }) as HTMLButtonElement;
    expect(importButton.disabled).toBe(true);
    expect(importCompanyRoster).not.toHaveBeenCalled();
  });

  it("derives PCM base and phase only from the color-coded PCM matrix", async () => {
    workbookState.rows = [
      ["Name", "email", "Reports To", "Position", "Location", "PCM 1", "PCM 2", "PCM 3", "PCM 4", "PCM 5", "PCM 6"],
      ["Vlad Manager", "vlad@example.com", "", "Manager", "București", "Promotor ()", "Perseverent ()", "Empatic ()", "Ganditor ()", "Rebel ()", "Imaginator ()"],
    ];
    workbookState.sheet = {
      I2: { s: { fill: { fgColor: { rgb: "FF00B0F0" } } } },
      G2: { s: { fill: { fgColor: { rgb: "FFFFFF00" } } } },
    };

    vi.mocked(importCompanyRoster).mockResolvedValue({
      participants: [],
      email_results: [],
      total_imported: 1,
      emails_sent: 0,
      emails_failed: 0,
    });

    const { container } = render(
      <RosterImporter
        companies={[{ id: "company-1", name: "Michelin" }]}
        defaultCompanyId="company-1"
        lockCompany
      />,
    );

    fireEvent.change(container.querySelector('input[type="file"]') as HTMLInputElement, {
      target: {
        files: [new File(["fake"], "pcm.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" })],
      },
    });

    expect(await screen.findByText("Gânditor")).not.toBeNull();
    expect(screen.getAllByText("Perseverent").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Salvează participanții" }));

    await waitFor(() => expect(importCompanyRoster).toHaveBeenCalledTimes(1));
    expect(importCompanyRoster).toHaveBeenCalledWith("company-1", [
      expect.objectContaining({
        Name: "Vlad Manager",
        email: "vlad@example.com",
        "PCM Bază": "Gânditor",
        "PCM Fază": "Perseverent",
      }),
    ]);
  });

  it("imports real roster rows with an embedded PCM matrix and ignores only standalone legend rows", async () => {
    workbookState.rows = [
      ["Name", "Reports To", "Position", "Location", "email", "Profil PCM", "", "", "", "", "", ""],
      ["Titus Julien Botis", "", "Directeur Site de Zalau", "Zalau", "titus@example.com", "Titus Botis", "Ganditor ()", "Perseverent ()", "Promotor ()", "Empatic ()", "Imaginator ()", "Rebel ()"],
      ["Denisa Stirb", "AdrianDemle", "Tehnician uniformitate", "Zalau", "denisa@example.com", "Legend", "", "", "", "", "", ""],
      ["Hailong Yan", "AdrianDemle", "Process Industrialisator", "Zalau", "hailong@example.com", "Base", "", "", "", "", "", ""],
      ["Legend", "", "", "", "", "", "", "", "", "", "", ""],
      ["Base", "", "", "", "", "", "", "", "", "", "", ""],
      ["Base & Phase", "", "", "", "", "", "", "", "", "", "", ""],
      ["Phase", "", "", "", "", "", "", "", "", "", "", ""],
      ["Stage", "", "", "", "", "", "", "", "", "", "", ""],
    ];
    workbookState.sheet = {
      G2: { s: { fill: { fgColor: { rgb: "FF00B0F0" } } } },
      H2: { s: { fill: { fgColor: { rgb: "FFFFFF00" } } } },
    };

    vi.mocked(importCompanyRoster).mockResolvedValue({
      participants: [],
      email_results: [],
      total_imported: 3,
      emails_sent: 0,
      emails_failed: 0,
    });

    const { container } = render(
      <RosterImporter
        companies={[{ id: "company-1", name: "Michelin" }]}
        defaultCompanyId="company-1"
        lockCompany
      />,
    );

    fireEvent.change(container.querySelector('input[type="file"]') as HTMLInputElement, {
      target: {
        files: [new File(["fake"], "michelin.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" })],
      },
    });

    expect(await screen.findByText(/Am încărcat 3 rânduri/)).not.toBeNull();
    expect(screen.getByText("Titus Julien Botis")).not.toBeNull();
    expect(screen.getAllByText("Denisa Stirb").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Hailong Yan").length).toBeGreaterThan(0);
    expect(screen.queryByText("Lipsă obligatoriu")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Salvează participanții" }));

    await waitFor(() => expect(importCompanyRoster).toHaveBeenCalledTimes(1));
    expect(importCompanyRoster).toHaveBeenCalledWith("company-1", [
      expect.objectContaining({
        Name: "Titus Julien Botis",
        email: "titus@example.com",
        "PCM Bază": "Gânditor",
        "PCM Fază": "Perseverent",
      }),
      expect.objectContaining({
        Name: "Denisa Stirb",
        email: "denisa@example.com",
        "PCM Bază": "",
        "PCM Fază": "",
      }),
      expect.objectContaining({
        Name: "Hailong Yan",
        email: "hailong@example.com",
        "PCM Bază": "",
        "PCM Fază": "",
      }),
    ]);
  });

  it("auto-maps common Romanian roster column variants", async () => {
    workbookState.rows = [
      ["Nume complet", "Reports To / Manager", "Poziție / Rol", "Locație", "Adresă Email"],
      ["Ana Pop", "", "Manager", "București", "ana@example.com"],
    ];

    vi.mocked(importCompanyRoster).mockResolvedValue({
      participants: [],
      email_results: [],
      total_imported: 1,
      emails_sent: 0,
      emails_failed: 0,
    });

    const { container } = render(
      <RosterImporter
        companies={[{ id: "company-1", name: "Michelin" }]}
        defaultCompanyId="company-1"
        lockCompany
      />,
    );

    fireEvent.change(container.querySelector('input[type="file"]') as HTMLInputElement, {
      target: {
        files: [new File(["fake"], "ro.xlsx", { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" })],
      },
    });

    expect(await screen.findByText(/Am încărcat 1 rânduri/)).not.toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Salvează participanții" }));

    await waitFor(() => expect(importCompanyRoster).toHaveBeenCalledTimes(1));
    expect(importCompanyRoster).toHaveBeenCalledWith("company-1", [
      expect.objectContaining({
        Name: "Ana Pop",
        "Reports To": "",
        Position: "Manager",
        Location: "București",
        email: "ana@example.com",
      }),
    ]);
  });
});
