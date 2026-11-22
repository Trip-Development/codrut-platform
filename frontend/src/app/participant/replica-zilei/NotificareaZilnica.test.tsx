import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PracticeError } from "@/api/practice";
import { TEXTE_NOTIFICARE as T, textulPornita } from "./texte-notificare";

// Plicul 252, §6.3: cartonașul notificării zilnice de pe pagina „O replică pe zi”.
const api = vi.hoisted(() => ({
  getNotificare: vi.fn(),
  stareaNotificarii: vi.fn(),
  pornesteNotificarea: vi.fn(),
  opresteNotificarea: vi.fn(),
}));
vi.mock("@/api/notificareZilnica", () => api);

const br = vi.hoisted(() => {
  class PermisiuneRefuzata extends Error {}
  return {
    PermisiuneRefuzata,
    suportat: vi.fn(),
    eIphoneFaraEcranPrincipal: vi.fn(),
    permisiunea: vi.fn(),
    abonareaDeAcum: vi.fn(),
    aboneaza: vi.fn(),
    dezaboneaza: vi.fn(),
  };
});
vi.mock("@/lib/notificare-browser", () => br);

const E = "https://fcm.googleapis.com/fcm/send/abc";
const INFO = { disponibila: true, cheiePublica: "K", ore: Array.from({ length: 15 }, (_, i) => i + 7) };
const ordine: string[] = [];

async function randeaza() {
  const { NotificareaZilnica } = await import("./NotificareaZilnica");
  const r = render(<NotificareaZilnica projectId="p-1" />);
  await act(async () => {
    await new Promise((f) => setTimeout(f, 0));
  });
  return r;
}

beforeEach(() => {
  ordine.length = 0;
  for (const f of Object.values(api)) f.mockReset();
  for (const f of [br.suportat, br.eIphoneFaraEcranPrincipal, br.permisiunea, br.abonareaDeAcum, br.aboneaza, br.dezaboneaza]) f.mockReset();
  api.getNotificare.mockResolvedValue(INFO);
  br.suportat.mockReturnValue(true);
  br.eIphoneFaraEcranPrincipal.mockReturnValue(false);
  br.permisiunea.mockReturnValue("default");
  br.abonareaDeAcum.mockResolvedValue(null);
  br.aboneaza.mockResolvedValue(E);
  br.dezaboneaza.mockImplementation(async () => {
    ordine.push("dezaboneaza");
  });
  api.opresteNotificarea.mockImplementation(async () => {
    ordine.push("opreste");
  });
  api.pornesteNotificarea.mockImplementation(async (_p: string, _e: string, ora: number) => ({ pornita: true, ora }));
});
afterEach(cleanup);

describe("NotificareaZilnica — plicul 252", () => {
  it("(1) indisponibilă, eroare sau acord lipsă → nimic randat", async () => {
    api.getNotificare.mockResolvedValue({ disponibila: false, cheiePublica: null, ore: [] });
    const a = await randeaza();
    expect(a.container.innerHTML).toBe("");
    cleanup();
    api.getNotificare.mockRejectedValue(new Error("x"));
    const b = await randeaza();
    expect(b.container.innerHTML).toBe("");
    cleanup();
    api.getNotificare.mockRejectedValue(new PracticeError("", "acord_lipsa", {}));
    const c = await randeaza();
    expect(c.container.innerHTML).toBe("");
  });

  it("(2) la deschidere nu cere permisiunea: OPRITĂ, T2, ora 9:00 propusă, T5, T15", async () => {
    await randeaza();
    expect(screen.getByText(T.T1)).toBeTruthy();
    expect(screen.getByText(T.T2)).toBeTruthy();
    expect((screen.getByRole("combobox") as HTMLSelectElement).value).toBe("9");
    expect(screen.getByRole("option", { name: "9:00" })).toBeTruthy();
    expect(screen.getByRole("button", { name: T.T5 })).toBeTruthy();
    expect(screen.getByText(T.T15)).toBeTruthy();
    expect(br.aboneaza).not.toHaveBeenCalled();
    expect(api.pornesteNotificarea).not.toHaveBeenCalled();
  });

  it("(3) T5 → T6, apoi T7 cu ora aleasă, T8, T9; serverul primește ora", async () => {
    let gata: (v: string) => void = () => undefined;
    br.aboneaza.mockReturnValue(new Promise<string>((f) => (gata = f)));
    await randeaza();
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "18" } });
    fireEvent.click(screen.getByRole("button", { name: T.T5 }));
    expect(await screen.findByRole("button", { name: T.T6 })).toBeTruthy();
    await act(async () => gata(E));
    expect(await screen.findByText(textulPornita(18))).toBeTruthy();
    expect(screen.getByText(T.T8)).toBeTruthy();
    expect(screen.getByRole("button", { name: T.T9 })).toBeTruthy();
    expect(api.pornesteNotificarea).toHaveBeenCalledWith("p-1", E, 18);
  });

  it("(4) pornită: schimbarea orei se salvează pe loc și T7 se schimbă", async () => {
    br.abonareaDeAcum.mockResolvedValue(E);
    api.stareaNotificarii.mockResolvedValue({ pornita: true, ora: 9 });
    await randeaza();
    expect(screen.getByText(textulPornita(9))).toBeTruthy();
    await act(async () => {
      fireEvent.change(screen.getByRole("combobox"), { target: { value: "20" } });
    });
    expect(api.pornesteNotificarea).toHaveBeenCalledWith("p-1", E, 20);
    expect(await screen.findByText(textulPornita(20))).toBeTruthy();
  });

  it("(5) T9: dezabonarea ÎNAINTE de server, apoi oprită; serverul pică → tot oprită; dezabonarea pică → T14", async () => {
    br.abonareaDeAcum.mockResolvedValue(E);
    api.stareaNotificarii.mockResolvedValue({ pornita: true, ora: 9 });
    await randeaza();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: T.T9 }));
    });
    expect(ordine).toEqual(["dezaboneaza", "opreste"]);
    expect(screen.getByText(T.T2)).toBeTruthy();
    expect(screen.getByRole("button", { name: T.T5 })).toBeTruthy();
    cleanup();

    api.opresteNotificarea.mockRejectedValue(new Error("server"));
    await randeaza();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: T.T9 }));
    });
    expect(screen.getByRole("button", { name: T.T5 })).toBeTruthy();
    cleanup();

    br.dezaboneaza.mockRejectedValue(new Error("telefon"));
    await randeaza();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: T.T9 }));
    });
    expect(screen.getByText(T.T14)).toBeTruthy();
  });

  it("(6) iPhone din Safari → T10; fără suport → T11; blocat → T12; refuzul serverului → T13 și dezabonare", async () => {
    br.eIphoneFaraEcranPrincipal.mockReturnValue(true);
    br.suportat.mockReturnValue(false);
    await randeaza();
    expect(screen.getByText(T.T10)).toBeTruthy();
    expect(screen.queryByRole("button", { name: T.T5 })).toBeNull();
    cleanup();

    br.eIphoneFaraEcranPrincipal.mockReturnValue(false);
    await randeaza();
    expect(screen.getByText(T.T11)).toBeTruthy();
    cleanup();

    br.suportat.mockReturnValue(true);
    br.permisiunea.mockReturnValue("denied");
    await randeaza();
    expect(screen.getByText(T.T12)).toBeTruthy();
    expect(screen.queryByRole("button", { name: T.T5 })).toBeNull();
    cleanup();

    br.permisiunea.mockReturnValue("default");
    api.pornesteNotificarea.mockRejectedValue(new PracticeError("", "notificare_adresa_necunoscuta", {}));
    await randeaza();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: T.T5 }));
    });
    expect(screen.getByText(T.T13)).toBeTruthy();
    expect(br.dezaboneaza).toHaveBeenCalled();
    expect(screen.getByRole("button", { name: T.T5 })).toBeTruthy();
  });

  it("(7) telefon întâi: fără lățimi fixe, butoane w-full min-h-11, niciun text scris direct", () => {
    const sursa = readFileSync(path.resolve(__dirname, "NotificareaZilnica.tsx"), "utf8");
    expect(sursa).not.toMatch(/w-\[|min-w-\[|width:/);
    const butoane = [...sursa.matchAll(/<Button[^>]*className="([^"]*)"/g)].map((m) => m[1]);
    expect(butoane.length).toBeGreaterThan(0);
    for (const c of butoane) {
      expect(c).toContain("w-full");
      expect(c).toContain("min-h-11");
    }
    for (const text of Object.values(T)) {
      expect(sursa, text).not.toContain(`"${text}"`);
      expect(sursa, text).not.toContain(`>${text}<`);
    }
  });

  it("paza: trainerul, Tabloul și panoul nu știu de notificare", () => {
    const src = path.resolve(__dirname, "../../..");
    const fisiere = (d: string): string[] =>
      existsSync(d)
        ? readdirSync(d).flatMap((n) => {
            const f = path.join(d, n);
            return statSync(f).isDirectory() ? fisiere(f) : [f];
          })
        : [];
    const locuri = [
      ...fisiere(path.join(src, "app", "trainer")),
      path.join(src, "api", "trainer.ts"),
      ...fisiere(path.join(src, "app", "participant", "dashboard")),
      ...fisiere(path.join(src, "app", "participant", "tablou")),
    ].filter((f) => existsSync(f));
    expect(locuri.length).toBeGreaterThan(0);
    // „Notificare” simplu există deja la trainer (o etichetă veche); paza caută numele lui 252.
    for (const f of locuri) {
      const text = readFileSync(f, "utf8");
      for (const nume of ["notificare-zilnica", "notificareZilnica", "NotificareaZilnica", "notificare-browser", "TEXTE_NOTIFICARE"]) {
        expect(text, `${f}: ${nume}`).not.toContain(nume);
      }
    }
  });
});
