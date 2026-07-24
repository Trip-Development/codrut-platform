import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { repairParticipantAccountLink } from "@/api/companies";
import { AccountLinkRepairPanel } from "./AccountLinkRepairPanel";

vi.mock("@/api/companies", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/companies")>();
  return {
    ...original,
    repairParticipantAccountLink: vi.fn(),
  };
});

const initialStatus = {
  participant_id: "participant-1",
  participant_email: "person@example.com",
  linked_account: {
    user_id: "wrong-user",
    email: "wrong@example.com",
    role: "participant" as const,
    is_shadow_account: true,
  },
  matching_email_account: {
    user_id: "matching-user",
    email: "person@example.com",
    role: "trainer" as const,
    is_shadow_account: false,
  },
  matching_account_is_linked: false,
};

describe("AccountLinkRepairPanel", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("requires exact email and a reason before linking the matching account", async () => {
    vi.mocked(repairParticipantAccountLink).mockResolvedValue({
      ...initialStatus,
      linked_account: initialStatus.matching_email_account,
      matching_account_is_linked: true,
    });
    render(
      <AccountLinkRepairPanel
        companyId="company-1"
        participantId="participant-1"
        initialStatus={initialStatus}
      />,
    );

    fireEvent.click(screen.getByText("Administrare legătură cont"));
    fireEvent.click(screen.getByRole("button", { name: "Leagă contul cu același email" }));
    const confirmButton = screen.getByRole("button", { name: "Confirmă repararea" }) as HTMLButtonElement;
    expect(confirmButton.disabled).toBe(true);

    fireEvent.change(screen.getByLabelText("Scrie exact emailul participantului pentru confirmare"), {
      target: { value: "person@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Motivul intervenției"), {
      target: { value: "Conflict verificat cu utilizatorul." },
    });
    expect(confirmButton.disabled).toBe(false);
    fireEvent.click(confirmButton);

    await waitFor(() => {
      expect(repairParticipantAccountLink).toHaveBeenCalledWith(
        "company-1",
        "participant-1",
        {
          action: "link_matching_email",
          confirmationEmail: "person@example.com",
          reason: "Conflict verificat cu utilizatorul.",
        },
      );
    });
    expect(await screen.findByText("Legătura contului a fost actualizată și înregistrată în audit.")).toBeTruthy();
  });

  it("renders a safe unavailable state when account status cannot be loaded", () => {
    render(
      <AccountLinkRepairPanel
        companyId="company-1"
        participantId="participant-1"
        initialStatus={null}
      />,
    );

    expect(
      screen.getByText("Starea contului nu este disponibilă pentru acest participant."),
    ).toBeTruthy();
    expect(screen.queryByText("Administrare legătură cont")).toBeNull();
  });

  it("unlinks the current account after explicit confirmation", async () => {
    vi.mocked(repairParticipantAccountLink).mockResolvedValue({
      ...initialStatus,
      linked_account: null,
      matching_email_account: null,
      matching_account_is_linked: false,
    });
    render(
      <AccountLinkRepairPanel
        companyId="company-1"
        participantId="participant-1"
        initialStatus={initialStatus}
      />,
    );

    fireEvent.click(screen.getByText("Administrare legătură cont"));
    fireEvent.click(screen.getByRole("button", { name: "Deconectează contul" }));
    fireEvent.change(screen.getByLabelText("Scrie exact emailul participantului pentru confirmare"), {
      target: { value: "PERSON@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Motivul intervenției"), {
      target: { value: "Legătura greșită a fost verificată." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirmă repararea" }));

    await waitFor(() => {
      expect(repairParticipantAccountLink).toHaveBeenCalledWith(
        "company-1",
        "participant-1",
        {
          action: "unlink",
          confirmationEmail: "PERSON@example.com",
          reason: "Legătura greșită a fost verificată.",
        },
      );
    });
    expect(
      await screen.findByText("Nu există încă un cont platformă cu emailul person@example.com."),
    ).toBeTruthy();
  });

  it("keeps the repair form open and shows a backend failure", async () => {
    vi.mocked(repairParticipantAccountLink).mockRejectedValue(
      new Error("Conflictul nu mai este actual."),
    );
    render(
      <AccountLinkRepairPanel
        companyId="company-1"
        participantId="participant-1"
        initialStatus={initialStatus}
      />,
    );

    fireEvent.click(screen.getByText("Administrare legătură cont"));
    fireEvent.click(screen.getByRole("button", { name: "Leagă contul cu același email" }));
    fireEvent.change(screen.getByLabelText("Scrie exact emailul participantului pentru confirmare"), {
      target: { value: "person@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Motivul intervenției"), {
      target: { value: "Conflict verificat înainte de intervenție." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Confirmă repararea" }));

    expect(await screen.findByText("Repararea a eșuat")).toBeTruthy();
    expect(screen.getByText("Conflictul nu mai este actual.")).toBeTruthy();
    expect(screen.getByLabelText("Motivul intervenției")).toBeTruthy();
  });
});
