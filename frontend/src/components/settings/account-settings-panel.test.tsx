import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { changePassword } from "@/api/auth";
import { PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH } from "@/api/password-policy";
import { AccountSettingsPanel } from "./account-settings-panel";

vi.mock("@/api/auth", () => ({
  changePassword: vi.fn(),
}));

describe("AccountSettingsPanel", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("can render the compact trainer settings panel without explanatory context or notes", () => {
    render(
      <AccountSettingsPanel
        passwordEnabled={false}
        accountRows={[
          { label: "Email", value: "trainer@example.com", tone: "accent" },
          { label: "Rol", value: "Trainer / owner" },
        ]}
      />,
    );

    expect(screen.getByText("trainer@example.com")).toBeDefined();
    expect(screen.getByText("Schimbă parola")).toBeDefined();
    expect(screen.queryByText("Program")).toBeNull();
    expect(screen.queryByText("Note")).toBeNull();
    expect(screen.queryByText(/Setările de aici afectează/i)).toBeNull();
  });

  it("uses the shared password policy constraints on editable password fields", () => {
    render(
      <AccountSettingsPanel
        passwordEnabled
        accountRows={[
          { label: "Email", value: "trainer@example.com", tone: "accent" },
          { label: "Rol", value: "Trainer / owner" },
        ]}
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

  it("shows a pending password update surface while the trainer password is saving", async () => {
    let resolveChange!: () => void;
    vi.mocked(changePassword).mockImplementation(
      () =>
        new Promise<void>((resolve) => {
          resolveChange = resolve;
        }),
    );

    render(
      <AccountSettingsPanel
        passwordEnabled
        accountRows={[
          { label: "Email", value: "trainer@example.com", tone: "accent" },
          { label: "Rol", value: "Trainer / owner" },
        ]}
      />,
    );

    fireEvent.change(screen.getByLabelText("Parola curentă"), { target: { value: "OldPass1!" } });
    fireEvent.change(screen.getByLabelText("Parolă nouă"), { target: { value: "NewPassphrase1!" } });
    fireEvent.change(screen.getByLabelText("Confirmă parola nouă"), { target: { value: "NewPassphrase1!" } });
    const submitButton = screen.getByRole("button", { name: "Actualizează parola" });
    const passwordForm = submitButton.closest("form");
    expect(passwordForm).not.toBeNull();

    fireEvent.submit(passwordForm!);
    fireEvent.submit(passwordForm!);

    expect(await screen.findAllByText("Actualizăm parola")).toHaveLength(1);
    expect(changePassword).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Actualizăm parola" })).toHaveProperty("disabled", true);
    expect(screen.getByLabelText("Parola curentă").hasAttribute("disabled")).toBe(true);

    await act(async () => {
      resolveChange();
    });

    expect(
      await screen.findByText("Parola a fost actualizată. Pentru securitate, sesiunile active au fost închise."),
    ).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Parola a fost actualizată" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Autentifică-te din nou" })).toHaveProperty("href", "http://localhost:3000/trainer/login");
    expect(screen.queryByLabelText("Parola curentă")).toBeNull();
  });
});
