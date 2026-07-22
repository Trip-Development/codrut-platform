import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { changePassword, type SessionState } from "@/api/auth";
import { PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH } from "@/api/password-policy";
import { AccountWorkspace } from "./AccountWorkspace";

vi.mock("@/api/auth", () => ({
  changePassword: vi.fn(),
}));

const session: SessionState = {
  state: "authenticated",
  user: {
    id: "participant-1",
    name: "Ana Participant",
    role: "participant",
  },
};

describe("AccountWorkspace", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows operational profile data and the participant result visibility rule", () => {
    render(
      <AccountWorkspace
        session={session}
        summary={{
          projectName: "Leadership septembrie",
          participantFullName: "Ana Participant",
          participantEmail: "ana@example.com",
          companyName: "Michelin",
          tasks: [],
        }}
      />,
    );

    expect(screen.getByText("ana@example.com")).toBeDefined();
    expect(screen.getByText("Michelin")).toBeDefined();
    expect(screen.queryByText("Scoruri și interpretări sumarizate în tabul Rezultate")).toBeNull();
    expect(screen.queryByText("Răspunsurile brute nu sunt afișate în cont")).toBeNull();
    expect(screen.getByText("Schimbă parola")).toBeDefined();
    expect(screen.queryByText("Armonizator")).toBeNull();
    expect(screen.queryByText("Gânditor")).toBeNull();
    expect(screen.queryByRole("link", { name: "Actualizează PCM" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Vezi chestionarele" })).toBeNull();
  });

  it("does not show missing PCM placeholders to participants", () => {
    render(
      <AccountWorkspace
        session={session}
        summary={{
          projectName: "Leadership septembrie",
          participantFullName: "Ana Participant",
          participantEmail: "ana@example.com",
          companyName: "Michelin",
          tasks: [],
        }}
      />,
    );

    expect(screen.queryByText("Necompletată")).toBeNull();
    expect(screen.getByText("Proiect")).toBeDefined();
  });

  it("uses the shared password policy constraints on participant password fields", () => {
    render(
      <AccountWorkspace
        session={session}
        summary={{
          projectName: "Leadership septembrie",
          participantFullName: "Ana Participant",
          participantEmail: "ana@example.com",
          companyName: "Michelin",
          tasks: [],
        }}
      />,
    );

    const newPassword = screen.getByLabelText("Parolă nouă") as HTMLInputElement;
    const confirmPassword = screen.getByLabelText("Confirmă parola nouă") as HTMLInputElement;

    expect(newPassword.minLength).toBe(PASSWORD_MIN_LENGTH);
    expect(newPassword.maxLength).toBe(PASSWORD_MAX_LENGTH);
    expect(newPassword.required).toBe(true);
    expect(confirmPassword.minLength).toBe(PASSWORD_MIN_LENGTH);
    expect(confirmPassword.maxLength).toBe(PASSWORD_MAX_LENGTH);
    expect(screen.getByText(/Minim 12 și maximum 128 de caractere/)).toBeDefined();
    expect(screen.getByText(/Parolele comune sau compromise sunt respinse/)).toBeDefined();
  });

  it("shows a pending password update surface while the participant password is saving", async () => {
    let resolveChange!: () => void;
    vi.mocked(changePassword).mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveChange = resolve;
        }),
    );

    render(
      <AccountWorkspace
        session={session}
        summary={{
          projectName: "Leadership septembrie",
          participantFullName: "Ana Participant",
          participantEmail: "ana@example.com",
          companyName: "Michelin",
          tasks: [],
        }}
      />,
    );

    fireEvent.change(screen.getByLabelText("Parola curentă"), { target: { value: "OldPass1!" } });
    fireEvent.change(screen.getByLabelText("Parolă nouă"), { target: { value: "NewPassphrase1!" } });
    fireEvent.change(screen.getByLabelText("Confirmă parola nouă"), { target: { value: "NewPassphrase1!" } });
    fireEvent.click(screen.getByRole("button", { name: "Actualizează parola" }));

    expect(await screen.findAllByText("Actualizăm parola")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Actualizăm parola" })).toHaveProperty("disabled", true);
    expect(screen.getByLabelText("Parola curentă").hasAttribute("disabled")).toBe(true);

    await act(async () => {
      resolveChange();
    });

    expect(
      await screen.findByText("Parola a fost actualizată. Pentru securitate, sesiunile active au fost închise."),
    ).toBeTruthy();
  });
});
