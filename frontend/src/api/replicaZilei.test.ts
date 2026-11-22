import { beforeEach, describe, expect, it, vi } from "vitest";
import { PracticeError } from "./practice";

// Plicul 251, §6.2: cele două cereri ale replicii zilei. Importul stă în teste,
// ca lipsa fișierului să fie roșul testului.
const http = vi.hoisted(() => ({ apiFetch: vi.fn() }));
vi.mock("./http", () => http);
vi.mock("./runtime", () => ({ getApiBaseUrl: () => "http://test.local/api" }));

function raspuns(corp: unknown, ok = true) {
  return { ok, json: async () => corp } as Response;
}

const STARE = {
  situatie: { id: "s-1", text: "cineva îți cere ceva.", obiectiv_nr: 3, obiectiv_titlu: "Spune nu" },
  motiv: null,
  din_obiectivul_meu: true,
  azi: {
    situatie_id: "s-1",
    replica: "Nu pot azi.",
    raspuns: "Bine spus.\n[🏆 Scor: 7.5/10]",
    nota: 7.5,
    trimisa_la: "2026-11-22T08:00:00Z",
  },
  serie: 4,
};

beforeEach(() => {
  http.apiFetch.mockReset();
});

describe("api/replicaZilei", () => {
  it("getReplicaZilei cere GET …/practice/projects/p/replica-zilei și mapează în camelCase", async () => {
    const { getReplicaZilei } = await import("./replicaZilei");
    http.apiFetch.mockResolvedValue(raspuns(STARE));

    const stare = await getReplicaZilei("p");

    expect(http.apiFetch).toHaveBeenCalledWith("http://test.local/api/practice/projects/p/replica-zilei");
    expect(stare).toEqual({
      situatie: { id: "s-1", text: "cineva îți cere ceva.", obiectivNr: 3, obiectivTitlu: "Spune nu" },
      motiv: null,
      dinObiectivulMeu: true,
      azi: {
        situatieId: "s-1",
        replica: "Nu pot azi.",
        raspuns: "Bine spus.\n[🏆 Scor: 7.5/10]",
        nota: 7.5,
        trimisaLa: "2026-11-22T08:00:00Z",
      },
      serie: 4,
    });
  });

  it("câmpurile lipsă devin null (situatie, motiv, azi, nota)", async () => {
    const { getReplicaZilei } = await import("./replicaZilei");
    http.apiFetch.mockResolvedValue(raspuns({ din_obiectivul_meu: false, serie: 0, motiv: "fara_obiective" }));

    const stare = await getReplicaZilei("p");

    expect(stare).toEqual({ situatie: null, motiv: "fara_obiective", dinObiectivulMeu: false, azi: null, serie: 0 });
  });

  it("trimiteReplicaZilei cere POST cu corpul {situation_id, replica}", async () => {
    const { trimiteReplicaZilei } = await import("./replicaZilei");
    http.apiFetch.mockResolvedValue(raspuns({ ...STARE, azi: { ...STARE.azi, nota: null } }));

    const stare = await trimiteReplicaZilei("p", "s-1", "Nu pot azi.");

    expect(http.apiFetch).toHaveBeenCalledWith("http://test.local/api/practice/projects/p/replica-zilei", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ situation_id: "s-1", replica: "Nu pot azi." }),
    });
    expect(stare.azi?.nota).toBeNull();
  });

  it("la refuz aruncă PracticeError cu code și message din {error:{code,message}}", async () => {
    const { trimiteReplicaZilei, getReplicaZilei } = await import("./replicaZilei");
    http.apiFetch.mockResolvedValue(
      raspuns({ error: { code: "situatia_alta", message: "Situația de azi s-a schimbat. Reîncarcă pagina.", details: { a: 1 } } }, false),
    );

    const eroare = await trimiteReplicaZilei("p", "s-1", "x").catch((e: unknown) => e);
    expect(eroare).toBeInstanceOf(PracticeError);
    expect((eroare as PracticeError).code).toBe("situatia_alta");
    expect((eroare as PracticeError).message).toBe("Situația de azi s-a schimbat. Reîncarcă pagina.");
    expect((eroare as PracticeError).details).toEqual({ a: 1 });

    http.apiFetch.mockResolvedValue({ ok: false, json: async () => Promise.reject(new Error("nu e json")) } as unknown as Response);
    const faraCorp = await getReplicaZilei("p").catch((e: unknown) => e);
    expect(faraCorp).toBeInstanceOf(PracticeError);
    expect((faraCorp as PracticeError).code).toBe("unknown");
  });
});
