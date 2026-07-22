import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import {
  createCompany,
  importCompanyRoster,
  sendParticipantInvitations,
} from "@/api/companies";
import { readSpreadsheetFile } from "@/utils/spreadsheet-import";
import { RosterImporter } from "./roster-importer";

const routerMock = vi.hoisted(() => ({
  push: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => routerMock,
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

vi.mock("@/utils/spreadsheet-import", () => ({
  readSpreadsheetFile: vi.fn(),
}));

describe("RosterImporter", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows file processing feedback while the spreadsheet is being read", async () => {
    const readRequest = createDeferred<Awaited<ReturnType<typeof readSpreadsheetFile>>>();
    vi.mocked(readSpreadsheetFile).mockReturnValue(readRequest.promise);

    const { container } = renderImporter();
    uploadRosterFile(container);

    expect(await screen.findByText("Citim fișierul")).toBeTruthy();
    expect(screen.getByText("Extragem coloanele, rândurile și marcajele PCM înainte de validarea listei.")).toBeTruthy();

    readRequest.resolve({
      sheetName: null,
      sheetNames: [],
      rows: [["Name", "email"], ["Ana Popescu", "ana@example.test"]],
      cells: [],
    });

    expect(await screen.findByText(/Am încărcat 1 rânduri/)).toBeTruthy();
    expect(screen.getByLabelText("Coloană pentru Nume Complet (Obligatoriu)").getAttribute("data-slot")).toBe("select");
  });

  it("ignores duplicate file changes while the spreadsheet is still being read", async () => {
    const readRequest = createDeferred<Awaited<ReturnType<typeof readSpreadsheetFile>>>();
    vi.mocked(readSpreadsheetFile).mockReturnValue(readRequest.promise);

    const { container } = renderImporter();
    uploadRosterFile(container);
    uploadRosterFile(container);

    expect(await screen.findByText("Citim fișierul")).toBeTruthy();
    expect(readSpreadsheetFile).toHaveBeenCalledTimes(1);

    readRequest.resolve({
      sheetName: null,
      sheetNames: [],
      rows: [["Name", "email"], ["Ana Popescu", "ana@example.test"]],
      cells: [],
    });

    expect(await screen.findByText(/Am încărcat 1 rânduri/)).toBeTruthy();
  });

  it("shows participant save and access feedback while backend calls are pending", async () => {
    vi.mocked(readSpreadsheetFile).mockResolvedValue({
      sheetName: null,
      sheetNames: [],
      rows: [["Name", "email"], ["Ana Popescu", "ana@example.test"]],
      cells: [],
    });
    const importRequest = createDeferred<Awaited<ReturnType<typeof importCompanyRoster>>>();
    vi.mocked(importCompanyRoster).mockReturnValue(importRequest.promise);

    const { container } = renderImporter();
    uploadRosterFile(container);

    expect(await screen.findByText(/Am încărcat 1 rânduri/)).toBeTruthy();
    const saveButton = screen.getByRole("button", { name: "Salvează participanții" });
    fireEvent.click(saveButton);
    fireEvent.click(saveButton);

    expect(await screen.findByText("Salvăm participanții")).toBeTruthy();
    expect(screen.getByText("Trimitem lista validată către companie și legăm participanții de proiectul selectat.")).toBeTruthy();
    expect(importCompanyRoster).toHaveBeenCalledTimes(1);

    importRequest.resolve({
      participants: [
        {
          id: "participant-1",
          full_name: "Ana Popescu",
          email: "ana@example.test",
          reports_to_name: null,
          position: null,
          location: null,
          role_group: null,
          pcm_profile: null,
          user_id: null,
        },
      ],
      email_results: [],
      total_imported: 1,
      emails_sent: 0,
      emails_failed: 0,
    });

    expect(await screen.findByText("Participanți salvați")).toBeTruthy();

    const accessRequest = createDeferred<Awaited<ReturnType<typeof sendParticipantInvitations>>>();
    vi.mocked(sendParticipantInvitations).mockReturnValue(accessRequest.promise);
    const secureLinksButton = screen.getByRole("button", { name: "Generează linkuri securizate" });
    fireEvent.click(secureLinksButton);
    fireEvent.click(secureLinksButton);

    expect(await screen.findByRole("button", { name: "Generăm linkurile" })).toBeTruthy();
    expect(await screen.findAllByText("Generăm linkurile")).toHaveLength(2);
    expect(screen.getByText("Creăm acces securizat pentru participanții importați acum.")).toBeTruthy();
    expect(sendParticipantInvitations).toHaveBeenCalledTimes(1);

    accessRequest.resolve({
      total: 1,
      emails_sent: 0,
      emails_failed: 0,
      links_generated: 1,
      results: [
        {
          participant_id: "participant-1",
          full_name: "Ana Popescu",
          email: "ana@example.test",
          delivery_mode: "secure_links",
          email_sent: false,
          invite_url: "https://codrut.example.test/invite/token",
          error: null,
        },
      ],
    });

    expect(await screen.findByText("1/1 linkuri securizate generate.")).toBeTruthy();
  });

  it("shows company creation feedback and locks the modal controls while pending", async () => {
    const createRequest = createDeferred<Awaited<ReturnType<typeof createCompany>>>();
    vi.mocked(createCompany).mockReturnValue(createRequest.promise);

    renderImporterWithCompanyPicker();

    expect(screen.getByLabelText("Companie destinație").getAttribute("data-slot")).toBe("select");
    expect(screen.getByLabelText("Proiect destinație").getAttribute("data-slot")).toBe("select");

    fireEvent.click(screen.getByRole("button", { name: "Companie nouă" }));
    const companyNameInput = screen.getByPlaceholderText("Ex. Atlas Mobility SRL") as HTMLInputElement;
    fireEvent.change(companyNameInput, { target: { value: "Nova Retail Group" } });
    const addButton = screen.getByRole("button", { name: "Adaugă" });
    fireEvent.click(addButton);
    fireEvent.click(addButton);

    expect(await screen.findAllByText("Creăm compania")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Creăm compania" })).toBeTruthy();
    expect(screen.getByText("Pregătim spațiul pentru Nova Retail Group.")).toBeTruthy();
    expect(createCompany).toHaveBeenCalledTimes(1);
    expect(companyNameInput.disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Anulează" }) as HTMLButtonElement).disabled).toBe(true);

    createRequest.resolve({ id: "company-2", name: "Nova Retail Group" });

    await waitFor(() => {
      expect(screen.queryByText("Creăm compania")).toBeNull();
    });
  });
});

function renderImporter() {
  return render(
    <RosterImporter
      companies={[{ id: "company-1", name: "Michelin" }]}
      defaultCompanyId="company-1"
      lockCompany
      projects={[{ id: "project-1", name: "Leadership", status: "active" }]}
      defaultProjectId="project-1"
      requireProject
    />,
  );
}

function renderImporterWithCompanyPicker() {
  return render(
    <RosterImporter
      companies={[{ id: "company-1", name: "Michelin" }]}
      defaultCompanyId="company-1"
      projects={[{ id: "project-1", name: "Leadership", status: "active" }]}
      requireProject
    />,
  );
}

function uploadRosterFile(container: HTMLElement) {
  const input = container.querySelector<HTMLInputElement>('input[type="file"]');
  expect(input).toBeTruthy();
  fireEvent.change(input!, {
    target: {
      files: [new File(["Name,email\nAna Popescu,ana@example.test"], "participants.csv", { type: "text/csv" })],
    },
  });
}

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });

  return { promise, resolve, reject };
}
