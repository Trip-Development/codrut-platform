import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { confirmPasswordReset } from "@/api/auth";
import UpdatePasswordPage from "./page";

const navigationMocks = {
  searchParams: new URLSearchParams("token=reset-token"),
};

vi.mock("next/navigation", () => ({
  useSearchParams: () => navigationMocks.searchParams,
}));

vi.mock("@/api/auth", () => ({
  confirmPasswordReset: vi.fn(),
}));

describe("UpdatePasswordPage", () => {
  beforeEach(() => {
    navigationMocks.searchParams = new URLSearchParams("token=reset-token");
    vi.mocked(confirmPasswordReset).mockResolvedValue();
    window.history.replaceState(null, "", "/update-password?token=reset-token");
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("keeps the reset token after cleaning it from the visible URL", async () => {
    const { rerender } = render(<UpdatePasswordPage />);

    expect(window.location.pathname).toBe("/update-password");
    expect(window.location.search).toBe("");

    navigationMocks.searchParams = new URLSearchParams();
    rerender(<UpdatePasswordPage />);

    fireEvent.change(screen.getByLabelText("Parola nouă"), {
      target: { value: "o frază lungă și memorabilă" },
    });
    fireEvent.change(screen.getByLabelText("Confirmă parola"), {
      target: { value: "o frază lungă și memorabilă" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvează parola" }));

    await waitFor(() => {
      expect(confirmPasswordReset).toHaveBeenCalledWith("reset-token", "o frază lungă și memorabilă");
    });
  });

  it("shows boxed pending feedback and locks password fields while saving", async () => {
    let resolveReset!: () => void;
    const resetPromise = new Promise<void>((resolve) => {
      resolveReset = resolve;
    });
    vi.mocked(confirmPasswordReset).mockReturnValue(resetPromise);

    render(<UpdatePasswordPage />);

    fireEvent.change(screen.getByLabelText("Parola nouă"), {
      target: { value: "o frază lungă și memorabilă" },
    });
    fireEvent.change(screen.getByLabelText("Confirmă parola"), {
      target: { value: "o frază lungă și memorabilă" },
    });
    const submitButton = screen.getByRole("button", { name: "Salvează parola" });
    const resetForm = submitButton.closest("form");
    expect(resetForm).not.toBeNull();
    fireEvent.submit(resetForm!);
    fireEvent.submit(resetForm!);

    await screen.findByText("Salvăm parola nouă");
    expect(confirmPasswordReset).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Salvăm parola" })).toHaveProperty("disabled", true);
    expect(screen.getByLabelText("Parola nouă")).toHaveProperty("disabled", true);
    expect(screen.getByLabelText("Confirmă parola")).toHaveProperty("disabled", true);

    await act(async () => {
      resolveReset();
      await resetPromise;
    });

    await screen.findByText("Parola a fost actualizată.");
  });
});
