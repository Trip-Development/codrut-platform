import { beforeEach, describe, expect, it, vi } from "vitest";
import { PracticeError } from "./practice";

// Plicul 252, §6.3: cele patru cereri ale notificării zilnice. Importul stă în teste,
// ca lipsa fișierului să fie roșul testului.
const http = vi.hoisted(() => ({ apiFetch: vi.fn() }));
vi.mock("./http", () => http);
vi.mock("./runtime", () => ({ getApiBaseUrl: () => "http://test.local/api" }));

function raspuns(corp: unknown, ok = true) {
  return { ok, json: async () => corp } as Response;
}

const BAZA = "http://test.local/api/practice/projects/p-1/notificare-zilnica";
const E = "https://fcm.googleapis.com/fcm/send/abc";

beforeEach(() => {
  http.apiFetch.mockReset();
});

describe("api/notificareZilnica — plicul 252", () => {
  it("getNotificare: GET pe adresa proiectului, cheia mapată", async () => {
    const { getNotificare } = await import("./notificareZilnica");
    http.apiFetch.mockResolvedValue(raspuns({ disponibila: true, cheie_publica: "K", ore: [7, 8] }));
    expect(await getNotificare("p-1")).toEqual({ disponibila: true, cheiePublica: "K", ore: [7, 8] });
    expect(http.apiFetch).toHaveBeenCalledWith(BAZA);
  });

  it("stareaNotificarii: POST …/stare cu {endpoint}", async () => {
    const { stareaNotificarii } = await import("./notificareZilnica");
    http.apiFetch.mockResolvedValue(raspuns({ pornita: true, ora: 9 }));
    expect(await stareaNotificarii("p-1", E)).toEqual({ pornita: true, ora: 9 });
    const [url, init] = http.apiFetch.mock.calls[0];
    expect(url).toBe(`${BAZA}/stare`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ endpoint: E });
  });

  it("pornesteNotificarea: PUT cu {endpoint, ora}", async () => {
    const { pornesteNotificarea } = await import("./notificareZilnica");
    http.apiFetch.mockResolvedValue(raspuns({ pornita: true, ora: 18 }));
    expect(await pornesteNotificarea("p-1", E, 18)).toEqual({ pornita: true, ora: 18 });
    const [url, init] = http.apiFetch.mock.calls[0];
    expect(url).toBe(BAZA);
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body)).toEqual({ endpoint: E, ora: 18 });
  });

  it("opresteNotificarea: POST …/opreste cu {endpoint}", async () => {
    const { opresteNotificarea } = await import("./notificareZilnica");
    http.apiFetch.mockResolvedValue({ ok: true, status: 204, json: async () => ({}) } as Response);
    await opresteNotificarea("p-1", E);
    const [url, init] = http.apiFetch.mock.calls[0];
    expect(url).toBe(`${BAZA}/opreste`);
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({ endpoint: E });
  });

  it("refuzul serverului: PracticeError cu codul", async () => {
    const { pornesteNotificarea } = await import("./notificareZilnica");
    http.apiFetch.mockResolvedValue(raspuns({ error: { code: "notificare_ora", message: "x" } }, false));
    const err = await pornesteNotificarea("p-1", E, 6).catch((e) => e);
    expect(err).toBeInstanceOf(PracticeError);
    expect(err.code).toBe("notificare_ora");
  });
});
