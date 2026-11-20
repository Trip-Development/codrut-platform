import { beforeEach, describe, expect, it, vi } from "vitest";

// Plicul 232: cele trei cereri ale ecranului de obiective. Importul stă în teste,
// ca lipsa fișierului să fie roșul testului.
const http = vi.hoisted(() => ({ apiFetch: vi.fn() }));
vi.mock("./http", () => http);
vi.mock("./runtime", () => ({ getApiBaseUrl: () => "http://test.local/api" }));

function raspuns(corp: unknown, ok = true) {
  return { ok, json: async () => corp } as Response;
}

const ITEM = {
  id: "ob-1",
  nr: 1,
  titlu: "Titlu inventat",
  situatie: "o situație inventată.",
  competente: ["Una"],
  semn_de_reusita: "un semn inventat.",
};

beforeEach(() => http.apiFetch.mockReset());

describe("api/obiective", () => {
  it("getObiectiveleProiectului cere GET …/practice/projects/p/obiective", async () => {
    const { getObiectiveleProiectului } = await import("./obiective");
    http.apiFetch.mockResolvedValue(raspuns({ catalog: "c", catalog_name: "C", obiective: [ITEM] }));

    const lista = await getObiectiveleProiectului("p");

    expect(http.apiFetch).toHaveBeenCalledWith("http://test.local/api/practice/projects/p/obiective");
    expect(lista.catalog).toBe("c");
    expect(lista.obiective[0]).toMatchObject({ id: "ob-1", nr: 1, titlu: "Titlu inventat", situatie: "o situație inventată.", semnDeReusita: "un semn inventat." });
  });

  it("getObiectivulMeu cere GET …/obiectiv", async () => {
    const { getObiectivulMeu } = await import("./obiective");
    http.apiFetch.mockResolvedValue(
      raspuns({ curent: { obiectiv: ITEM, aleasa_la: "2026-11-01T10:00:00Z" }, prima_alegere_la: "2026-10-20T10:00:00Z", istoric: [] }),
    );

    const meu = await getObiectivulMeu("p");

    expect(http.apiFetch).toHaveBeenCalledWith("http://test.local/api/practice/projects/p/obiectiv");
    expect(meu.curent?.obiectiv.id).toBe("ob-1");
    expect(meu.primaAlegereLa).toBe("2026-10-20T10:00:00Z");
  });

  it("alegeObiectivul trimite POST …/obiectiv cu corpul exact {objective_id}", async () => {
    const { alegeObiectivul } = await import("./obiective");
    http.apiFetch.mockResolvedValue(raspuns({ curent: null, prima_alegere_la: null, istoric: [] }));

    await alegeObiectivul("p", "ob-7");

    const [url, init] = http.apiFetch.mock.calls[0];
    expect(url).toBe("http://test.local/api/practice/projects/p/obiectiv");
    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ objective_id: "ob-7" }));
  });

  it("un răspuns ne-ok aruncă eroare, cu mesajul serverului dacă există", async () => {
    const { alegeObiectivul, getObiectiveleProiectului } = await import("./obiective");
    http.apiFetch.mockResolvedValue(raspuns({ error: { code: "x", message: "Mesajul serverului" } }, false));
    await expect(alegeObiectivul("p", "ob-7")).rejects.toThrow("Mesajul serverului");

    http.apiFetch.mockResolvedValue(raspuns({}, false));
    await expect(getObiectiveleProiectului("p")).rejects.toThrow();
  });
});
