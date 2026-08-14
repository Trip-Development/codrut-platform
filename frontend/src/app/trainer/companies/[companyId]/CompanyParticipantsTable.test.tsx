import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  deleteCompanyParticipant,
  updateCompanyParticipant,
  type CompanyParticipant,
} from "@/api/companies";
import { CompanyParticipantsTable } from "./CompanyParticipantsTable";

vi.mock("next/navigation", () => ({
  usePathname: () => "/trainer/companies/company-1/participants",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ refresh: vi.fn() }),
}));

vi.mock("@/api/companies", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/companies")>();
  return {
    ...original,
    deleteCompanyParticipant: vi.fn(),
    updateCompanyParticipant: vi.fn(),
  };
});

const participants: CompanyParticipant[] = [
  {
    id: "participant-1",
    full_name: "Ștefan Ionescu",
    email: "stefan@example.test",
    reports_to_name: "Ana Manager",
    position: "Consultant",
    location: "București",
    role_group: "member",
    pcm_profile: null,
    user_id: null,
  },
  {
    id: "participant-2",
    full_name: "Ana Manager",
    email: "ana@example.test",
    reports_to_name: null,
    position: "Director",
    location: "Cluj",
    role_group: "leadership",
    pcm_profile: null,
    user_id: "user-2",
    avatar_palette_key: 12_345,
  },
  {
    id: "participant-3",
    full_name: "Mihai Temporar",
    email: "mihai@example.test",
    reports_to_name: "Ana Manager",
    position: "Specialist",
    location: "Iași",
    role_group: "member",
    pcm_profile: null,
    user_id: "shadow-user-3",
    is_shadow_account: true,
  },
];

describe("CompanyParticipantsTable", () => {
  beforeEach(() => {
    window.history.replaceState(null, "", "/trainer/companies/company-1/participants");
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("filters company participants without diacritics and persists the query in the URL", () => {
    render(<CompanyParticipantsTable companyId="company-1" participants={participants} />);

    fireEvent.change(screen.getByLabelText("Caută participant"), {
      target: { value: "stefan" },
    });

    expect(screen.getByText("Ștefan Ionescu")).toBeTruthy();
    expect(screen.queryByText("ana@example.test")).toBeNull();
    expect(`${window.location.pathname}${window.location.search}`).toBe(
      "/trainer/companies/company-1/participants?q=stefan",
    );
  });

  it("shows only real linked accounts as active", () => {
    render(<CompanyParticipantsTable companyId="company-1" participants={participants} />);

    const permanentRow = screen.getByText("ana@example.test").closest("tr");
    const shadowRow = screen.getByText("Mihai Temporar").closest("tr");

    expect(permanentRow).toBeTruthy();
    expect(shadowRow).toBeTruthy();
    expect(within(permanentRow as HTMLElement).getByText("Activ")).toBeTruthy();
    expect(within(shadowRow as HTMLElement).getByText("Necreat")).toBeTruthy();
    expect(
      permanentRow?.querySelector("[data-avatar-palette-key='12345']"),
    ).toBeTruthy();
  });

  it("edits the company-level manager from the participant sheet", async () => {
    vi.mocked(updateCompanyParticipant).mockResolvedValue({
      ...participants[0],
      reports_to_name: null,
    });
    render(<CompanyParticipantsTable companyId="company-1" participants={participants} />);

    fireEvent.click(screen.getByRole("button", { name: "Editează Ștefan Ionescu" }));
    fireEvent.change(await screen.findByRole("combobox", { name: "Manager" }), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvează managerul" }));

    await waitFor(() => expect(updateCompanyParticipant).toHaveBeenCalledWith(
      "company-1",
      "participant-1",
      { reportsToName: null },
    ));
  });

  it("warns with named direct reports before company deletion", async () => {
    vi.mocked(deleteCompanyParticipant).mockResolvedValue();
    render(<CompanyParticipantsTable companyId="company-1" participants={participants} />);

    fireEvent.click(screen.getByRole("button", { name: "Editează Ana Manager" }));
    fireEvent.click(screen.getByRole("button", { name: "Șterge din companie" }));

    const removalDialog = await screen.findByRole("dialog", { name: "Șterge din companie" });
    expect(within(removalDialog).getByText(/Ștefan Ionescu/)).toBeTruthy();
    expect(within(removalDialog).getByText(/Mihai Temporar/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Șterge din companie" }));

    await waitFor(() => expect(deleteCompanyParticipant).toHaveBeenCalledWith(
      "company-1",
      "participant-2",
      ["participant-3", "participant-1"],
    ));
  });
});
