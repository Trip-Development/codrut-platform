import fs from "node:fs";
import path from "node:path";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Plicul 232: cartonașul obiectivului de pe Exersează. Textele obiectivelor vin din
// JSON-ul din depozit, nu sunt rescrise aici.
const api = vi.hoisted(() => ({
  getObiectiveleProiectului: vi.fn(),
  getObiectivulMeu: vi.fn(),
  alegeObiectivul: vi.fn(),
}));
vi.mock("@/api/obiective", () => api);

type ItemJson = { nr: number; titlu: string; situatie: string; competente: string[]; semn_de_reusita: string };
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

async function randeaza(props: Partial<{ blocat: boolean; onExerseaza: () => void }> = {}) {
  const { ObiectivulCurent } = await import("./ObiectivulCurent");
  return render(
    <ObiectivulCurent
      projectId="proiect-1"
      obiectivHref="/participant/obiectiv?project=proiect-1"
      blocat={props.blocat ?? false}
      onExerseaza={props.onExerseaza ?? vi.fn()}
    />,
  );
}

function lista(obiective = OBIECTIVE, catalog: string | null = "comunicare-asertiva") {
  api.getObiectiveleProiectului.mockResolvedValue({ catalog, catalogName: catalog ? "Comunicare asertivă" : null, obiective });
}
function ales(obiectiv: (typeof OBIECTIVE)[number] | null, primaAlegereLa: string | null = null, aleasaLa = "2026-11-19T10:00:00Z") {
  api.getObiectivulMeu.mockResolvedValue({
    curent: obiectiv ? { obiectiv, aleasaLa } : null,
    primaAlegereLa,
    istoric: [],
  });
}

beforeEach(() => {
  api.getObiectiveleProiectului.mockReset();
  api.getObiectivulMeu.mockReset();
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("ObiectivulCurent", () => {
  it("a. proiect fără listă: nu randează nimic și nu cere obiectivul omului", async () => {
    lista([], null);
    const { container } = await randeaza();
    await waitFor(() => expect(api.getObiectiveleProiectului).toHaveBeenCalledWith("proiect-1"));
    expect(container.innerHTML).toBe("");
    expect(api.getObiectivulMeu).not.toHaveBeenCalled();
  });

  it("b. lista goală sau o eroare la citire: nu randează nimic", async () => {
    lista([]);
    const gol = await randeaza();
    await waitFor(() => expect(api.getObiectiveleProiectului).toHaveBeenCalled());
    expect(gol.container.innerHTML).toBe("");
    cleanup();

    api.getObiectiveleProiectului.mockRejectedValue(new Error("x"));
    const eroare1 = await randeaza();
    await waitFor(() => expect(api.getObiectiveleProiectului).toHaveBeenCalledTimes(2));
    expect(eroare1.container.innerHTML).toBe("");
    cleanup();

    lista();
    api.getObiectivulMeu.mockRejectedValue(new Error("y"));
    const eroare2 = await randeaza();
    await waitFor(() => expect(api.getObiectivulMeu).toHaveBeenCalled());
    expect(eroare2.container.innerHTML).toBe("");
  });

  it("c. fără obiectiv ales: invitația și legătura spre alegere", async () => {
    lista();
    ales(null);
    await randeaza();
    expect(await screen.findByText("Ce vrei să aplici de mâine?")).toBeTruthy();
    expect(screen.getByText("Alege un singur obiectiv din trainingul tău. Îl poți schimba oricând.")).toBeTruthy();
    expect((screen.getByRole("link", { name: "Alege obiectivul" })).getAttribute("href")).toBe("/participant/obiectiv?project=proiect-1");
  });

  it("d. cu obiectivul 1 ales: titlul, situația, semnul, butonul și schimbarea", async () => {
    lista();
    ales(OBIECTIVE[0], "2026-11-19T10:00:00Z");
    await randeaza();
    expect(await screen.findByText("Obiectivul tău")).toBeTruthy();
    expect(screen.getByText(OBIECTIVE[0].titlu)).toBeTruthy();
    expect(screen.getByText("Situația: vineri, 17:00, șeful îți mai dă un raport „urgent”.")).toBeTruthy();
    expect(screen.getByText("A reușit dacă: refuză sau negociază termenul clar, fără justificări lungi.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Exersează pe obiectiv" })).toBeTruthy();
    expect((screen.getByRole("link", { name: "Schimbă obiectivul" })).getAttribute("href")).toBe("/participant/obiectiv?project=proiect-1");
  });

  it("e. un obiectiv fără situație: fără „Situația:”, cu „A reușit dacă:”", async () => {
    lista([...OBIECTIVE, INVENTAT]);
    ales(INVENTAT, "2026-11-19T10:00:00Z");
    await randeaza();
    expect(await screen.findByText("Un obiectiv inventat")).toBeTruthy();
    expect(screen.queryByText(/Situația:/)).toBeNull();
    expect(screen.getByText("A reușit dacă: un semn inventat.")).toBeTruthy();
  });

  it("f. săptămâna se numără de la prima alegere, nu de la obiectivul curent", async () => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date("2026-11-20T10:00:00Z"));
    lista();
    ales(OBIECTIVE[1], "2026-11-05T10:00:00Z", "2026-11-19T10:00:00Z");
    await randeaza();
    expect(await screen.findByText("Săptămâna 3 din 8")).toBeTruthy();
    cleanup();

    ales(OBIECTIVE[1], "2026-09-21T10:00:00Z", "2026-11-19T10:00:00Z");
    await randeaza();
    expect(await screen.findByText("Cele 8 săptămâni s-au încheiat.")).toBeTruthy();
    expect(screen.queryByText(/din 8/)).toBeNull();
  });

  it("g. butonul cheamă onExerseaza o dată; blocat = dezactivat, cu îndemnul la acord", async () => {
    lista();
    ales(OBIECTIVE[0], "2026-11-19T10:00:00Z");
    const onExerseaza = vi.fn();
    await randeaza({ onExerseaza });
    fireEvent.click(await screen.findByRole("button", { name: "Exersează pe obiectiv" }));
    expect(onExerseaza).toHaveBeenCalledTimes(1);
    expect(screen.queryByText("Bifează întâi acordul de mai jos.")).toBeNull();
    cleanup();

    await randeaza({ blocat: true, onExerseaza });
    expect((await screen.findByRole("button", { name: "Exersează pe obiectiv" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText("Bifează întâi acordul de mai jos.")).toBeTruthy();
  });
});
