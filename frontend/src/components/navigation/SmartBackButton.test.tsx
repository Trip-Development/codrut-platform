import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { SmartBackButton } from "./SmartBackButton";

const navigation = vi.hoisted(() => ({
  back: vi.fn(),
  push: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  useRouter: () => navigation,
}));

describe("SmartBackButton", () => {
  afterEach(() => {
    cleanup();
    navigation.back.mockReset();
    navigation.push.mockReset();
    vi.restoreAllMocks();
  });

  it("returns through app history when a stale link was opened from another page", () => {
    vi.spyOn(window.history, "length", "get").mockReturnValue(2);
    render(<SmartBackButton />);

    fireEvent.click(screen.getByRole("button", { name: "Înapoi" }));

    expect(navigation.back).toHaveBeenCalledOnce();
    expect(navigation.push).not.toHaveBeenCalled();
  });

  it("uses the safe fallback for a direct visit", () => {
    vi.spyOn(window.history, "length", "get").mockReturnValue(1);
    render(<SmartBackButton fallbackHref="/participant" />);

    fireEvent.click(screen.getByRole("button", { name: "Înapoi" }));

    expect(navigation.push).toHaveBeenCalledWith("/participant");
    expect(navigation.back).not.toHaveBeenCalled();
  });
});
