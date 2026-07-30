import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import PrivacyPage from "./page";

describe("PrivacyPage", () => {
  it("truthfully explains the transitional archive and future privacy lifecycle", () => {
    render(<PrivacyPage />);

    expect(screen.getByText("Actualizat la 30 iulie 2026")).toBeTruthy();
    expect(screen.getByText(/Contactul poate fi restaurat din Arhivă/)).toBeTruthy();
    expect(screen.getByText(/Ștergerea automată a datelor directe nu este încă activă/)).toBeTruthy();
    expect(screen.getByText(/După activarea procesului.*vor putea rămâne numai marcaje codificate/)).toBeTruthy();
    expect(screen.getByText(/Fiecare marcaj păstrat va avea o dată de revizuire în cel mult 12 luni/)).toBeTruthy();
    expect(screen.queryByText(/În cel mult 30 de zile ștergem/i)).toBeNull();
    expect(screen.getByRole("link", { name: "andrei@andreivacaru.ro" })).toBeTruthy();
    expect(screen.queryByText(/provider_message_fingerprint|tombstone|hash/i)).toBeNull();
  });
});
