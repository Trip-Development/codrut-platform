import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AccountSettingsPanel } from "./account-settings-panel";

vi.mock("@/api/auth", () => ({
  changePassword: vi.fn(),
}));

describe("AccountSettingsPanel", () => {
  afterEach(() => {
    cleanup();
  });

  it("can render the compact trainer settings panel without explanatory context or notes", () => {
    render(
      <AccountSettingsPanel
        eyebrow="Cont trainer"
        title="trainer"
        passwordEnabled={false}
        accountRows={[
          { label: "Email", value: "trainer@example.com", tone: "accent" },
          { label: "Rol", value: "Trainer / owner" },
        ]}
      />,
    );

    expect(screen.getByText("trainer@example.com")).toBeDefined();
    expect(screen.getByText("Schimbă parola")).toBeDefined();
    expect(screen.queryByText("Context operațional")).toBeNull();
    expect(screen.queryByText("Note")).toBeNull();
    expect(screen.queryByText(/Setările de aici afectează/i)).toBeNull();
  });
});
