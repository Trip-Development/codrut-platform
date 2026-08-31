import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PracticeWorkspace } from "./PracticeWorkspace";

vi.mock("@/hooks/useVoiceToText", () => ({
  useVoiceToText: () => ({
    isListening: false,
    isTranscribing: false,
    startListening: vi.fn(),
    stopListening: vi.fn(),
    error: null,
  }),
}));

const api = vi.hoisted(() => ({
  startPracticeSession: vi.fn(),
  submitPracticeTurn: vi.fn(),
  endPracticeSession: vi.fn(),
}));

vi.mock("@/api/practice", () => api);

const SESIUNE_DESCHISA = {
  id: "sesiune-1",
  kind: "roleplay" as const,
  state: "open" as const,
  turnCount: 0,
};

beforeEach(() => {
  // jsdom nu are scrollIntoView, iar componenta il cheama la fiecare replica noua.
  Element.prototype.scrollIntoView = vi.fn();
  api.startPracticeSession.mockReset();
  api.submitPracticeTurn.mockReset();
  api.endPracticeSession.mockReset();
  api.startPracticeSession.mockResolvedValue(SESIUNE_DESCHISA);
});

afterEach(cleanup);

async function porneste() {
  render(<PracticeWorkspace projectId="proiect-1" />);
  fireEvent.click(screen.getByRole("button", { name: "Începe conversația" }));
  await waitFor(() => expect(api.startPracticeSession).toHaveBeenCalled());
}

describe("PracticeWorkspace — drumul înapoi", () => {
  it("dintr-o sesiune deschisă se poate ieși la alegerea modului fără a o închide", async () => {
    // Pana la plicul 34 singura iesire dintr-o sesiune pornita era „Incheie
    // sesiunea". Butonul care ducea inapoi aparea abia dupa ce sesiunea era inchisa.
    await porneste();

    fireEvent.click(screen.getByRole("button", { name: /Înapoi/ }));

    expect(screen.getByText("Alege modul de antrenament")).toBeTruthy();
    // sesiunea NU s-a inchis
    expect(api.endPracticeSession).not.toHaveBeenCalled();
    // si se poate intoarce la ea
    expect(screen.getByText("Ai o sesiune deschisă.")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Întoarce-te la sesiune" }));
    expect(screen.queryByText("Alege modul de antrenament")).toBeNull();
  });

  it("după încheiere, drumul înapoi e primul lucru de pe ecran, iar sinteza rămâne", async () => {
    api.endPracticeSession.mockResolvedValue({
      session: { ...SESIUNE_DESCHISA, state: "closed" },
      summary: "Ai condus discuția calm și ai propus un pas concret.",
    });
    await porneste();

    fireEvent.click(screen.getByRole("button", { name: /Încheie sesiunea/ }));
    await waitFor(() => expect(api.endPracticeSession).toHaveBeenCalled());

    const inapoi = await screen.findByRole("button", { name: /Înapoi la alegerea modului/ });
    const sinteza = screen.getByText("Ai condus discuția calm și ai propus un pas concret.");

    // sinteza ramane vizibila
    expect(sinteza).toBeTruthy();
    // dar drumul inapoi vine INAINTEA ei pe ecran
    expect(inapoi.compareDocumentPosition(sinteza) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();

    fireEvent.click(inapoi);
    expect(screen.getByText("Alege modul de antrenament")).toBeTruthy();
  });
});
