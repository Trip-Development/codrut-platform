import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TEXTE, formateazaNota } from "./texte";

// Plicul 267, §6.2: răspunsul profesorului vine din fundal. Ceasuri false, API prefăcut: niciun apel real.
const api = vi.hoisted(() => ({ getReplicaZilei: vi.fn(), trimiteReplicaZilei: vi.fn() }));
vi.mock("@/api/replicaZilei", () => api);
vi.mock("@/hooks/useVoiceToText", () => ({
  useVoiceToText: () => ({
    isListening: false,
    isTranscribing: false,
    transcript: "",
    error: null,
    startListening: vi.fn(),
    stopListening: vi.fn(),
    resetTranscript: vi.fn(),
  }),
}));

const SITUATIE = { id: "s-1", text: "cineva îți cere să rămâi peste program.", obiectivNr: 2, obiectivTitlu: "Spune nu fără vină" };
const REPLICA = "Azi nu pot rămâne, mâine da.";
const IN_LUCRU = { situatieId: "s-1", replica: REPLICA, raspuns: "", nota: null, trimisaLa: "2026-11-24T08:00:00Z", inLucru: true };
const GATA = { ...IN_LUCRU, raspuns: "Ai spus clar ce poți. [🏆 Scor: 7.5/10]", nota: 7.5, inLucru: false };
function stare(azi: unknown = null) {
  return { situatie: SITUATIE, motiv: null, dinObiectivulMeu: true, azi, serie: 0 };
}

async function curge(ms = 0) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}
async function randeaza() {
  const { ReplicaZilei } = await import("./ReplicaZilei");
  render(<ReplicaZilei projectId="proiect-1" exerseazaHref="/participant/practice?project=proiect-1" />);
  await curge();
}
async function trimiteReplica() {
  fireEvent.change(screen.getByLabelText(TEXTE.T12), { target: { value: REPLICA } });
  fireEvent.click(screen.getByRole("button", { name: TEXTE.T18 }));
  await curge();
}
const status = () => screen.queryByRole("status");

beforeEach(() => {
  vi.useFakeTimers();
  api.getReplicaZilei.mockReset();
  api.trimiteReplicaZilei.mockReset();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("ReplicaZilei — răspunsul din fundal (plicul 267)", () => {
  it("F1. POST întoarce `inLucru`: T19 cu role=status, replica sub T22; fără T21 și fără formular", async () => {
    api.getReplicaZilei.mockResolvedValue(stare());
    api.trimiteReplicaZilei.mockResolvedValue(stare(IN_LUCRU));
    await randeaza();
    await trimiteReplica();
    expect(status()?.textContent).toBe(TEXTE.T19);
    expect(screen.getByText(TEXTE.T22)).toBeTruthy();
    expect(screen.getByText(REPLICA)).toBeTruthy();
    expect(screen.queryByText(TEXTE.T21(formateazaNota(7.5)))).toBeNull();
    expect(screen.queryByText(TEXTE.T20)).toBeNull();
    expect(screen.queryByLabelText(TEXTE.T12)).toBeNull();
  });

  it("F2. la a doua întrebare vine nota: T21 și T20 cu răspunsul, T19 dispare, întrebările se opresc", async () => {
    api.getReplicaZilei.mockResolvedValueOnce(stare()).mockResolvedValueOnce(stare(IN_LUCRU)).mockResolvedValue(stare(GATA));
    api.trimiteReplicaZilei.mockResolvedValue(stare(IN_LUCRU));
    await randeaza();
    await trimiteReplica();
    await curge(2000);
    await curge(2000);
    expect(screen.getByText(TEXTE.T20)).toBeTruthy();
    expect(screen.getByTestId("raspunsul-lui-cody").textContent).toBe(GATA.raspuns);
    expect(status()).toBeNull();
    const chemari = api.getReplicaZilei.mock.calls.length;
    await curge(10000);
    expect(api.getReplicaZilei.mock.calls.length).toBe(chemari);
  });

  it("F3. întrebarea dă `azi: null`: T35 cu role=alert, formularul revine cu replica în casetă", async () => {
    api.getReplicaZilei.mockResolvedValueOnce(stare()).mockResolvedValue(stare(null));
    api.trimiteReplicaZilei.mockResolvedValue(stare(IN_LUCRU));
    await randeaza();
    await trimiteReplica();
    await curge(2000);
    expect(screen.getByRole("alert").textContent).toBe(TEXTE.T35);
    expect((screen.getByLabelText(TEXTE.T12) as HTMLTextAreaElement).value).toBe(REPLICA);
  });

  it("F4. pagina se încarcă direct cu `inLucru`: întrebările pornesc", async () => {
    api.getReplicaZilei.mockResolvedValueOnce(stare(IN_LUCRU)).mockResolvedValue(stare(GATA));
    await randeaza();
    expect(status()?.textContent).toBe(TEXTE.T19);
    await curge(2000);
    expect(api.getReplicaZilei).toHaveBeenCalledTimes(2);
    expect(screen.getByText(TEXTE.T20)).toBeTruthy();
  });

  it("F5. serverul dă mereu `inLucru`: după 160 s întrebările se opresc și apare T30", async () => {
    api.getReplicaZilei.mockResolvedValue(stare(IN_LUCRU));
    await randeaza();
    await curge(160000);
    await curge(0);
    expect(screen.getByRole("alert").textContent).toBe(TEXTE.T30);
    const chemari = api.getReplicaZilei.mock.calls.length;
    await curge(20000);
    expect(api.getReplicaZilei.mock.calls.length).toBe(chemari);
  });

  it("F6. fără `inLucru`: getReplicaZilei e chemată numai la încărcare", async () => {
    api.getReplicaZilei.mockResolvedValue(stare(GATA));
    await randeaza();
    await curge(30000);
    expect(api.getReplicaZilei).toHaveBeenCalledTimes(1);
  });

  it("F7. întrebările aruncă erori: se încearcă mai departe, fără mesaj, până la limită", async () => {
    api.getReplicaZilei.mockResolvedValueOnce(stare(IN_LUCRU)).mockRejectedValue(new Error("rețea"));
    await randeaza();
    await curge(2000);
    await curge(2000);
    await curge(2000);
    expect(api.getReplicaZilei.mock.calls.length).toBeGreaterThanOrEqual(4);
    expect(screen.queryByRole("alert")).toBeNull();
    expect(status()?.textContent).toBe(TEXTE.T19);
    await curge(160000);
    expect(screen.getByRole("alert").textContent).toBe(TEXTE.T30);
  });
});
