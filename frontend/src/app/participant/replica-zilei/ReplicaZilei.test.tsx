import fs from "node:fs";
import path from "node:path";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PracticeError } from "@/api/practice";
import { TEXTE } from "./texte";

// Plicul 251, §6.3: ecranul „O replică pe zi”. API-ul și microfonul sunt prefăcute: niciun apel real.
const api = vi.hoisted(() => ({ getReplicaZilei: vi.fn(), trimiteReplicaZilei: vi.fn() }));
vi.mock("@/api/replicaZilei", () => api);

type OptiuniVoce = { onTranscript?: (t: string) => void; onError?: (e: string, pentruOm?: boolean) => void };
const voce = vi.hoisted(() => ({
  optiuni: null as OptiuniVoce | null,
  asculta: false,
  transcrie: false,
  porneste: vi.fn(),
  opreste: vi.fn(),
}));
vi.mock("@/hooks/useVoiceToText", () => ({
  useVoiceToText: (optiuni: OptiuniVoce) => {
    voce.optiuni = optiuni;
    return {
      isListening: voce.asculta,
      isTranscribing: voce.transcrie,
      transcript: "",
      error: null,
      startListening: voce.porneste,
      stopListening: voce.opreste,
      resetTranscript: vi.fn(),
    };
  },
}));

const EXERSEAZA = "/participant/practice?project=proiect-1";
const SITUATIE = { id: "s-1", text: "cineva îți cere să rămâi peste program.", obiectivNr: 2, obiectivTitlu: "Spune nu fără vină" };
const AZI = {
  situatieId: "s-1",
  replica: "Azi nu pot rămâne.",
  raspuns: "Ai spus clar ce nu poți.\n\nÎncearcă și o variantă cu ce poți.\n[🏆 Scor: 7.5/10]",
  nota: 7.5,
  trimisaLa: "2026-11-22T08:00:00Z",
};
function stare(extra: Record<string, unknown> = {}) {
  return { situatie: SITUATIE, motiv: null, dinObiectivulMeu: true, azi: null, serie: 0, ...extra };
}

async function randeaza() {
  const { ReplicaZilei } = await import("./ReplicaZilei");
  return render(<ReplicaZilei projectId="proiect-1" exerseazaHref={EXERSEAZA} />);
}
const caseta = () => screen.getByLabelText(TEXTE.T12) as HTMLTextAreaElement;
const butonul = () => screen.getByRole("button", { name: TEXTE.T18 });
async function scrieSiTrimite(text: string) {
  fireEvent.change(caseta(), { target: { value: text } });
  fireEvent.click(butonul());
}

beforeEach(() => {
  api.getReplicaZilei.mockReset();
  api.trimiteReplicaZilei.mockReset();
  voce.optiuni = null;
  voce.asculta = false;
  voce.transcrie = false;
  voce.porneste.mockReset();
  voce.opreste.mockReset();
});
afterEach(cleanup);

describe("ReplicaZilei — plicul 251", () => {
  it("1. fără `azi`: T9, T10 sau T11, situația, caseta, T18 blocat cât e goală", async () => {
    api.getReplicaZilei.mockResolvedValue(stare());
    await randeaza();
    expect(screen.getByText(TEXTE.T29)).toBeTruthy();
    await screen.findByText(TEXTE.T9);
    expect(screen.getByText(TEXTE.T10("Spune nu fără vină"))).toBeTruthy();
    expect(screen.queryByText(TEXTE.T11("Spune nu fără vină"))).toBeNull();
    expect(screen.getByText("Cineva îți cere să rămâi peste program.")).toBeTruthy();
    expect(caseta().placeholder).toBe(TEXTE.T13);
    expect((butonul() as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(caseta(), { target: { value: "   " } });
    expect((butonul() as HTMLButtonElement).disabled).toBe(true);
    fireEvent.change(caseta(), { target: { value: "Azi nu pot." } });
    expect((butonul() as HTMLButtonElement).disabled).toBe(false);
    expect(api.getReplicaZilei).toHaveBeenCalledWith("proiect-1");

    cleanup();
    api.getReplicaZilei.mockResolvedValue(stare({ dinObiectivulMeu: false }));
    await randeaza();
    await screen.findByText(TEXTE.T11("Spune nu fără vină"));
    expect(screen.queryByText(TEXTE.T10("Spune nu fără vină"))).toBeNull();
  });

  it("2. trimiterea: T19 cât așteaptă, apoi nota, răspunsul întreg, replica, T23; caseta și T18 dispar", async () => {
    api.getReplicaZilei.mockResolvedValue(stare());
    let gata: (v: unknown) => void = () => {};
    api.trimiteReplicaZilei.mockReturnValue(new Promise((r) => (gata = r)));
    await randeaza();
    await screen.findByText(TEXTE.T9);
    await scrieSiTrimite("Azi nu pot rămâne.");
    expect(api.trimiteReplicaZilei).toHaveBeenCalledWith("proiect-1", "s-1", "Azi nu pot rămâne.");
    expect(screen.getByText(TEXTE.T19)).toBeTruthy();
    expect(caseta().disabled).toBe(true);
    expect((butonul() as HTMLButtonElement).disabled).toBe(true);

    await act(async () => gata(stare({ azi: AZI, serie: 1 })));
    await screen.findByText(TEXTE.T21("7,5"));
    expect(screen.getByText(TEXTE.T20)).toBeTruthy();
    const raspuns = screen.getByTestId("raspunsul-lui-cody");
    expect(raspuns.textContent).toBe(AZI.raspuns);
    expect(raspuns.className).toContain("whitespace-pre-wrap");
    expect(screen.getByText(TEXTE.T22)).toBeTruthy();
    expect(screen.getByText("Azi nu pot rămâne.")).toBeTruthy();
    expect(screen.getByText(TEXTE.T23)).toBeTruthy();
    expect(screen.queryByLabelText(TEXTE.T12)).toBeNull();
    expect(screen.queryByRole("button", { name: TEXTE.T18 })).toBeNull();
    expect(screen.queryByText(TEXTE.T19)).toBeNull();
  });

  it("2b. nota 7 se scrie „7”, fără „,0”", async () => {
    api.getReplicaZilei.mockResolvedValue(stare({ azi: { ...AZI, nota: 7 } }));
    await randeaza();
    await screen.findByText(TEXTE.T21("7"));
  });

  it("3. `nota: null` → fără rândul T21, restul la fel", async () => {
    api.getReplicaZilei.mockResolvedValue(stare());
    api.trimiteReplicaZilei.mockResolvedValue(stare({ azi: { ...AZI, nota: null } }));
    await randeaza();
    await screen.findByText(TEXTE.T9);
    await scrieSiTrimite("Azi nu pot rămâne.");
    await screen.findByText(TEXTE.T23);
    expect(screen.queryByText(/^Nota ta:/)).toBeNull();
    expect(screen.getByText(TEXTE.T20)).toBeTruthy();
    expect(screen.getByTestId("raspunsul-lui-cody").textContent).toBe(AZI.raspuns);
    expect(screen.getByText(TEXTE.T22)).toBeTruthy();
  });

  it("4. cu `azi` la deschidere → direct rezultatul, fără casetă", async () => {
    api.getReplicaZilei.mockResolvedValue(stare({ azi: AZI }));
    await randeaza();
    await screen.findByText(TEXTE.T23);
    expect(screen.queryByLabelText(TEXTE.T12)).toBeNull();
    expect(screen.queryByRole("button", { name: TEXTE.T18 })).toBeNull();
    expect(api.trimiteReplicaZilei).not.toHaveBeenCalled();
  });

  it("5. seria: 0 → fără T24/T25; 3 → „Seria ta: 3 zile” + T25", async () => {
    api.getReplicaZilei.mockResolvedValue(stare({ serie: 0 }));
    await randeaza();
    await screen.findByText(TEXTE.T9);
    expect(screen.queryByText(/^Seria ta:/)).toBeNull();
    expect(screen.queryByText(TEXTE.T25)).toBeNull();

    cleanup();
    api.getReplicaZilei.mockResolvedValue(stare({ serie: 3 }));
    await randeaza();
    await screen.findByText(TEXTE.T24(3));
    expect(TEXTE.T24(3)).toBe("Seria ta: 3 zile");
    expect(screen.getByText(TEXTE.T25)).toBeTruthy();
  });

  const REFUZURI: Array<[string, string, string]> = [
    ["situatia_alta", "Situația de azi s-a schimbat. Reîncarcă pagina.", "Situația de azi s-a schimbat. Reîncarcă pagina."],
    ["replica_goala", "Scrie replica ta înainte să trimiți.", "Scrie replica ta înainte să trimiți."],
    ["replica_zilei_indisponibila", "Pe acest proiect nu există încă replica zilei.", "Pe acest proiect nu există încă replica zilei."],
    ["profesor_indisponibil", "Cody nu poate răspunde acum. Replica ta nu s-a salvat; încearcă din nou.", "Cody nu poate răspunde acum. Replica ta nu s-a salvat; încearcă din nou."],
    ["acord_lipsa", "Acordul lipsește.", TEXTE.T27],
    ["practice_not_enabled", "Practice is not enabled.", TEXTE.T34],
    ["budget_exceeded", "Budget exceeded.", TEXTE.T31],
    ["practice_busy", "Busy.", TEXTE.T32],
    ["practice_turn_too_long", "Too long.", TEXTE.T33],
    ["altceva", "Something else.", TEXTE.T35],
  ];
  for (const [cod, mesajServer, peEcran] of REFUZURI) {
    it(`6. refuzul ${cod} → „${peEcran}”, replica rămâne în casetă`, async () => {
      api.getReplicaZilei.mockResolvedValue(stare());
      api.trimiteReplicaZilei.mockRejectedValue(new PracticeError(mesajServer, cod, {}));
      await randeaza();
      await screen.findByText(TEXTE.T9);
      await scrieSiTrimite("Azi nu pot rămâne.");
      await screen.findByText(peEcran);
      expect(caseta().value).toBe("Azi nu pot rămâne.");
      expect((butonul() as HTMLButtonElement).disabled).toBe(false);
    });
  }

  it("6b. o eroare de rețea la trimitere → T35, replica rămâne", async () => {
    api.getReplicaZilei.mockResolvedValue(stare());
    api.trimiteReplicaZilei.mockRejectedValue(new TypeError("Failed to fetch"));
    await randeaza();
    await screen.findByText(TEXTE.T9);
    await scrieSiTrimite("Azi nu pot rămâne.");
    await screen.findByText(TEXTE.T35);
    expect(caseta().value).toBe("Azi nu pot rămâne.");
  });

  it("6c. `replica_zilei_facuta` → fără eroare, se cere starea din nou și se arată rezultatul", async () => {
    api.getReplicaZilei.mockResolvedValueOnce(stare()).mockResolvedValueOnce(stare({ azi: AZI }));
    api.trimiteReplicaZilei.mockRejectedValue(new PracticeError("Ai trimis deja replica de azi.", "replica_zilei_facuta", {}));
    await randeaza();
    await screen.findByText(TEXTE.T9);
    await scrieSiTrimite("Altă replică.");
    await screen.findByText(TEXTE.T23);
    expect(api.getReplicaZilei).toHaveBeenCalledTimes(2);
    expect(screen.queryByText("Ai trimis deja replica de azi.")).toBeNull();
    expect(screen.getByTestId("raspunsul-lui-cody").textContent).toBe(AZI.raspuns);
  });

  it("7. `fara_obiective` / `fara_situatii` → T26 + T28; `acord_lipsa` la încărcare → T27 + T28; altă eroare → T30", async () => {
    for (const motiv of ["fara_obiective", "fara_situatii"]) {
      api.getReplicaZilei.mockResolvedValue(stare({ situatie: null, motiv }));
      await randeaza();
      await screen.findByText(TEXTE.T26);
      expect(screen.getByRole("link", { name: TEXTE.T28 }).getAttribute("href")).toBe(EXERSEAZA);
      expect(screen.queryByLabelText(TEXTE.T12)).toBeNull();
      cleanup();
    }
    api.getReplicaZilei.mockRejectedValue(new PracticeError("Acord.", "acord_lipsa", {}));
    await randeaza();
    await screen.findByText(TEXTE.T27);
    expect(screen.getByRole("link", { name: TEXTE.T28 }).getAttribute("href")).toBe(EXERSEAZA);
    cleanup();

    api.getReplicaZilei.mockRejectedValue(new TypeError("Failed to fetch"));
    await randeaza();
    await screen.findByText(TEXTE.T30);
    cleanup();

    api.getReplicaZilei.mockRejectedValue(new PracticeError("off", "practice_not_enabled", {}));
    await randeaza();
    await screen.findByText(TEXTE.T34);
  });

  it("7b. legătura T28 de jos duce la Exersează", async () => {
    api.getReplicaZilei.mockResolvedValue(stare());
    await randeaza();
    await screen.findByText(TEXTE.T9);
    expect(screen.getByRole("link", { name: TEXTE.T28 }).getAttribute("href")).toBe(EXERSEAZA);
  });

  it("8. microfonul: textul transcris se adaugă în casetă, nu se trimite singur", async () => {
    api.getReplicaZilei.mockResolvedValue(stare());
    await randeaza();
    await screen.findByText(TEXTE.T9);
    const mic = screen.getByRole("button", { name: TEXTE.T16 });
    expect(mic.getAttribute("title")).toBe(TEXTE.T16);
    fireEvent.click(mic);
    expect(voce.porneste).toHaveBeenCalledTimes(1);
    fireEvent.change(caseta(), { target: { value: "Azi" } });
    act(() => voce.optiuni?.onTranscript?.("nu pot rămâne."));
    await waitFor(() => expect(caseta().value).toBe("Azi nu pot rămâne."));
    expect(api.trimiteReplicaZilei).not.toHaveBeenCalled();
  });

  it("8b. cât ascultă: T14 în casetă, T17 pe microfon; cât transcrie: T15", async () => {
    api.getReplicaZilei.mockResolvedValue(stare());
    voce.asculta = true;
    await randeaza();
    await screen.findByText(TEXTE.T9);
    expect(caseta().placeholder).toBe(TEXTE.T14);
    const mic = screen.getByRole("button", { name: TEXTE.T17 });
    fireEvent.click(mic);
    expect(voce.opreste).toHaveBeenCalledTimes(1);
    cleanup();

    voce.asculta = false;
    voce.transcrie = true;
    await randeaza();
    await screen.findByText(TEXTE.T9);
    expect(caseta().placeholder).toBe(TEXTE.T15);
    expect(caseta().disabled).toBe(true);
  });

  it("8c. Enter în casetă nu trimite", async () => {
    api.getReplicaZilei.mockResolvedValue(stare());
    await randeaza();
    await screen.findByText(TEXTE.T9);
    fireEvent.change(caseta(), { target: { value: "Azi nu pot." } });
    fireEvent.keyDown(caseta(), { key: "Enter" });
    expect(api.trimiteReplicaZilei).not.toHaveBeenCalled();
  });

  it("9. K1: „cineva îți cere” se vede „Cineva îți cere”", async () => {
    api.getReplicaZilei.mockResolvedValue(stare());
    await randeaza();
    await screen.findByText("Cineva îți cere să rămâi peste program.");
    expect(screen.queryByText("cineva îți cere să rămâi peste program.")).toBeNull();
  });

  it("10. telefon întâi (paza pe cod): fără lățimi fixe; caseta w-full; T18 w-full și min-h-11", async () => {
    for (const fisier of ["ReplicaZilei.tsx", "CartonasulReplicaZilei.tsx"]) {
      const cod = fs.readFileSync(path.join(__dirname, fisier), "utf8");
      for (const interzis of ["w-[", "min-w-[", "width:"]) expect(cod.includes(interzis), `${fisier}: ${interzis}`).toBe(false);
    }
    api.getReplicaZilei.mockResolvedValue(stare());
    await randeaza();
    await screen.findByText(TEXTE.T9);
    expect(caseta().className.split(/\s+/)).toContain("w-full");
    const clase = butonul().className.split(/\s+/);
    expect(clase).toContain("w-full");
    expect(clase).toContain("min-h-11");
  });
});
