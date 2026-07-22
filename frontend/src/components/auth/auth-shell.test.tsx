import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RememberedSessionSplash } from "./auth-shell";

describe("RememberedSessionSplash", () => {
  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("does not present a generic role as a saved user name", () => {
    render(
      <RememberedSessionSplash
        user={{
          id: "trainer-1",
          name: "trainer",
          email: "trainer@example.com",
          role: "trainer",
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Cont trainer salvat" })).toBeDefined();
    expect(screen.queryByRole("heading", { name: "Trainer" })).toBeNull();
    expect(screen.getByText(/pentru contul trainer/i)).toBeDefined();
  });

  it("keeps a human display name when the session has one", () => {
    render(
      <RememberedSessionSplash
        user={{
          id: "participant-1",
          name: "Bianca Pavel",
          email: "bianca.pavel@example.com",
          role: "participant",
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "Bianca Pavel" })).toBeDefined();
    expect(screen.getByText("Am găsit sesiunea ta salvată. Te ducem în spațiul tău.")).toBeDefined();
  });

  it("animates remembered-session progress through classes so reduced motion can override it", () => {
    vi.useFakeTimers();

    render(
      <RememberedSessionSplash
        user={{
          id: "participant-1",
          name: "Bianca Pavel",
          email: "bianca.pavel@example.com",
          role: "participant",
        }}
      />,
    );

    const track = screen.getByLabelText("Încărcăm sesiunea salvată");
    const fill = track.firstElementChild;

    if (!(fill instanceof HTMLElement)) {
      throw new Error("Remembered-session progress fill was not rendered.");
    }

    expect(fill.classList.contains("scale-x-0")).toBe(true);
    expect(fill.getAttribute("style") ?? "").not.toContain("transform");

    act(() => {
      vi.advanceTimersByTime(45);
    });

    expect(fill.classList.contains("scale-x-100")).toBe(true);
  });
});
