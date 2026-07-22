import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { requestPasswordReset } from "@/api/auth";
import ResetPasswordPage from "./page";

vi.mock("@/api/auth", () => ({
  requestPasswordReset: vi.fn(),
}));

describe("ResetPasswordPage", () => {
  beforeEach(() => {
    vi.mocked(requestPasswordReset).mockResolvedValue();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("keeps reset available and submits a browser-autofilled address", async () => {
    render(<ResetPasswordPage />);

    const emailInput = screen.getByLabelText("Email") as HTMLInputElement;
    const submitButton = screen.getByRole("button", { name: "Trimite link securizat" });
    expect(submitButton).toHaveProperty("disabled", false);

    const nativeValueSetter = Object.getOwnPropertyDescriptor(
      HTMLInputElement.prototype,
      "value",
    )?.set;
    nativeValueSetter?.call(emailInput, "existing@example.com");
    fireEvent.submit(submitButton.closest("form")!);

    await screen.findByText("Verifică emailul.");
    expect(requestPasswordReset).toHaveBeenCalledWith("existing@example.com");
  });

  it("shows a recoverable error for an empty programmatic submission", async () => {
    render(<ResetPasswordPage />);

    const submitButton = screen.getByRole("button", { name: "Trimite link securizat" });
    fireEvent.submit(submitButton.closest("form")!);

    expect(await screen.findByText("Introdu adresa de email asociată contului.")).toBeTruthy();
    expect(requestPasswordReset).not.toHaveBeenCalled();
  });

  it("shows boxed pending feedback and locks the email field while sending", async () => {
    let resolveReset!: () => void;
    const resetPromise = new Promise<void>((resolve) => {
      resolveReset = resolve;
    });
    vi.mocked(requestPasswordReset).mockReturnValue(resetPromise);

    render(<ResetPasswordPage />);

    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "andreea@example.com" },
    });
    const submitButton = screen.getByRole("button", { name: "Trimite link securizat" });
    const resetForm = submitButton.closest("form");
    expect(resetForm).not.toBeNull();
    fireEvent.submit(resetForm!);
    fireEvent.submit(resetForm!);

    await screen.findByText("Trimitem linkul securizat");
    expect(requestPasswordReset).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Trimitem linkul" })).toHaveProperty("disabled", true);
    expect(screen.getByLabelText("Email")).toHaveProperty("disabled", true);

    await act(async () => {
      resolveReset();
      await resetPromise;
    });

    await screen.findByText("Verifică emailul.");
  });
});
