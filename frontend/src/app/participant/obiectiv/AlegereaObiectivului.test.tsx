import fs from "node:fs";
import path from "node:path";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useRouter } from "next/navigation";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Plicul 232: ecranul de alegere a obiectivului.
const api = vi.hoisted(() => ({
  getObiectiveleProiectului: vi.fn(),
  getObiectivulMeu: vi.fn(),
  alegeObiectivul: vi.fn(),
}));
vi.mock("@/api/obiective", () => api);

type ItemJson = { nr: number; titlu: string; situatie: string; semn_de_reusita: string };
const JSON_DEPOZIT = JSON.parse(
  fs.readFileSync(
    path.resolve(__dirname, "../../../../../backend/src/codrut/modules/practice/obiective/comunicare-asertiva.json"),
    "utf8",
  ),
) as { obiective: ItemJson[] };
const OBIECTIVE = JSON_DEPOZIT.obiective.map((o) => ({
  id: `ob-${o.nr}`,
  nr: o.nr,
  titlu: o.titlu,
  situatie: o.situatie,
  semnDeReusita: o.semn_de_reusita,
}));
const INVENTAT = { id: "ob-99", nr: 99, titlu: "Un obiectiv inventat", situatie: "", semnDeReusita: "un semn inventat." };
const INAPOI = "/participant/practice?project=proiect-1";

async function randeaza() {
  const { AlegereaObiectivului } = await import("./AlegereaObiectivului");
  return render(<AlegereaObiectivului projectId="proiect-1" inapoiHref={INAPOI} />);
}
function lista(obiective: typeof OBIECTIVE, catalog: string | null = "comunicare-asertiva") {
  // trimise amestecat, ca ordinea pe ecran să vină din `nr`
  api.getObiectiveleProiectului.mockResolvedValue({ catalog, catalogName: null, obiective: [...obiective].reverse() });
}
function ales(obiectiv: (typeof OBIECTIVE)[number] | null) {
  api.getObiectivulMeu.mockResolvedValue({ curent: obiectiv ? { obiectiv, aleasaLa: "2026-11-19T10:00:00Z" } : null, primaAlegereLa: null, istoric: [] });
}
const randuri = () => screen.getAllByRole("listitem");

beforeEach(() => {
  api.getObiectiveleProiectului.mockReset();
  api.getObiectivulMeu.mockReset();
  api.alegeObiectivul.mockReset();
  vi.mocked(useRouter().push).mockReset();
});
afterEach(cleanup);

describe("AlegereaObiectivului", () => {
  it("a. 12 rânduri în ordinea nr, cu situația numai unde există, egale cu JSON-ul", async () => {
    lista([...OBIECTIVE, INVENTAT]);
    ales(null);
    await randeaza();
    await screen.findByText(OBIECTIVE[0].titlu);
    const r = randuri();
    expect(r).toHaveLength(13);
    OBIECTIVE.forEach((o, i) => {
      expect(within(r[i]).getByText(o.titlu)).toBeTruthy();
      expect(within(r[i]).getByText(`Situația: ${o.situatie}`)).toBeTruthy();
      expect(within(r[i]).getByText(`A reușit dacă: ${o.semnDeReusita}`)).toBeTruthy();
    });
    expect(within(r[12]).queryByText(/Situația:/)).toBeNull();
  });

  it("b. butonul de alegere pe fiecare rând; rândul ales are insigna, fără buton", async () => {
    lista(OBIECTIVE);
    ales(null);
    await randeaza();
    expect(await screen.findAllByRole("button", { name: "Aleg acest obiectiv" })).toHaveLength(12);
    cleanup();

    ales(OBIECTIVE[2]);
    await randeaza();
    await screen.findByText(OBIECTIVE[2].titlu);
    const r = randuri();
    expect(within(r[2]).getByText("Obiectivul tău acum")).toBeTruthy();
    expect(within(r[2]).queryByRole("button", { name: "Aleg acest obiectiv" })).toBeNull();
    expect(screen.getAllByRole("button", { name: "Aleg acest obiectiv" })).toHaveLength(11);
  });

  it("c. alegerea trimite un singur POST și întoarce omul pe Exersează", async () => {
    lista(OBIECTIVE);
    ales(null);
    let gata: (v: unknown) => void = () => {};
    api.alegeObiectivul.mockReturnValue(new Promise((r) => (gata = r)));
    await randeaza();
    await screen.findByText(OBIECTIVE[6].titlu);
    const buton7 = within(randuri()[6]).getByRole("button", { name: "Aleg acest obiectiv" });
    fireEvent.click(buton7);
    await waitFor(() => expect((buton7 as HTMLButtonElement).disabled).toBe(true));
    fireEvent.click(buton7);
    expect(api.alegeObiectivul).toHaveBeenCalledTimes(1);
    expect(api.alegeObiectivul).toHaveBeenCalledWith("proiect-1", "ob-7");
    gata({});
    await waitFor(() => expect(useRouter().push).toHaveBeenCalledWith(INAPOI));
  });

  it("d. un refuz arată mesajul, nu mută omul și reactivează butoanele", async () => {
    lista(OBIECTIVE);
    ales(null);
    api.alegeObiectivul.mockRejectedValue(new Error("refuz"));
    await randeaza();
    await screen.findByText(OBIECTIVE[0].titlu);
    fireEvent.click(within(randuri()[0]).getByRole("button", { name: "Aleg acest obiectiv" }));
    expect(await screen.findByText("Nu am putut salva alegerea. Încearcă din nou.")).toBeTruthy();
    expect(useRouter().push).not.toHaveBeenCalled();
    for (const b of screen.getAllByRole("button", { name: "Aleg acest obiectiv" })) expect((b as HTMLButtonElement).disabled).toBe(false);
  });

  it("e. fără listă sau cu eroare: mesajul și legătura înapoi, fără listă", async () => {
    lista([], null);
    ales(null);
    await randeaza();
    expect(await screen.findByText("Trainingul tău nu are încă obiective de ales.")).toBeTruthy();
    expect((screen.getByRole("link", { name: "Înapoi la Exersează" })).getAttribute("href")).toBe(INAPOI);
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
    cleanup();

    lista([]);
    await randeaza();
    expect(await screen.findByText("Trainingul tău nu are încă obiective de ales.")).toBeTruthy();
    cleanup();

    api.getObiectiveleProiectului.mockRejectedValue(new Error("x"));
    await randeaza();
    expect(await screen.findByText("Nu am putut încărca obiectivele. Încearcă din nou mai târziu.")).toBeTruthy();
    expect((screen.getByRole("link", { name: "Înapoi la Exersează" })).getAttribute("href")).toBe(INAPOI);
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });

  it("f. cât se încarcă: mesajul de încărcare", async () => {
    api.getObiectiveleProiectului.mockReturnValue(new Promise(() => {}));
    api.getObiectivulMeu.mockReturnValue(new Promise(() => {}));
    await randeaza();
    expect(await screen.findByText("Se încarcă obiectivele…")).toBeTruthy();
  });
});
