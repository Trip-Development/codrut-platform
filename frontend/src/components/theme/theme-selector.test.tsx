import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getStoredThemeMode, persistThemeMode, resolveTheme, ThemeSelector } from "./theme-selector";

beforeEach(() => {
  window.localStorage.clear();
  document.documentElement.removeAttribute("data-theme");
  document.documentElement.removeAttribute("data-theme-mode");
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query.includes("dark"),
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    })),
  });
});

afterEach(() => cleanup());

describe("ThemeSelector", () => {
  it("uses the system preference when no explicit choice exists", async () => {
    render(<ThemeSelector />);

    await waitFor(() => {
      expect(document.documentElement.dataset.themeMode).toBe("system");
      expect(document.documentElement.dataset.theme).toBe("dark");
    });
    expect(screen.getByRole("combobox", { name: "Temă" }).textContent).toContain("Sistem");
  });

  it("persists an explicit selection", async () => {
    persistThemeMode("light");

    await waitFor(() => {
      expect(window.localStorage.setItem).toHaveBeenCalledWith("codrut-theme", "light");
      expect(document.documentElement.dataset.theme).toBe("light");
    });
  });

  it("tracks system theme changes while system mode is active", async () => {
    let prefersDark = false;
    let handleChange: (() => void) | undefined;
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: vi.fn().mockImplementation((query: string) => ({
        get matches() {
          return prefersDark && query.includes("dark");
        },
        media: query,
        addEventListener: vi.fn((_event: string, listener: () => void) => {
          handleChange = listener;
        }),
        removeEventListener: vi.fn(),
      })),
    });

    render(<ThemeSelector />);
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("light"));

    prefersDark = true;
    handleChange?.();

    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("dark"));
  });
});

describe("theme preference helpers", () => {
  it("rejects unknown stored values", () => {
    window.localStorage.setItem("codrut-theme", "sepia");
    expect(getStoredThemeMode()).toBe("system");
  });

  it("resolves explicit themes without consulting the system", () => {
    expect(resolveTheme("light")).toBe("light");
    expect(resolveTheme("dark")).toBe("dark");
  });
});
