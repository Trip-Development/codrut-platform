import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import PrivacyPage from "./page";

describe("PrivacyPage", () => {
  it("truthfully explains the active archive and privacy lifecycle", () => {
    render(<PrivacyPage />);

    expect(screen.getByText("Actualizat la 30 iulie 2026")).toBeTruthy();
    expect(screen.getByText(/contactul poate fi restaurat din Arhivă timp de 30 de zile/i)).toBeTruthy();
    expect(screen.getByText(/datele directe de contact și legăturile cu campaniile sunt șterse automat/)).toBeTruthy();
    expect(screen.getByText(/După ștergerea datelor directe pot rămâne numai marcaje codificate/)).toBeTruthy();
    expect(screen.getByText(/Fiecare marcaj păstrat are o dată de revizuire în cel mult 12 luni/)).toBeTruthy();
    expect(screen.queryByText(/nu este încă activă|va fi pornită|După activarea procesului/i)).toBeNull();
    expect(screen.getByRole("link", { name: "andrei@andreivacaru.ro" })).toBeTruthy();
    expect(screen.queryByText(/provider_message_fingerprint|tombstone|hash/i)).toBeNull();
  });
});
