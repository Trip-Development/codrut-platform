import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { PracticeError } from "@/api/practice";
import { TEXTE } from "./texte";

// Plicul 251, §6.4: cartonașul „O replică pe zi” de pe Exersează.
const api = vi.hoisted(() => ({ getReplicaZilei: vi.fn(), trimiteReplicaZilei: vi.fn() }));
vi.mock("@/api/replicaZilei", () => api);

const HREF = "/participant/replica-zilei?project=proiect-1";
const SITUATIE = { id: "s-1", text: "cineva îți cere ceva.", obiectivNr: 1, obiectivTitlu: "Spune nu" };
const AZI = { situatieId: "s-1", replica: "Nu.", raspuns: "Bine.\n[🏆 Scor: 8/10]", nota: 8, trimisaLa: "2026-11-22T08:00:00Z" };
const stare = (extra: Record<string, unknown> = {}) => ({
  situatie: SITUATIE,
  motiv: null,
  dinObiectivulMeu: true,
  azi: null,
  serie: 5,
  ...extra,
});

async function randeaza() {
  const { CartonasulReplicaZilei } = await import("./CartonasulReplicaZilei");
  return render(<CartonasulReplicaZilei projectId="proiect-1" href={HREF} />);
}

// Corp cu acolade: o funcție întoarsă din beforeEach e chemată de vitest ca „curățenie” după test.
beforeEach(() => {
  api.getReplicaZilei.mockReset();
});
afterEach(cleanup);

describe("CartonasulReplicaZilei — plicul 251", () => {
  it("fără `azi`: T4, T5 și butonul T6 spre pagina replicii zilei", async () => {
    api.getReplicaZilei.mockResolvedValue(stare());
    await randeaza();
    await screen.findByText(TEXTE.T4);
    expect(screen.getByText(TEXTE.T5)).toBeTruthy();
    expect(screen.getByRole("link", { name: TEXTE.T6 }).getAttribute("href")).toBe(HREF);
    expect(screen.queryByText(TEXTE.T7)).toBeNull();
    expect(api.getReplicaZilei).toHaveBeenCalledTimes(1);
    expect(api.getReplicaZilei).toHaveBeenCalledWith("proiect-1");
  });

  it("cu `azi`: T4, T7 și butonul T8", async () => {
    api.getReplicaZilei.mockResolvedValue(stare({ azi: AZI }));
    await randeaza();
    await screen.findByText(TEXTE.T7);
    expect(screen.getByText(TEXTE.T4)).toBeTruthy();
    expect(screen.getByRole("link", { name: TEXTE.T8 }).getAttribute("href")).toBe(HREF);
    expect(screen.queryByText(TEXTE.T5)).toBeNull();
  });

  it("nu arată nici nota, nici seria, nici puncte", async () => {
    api.getReplicaZilei.mockResolvedValue(stare({ azi: AZI }));
    const { container } = await randeaza();
    await screen.findByText(TEXTE.T7);
    const text = container.textContent ?? "";
    expect(text).not.toMatch(/Nota|Scor|Seria|puncte|\/10/);
  });

  const NIMIC: Array<[string, () => void]> = [
    ["situatie: null", () => api.getReplicaZilei.mockResolvedValue(stare({ situatie: null, motiv: "fara_obiective" }))],
    ["eroare de rețea", () => api.getReplicaZilei.mockRejectedValue(new TypeError("Failed to fetch"))],
    ["acord_lipsa", () => api.getReplicaZilei.mockRejectedValue(new PracticeError("Acord.", "acord_lipsa", {}))],
  ];
  for (const [caz, pregateste] of NIMIC) {
    it(`${caz} → nimic randat`, async () => {
      pregateste();
      const { container } = await randeaza();
      await act(async () => {
        await new Promise((r) => setTimeout(r, 0));
      });
      expect(api.getReplicaZilei).toHaveBeenCalledTimes(1);
      expect(container.innerHTML).toBe("");
    });
  }
});
