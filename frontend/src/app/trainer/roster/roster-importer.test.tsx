import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { importCompanyRoster, sendParticipantInvitations } from "@/api/companies";
import { RosterImporter } from "./roster-importer";

const router = vi.hoisted(() => ({
  push: vi.fn(),
  refresh: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

vi.mock("xlsx", () => ({
  read: vi.fn(() => ({
    SheetNames: ["Roster"],
    Sheets: { Roster: {} },
  })),
  utils: {
    sheet_to_json: vi.fn(() => [
      ["Name", "email", "Reports To", "Position", "Location", "Profil PCM"],
      ["Ana Pop", "ana@example.com", "", "Manager", "București", "PCM rebel"],
    ]),
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
          "Profil PCM": "PCM rebel",
        },
      ],
    );

    expect(await screen.findByText("Participanți salvați. Alege cum le dai acces.")).not.toBeNull();
    expect(sendParticipantInvitations).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Generează linkuri securizate" }));

    await waitFor(() => expect(sendParticipantInvitations).toHaveBeenCalledTimes(1));
    expect(sendParticipantInvitations).toHaveBeenCalledWith("company-1", {
      participantIds: ["participant-1"],
      mode: "secure_links",
    });
    expect(await screen.findByText("1/1 linkuri securizate generate.")).not.toBeNull();
    expect(screen.getByText("Link securizat pregătit")).not.toBeNull();
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
});
