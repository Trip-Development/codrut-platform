import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { PracticeWorkspace } from "./PracticeWorkspace";

// Plicul 232: cartonașul obiectivului în pagina Exersează. Mock-urile sunt copiate din
// PracticeWorkspace.test.tsx, plus cel al obiectivelor.
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
  getPracticeConsent: vi.fn(),
  givePracticeConsent: vi.fn(),
  startPracticeSession: vi.fn(),
  submitPracticeTurn: vi.fn(),
  endPracticeSession: vi.fn(),
  getConversatiaNeincheiata: vi.fn(),
}));

const { PracticeError } = vi.hoisted(() => ({
  PracticeError: class extends Error {
    code: string;
    details: Record<string, unknown>;
    constructor(message: string, code: string, details: Record<string, unknown>) {
      super(message);
      this.code = code;
      this.details = details;
    }
  },
}));

vi.mock("@/api/practice", () => ({ ...api, PracticeError }));

const obiective = vi.hoisted(() => ({
  getObiectiveleProiectului: vi.fn(),
  getObiectivulMeu: vi.fn(),
  alegeObiectivul: vi.fn(),
}));
vi.mock("@/api/obiective", () => obiective);

const ACORD = {
  acordat: false,
  cod: "Fox 34",
  titlu: "Exersează cu Cody",
  paragrafe: ["Un paragraf inventat."],
  bifa: "Am înțeles și vreau să încep.",
  amprenta: "amprenta-textului",
};
const OBIECTIV = { id: "ob-1", nr: 1, titlu: "Un obiectiv inventat", situatie: "o situație inventată.", semnDeReusita: "un semn inventat." };
const HREF = "/participant/obiectiv?project=proiect-1";

beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn();
  api.startPracticeSession.mockReset();
  api.startPracticeSession.mockResolvedValue({ id: "sesiune-1", kind: "roleplay", state: "open", turnCount: 0 });
  api.getPracticeConsent.mockReset();
  api.givePracticeConsent.mockReset();
  api.getPracticeConsent.mockResolvedValue({ ...ACORD, acordat: true });
  api.givePracticeConsent.mockResolvedValue({ ...ACORD, acordat: true });
  api.getConversatiaNeincheiata.mockReset();
  api.getConversatiaNeincheiata.mockResolvedValue(null);
  obiective.getObiectiveleProiectului.mockReset();
  obiective.getObiectivulMeu.mockReset();
  obiective.getObiectiveleProiectului.mockResolvedValue({ catalog: "c", catalogName: "C", obiective: [OBIECTIV] });
  obiective.getObiectivulMeu.mockResolvedValue({
    curent: { obiectiv: OBIECTIV, aleasaLa: "2026-11-19T10:00:00Z" },
    primaAlegereLa: "2026-11-19T10:00:00Z",
    istoric: [],
  });
});
afterEach(cleanup);

describe("PracticeWorkspace — obiectivul", () => {
  it("a. fără obiectivHref nu cere obiectivele și ecranul e cel de azi", async () => {
    render(<PracticeWorkspace projectId="proiect-1" />);
    expect(await screen.findByText("Alege modul de antrenament")).toBeTruthy();
    await waitFor(() => expect(api.getConversatiaNeincheiata).toHaveBeenCalled());
    expect(obiective.getObiectiveleProiectului).not.toHaveBeenCalled();
    expect(screen.queryByText("Obiectivul tău")).toBeNull();
  });

  it("b. cu obiectivHref, cartonașul stă deasupra titlului „Alege modul de antrenament”", async () => {
    render(<PracticeWorkspace projectId="proiect-1" obiectivHref={HREF} />);
    const cartonas = await screen.findByText("Obiectivul tău");
    const titlu = screen.getByText("Alege modul de antrenament");
    expect(cartonas.compareDocumentPosition(titlu) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("c. „Exersează pe obiectiv” pornește rolul, chiar dacă omul selectase quizul", async () => {
    render(<PracticeWorkspace projectId="proiect-1" obiectivHref={HREF} quizEnabled={true} />);
    fireEvent.click(await screen.findByText("Verificăm cât ai reținut"));
    fireEvent.click(await screen.findByRole("button", { name: "Exersează pe obiectiv" }));
    await waitFor(() => expect(api.startPracticeSession).toHaveBeenCalledTimes(1));
    expect(api.startPracticeSession).toHaveBeenCalledWith({ projectId: "proiect-1", kind: "roleplay" });
  });

  it("d. fără acord bifat butonul e oprit; după bifă, acordul se dă întâi", async () => {
    api.getPracticeConsent.mockResolvedValue(ACORD);
    render(<PracticeWorkspace projectId="proiect-1" obiectivHref={HREF} />);
    const buton = await screen.findByRole("button", { name: "Exersează pe obiectiv" });
    await waitFor(() => expect((buton as HTMLButtonElement).disabled).toBe(true));
    expect(screen.getByText("Bifează întâi acordul de mai jos.")).toBeTruthy();

    fireEvent.click(screen.getByRole("checkbox"));
    await waitFor(() => expect((buton as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(buton);
    await waitFor(() => expect(api.startPracticeSession).toHaveBeenCalledTimes(1));
    expect(api.givePracticeConsent).toHaveBeenCalledWith("proiect-1", "amprenta-textului");
    expect(api.givePracticeConsent.mock.invocationCallOrder[0]).toBeLessThan(
      api.startPracticeSession.mock.invocationCallOrder[0],
    );
  });

  it("e. „Începe conversația” pornește cu modul selectat, ca azi", async () => {
    render(<PracticeWorkspace projectId="proiect-1" obiectivHref={HREF} quizEnabled={true} />);
    fireEvent.click(await screen.findByText("Verificăm cât ai reținut"));
    fireEvent.click(screen.getByRole("button", { name: "Începe conversația" }));
    await waitFor(() => expect(api.startPracticeSession).toHaveBeenCalledTimes(1));
    expect(api.startPracticeSession).toHaveBeenCalledWith({ projectId: "proiect-1", kind: "knowledge" });
  });
});
