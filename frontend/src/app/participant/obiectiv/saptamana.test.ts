import { describe, expect, it } from "vitest";

// Plicul 232: săptămâna din cele 8, numărată pe calendarul de la București.
async function s(prima: string, acum: string) {
  const { saptamanaDin8 } = await import("./saptamana");
  return saptamanaDin8(prima, new Date(acum));
}

describe("saptamanaDin8", () => {
  it("numără săptămânile de la prima alegere", async () => {
    expect(await s("2026-11-02T09:00:00Z", "2026-11-02T15:00:00Z")).toBe(1);
    expect(await s("2026-11-02T09:00:00Z", "2026-11-08T09:00:00Z")).toBe(1);
    expect(await s("2026-11-02T09:00:00Z", "2026-11-09T09:00:00Z")).toBe(2);
    expect(await s("2026-11-02T09:00:00Z", "2026-12-21T09:00:00Z")).toBe(8);
    expect(await s("2026-11-02T09:00:00Z", "2026-12-27T09:00:00Z")).toBe(8);
    expect(await s("2026-11-02T09:00:00Z", "2026-12-28T09:00:00Z")).toBeNull();
  });

  it("o dată din viitor e săptămâna 1", async () => {
    expect(await s("2026-11-10T09:00:00Z", "2026-11-02T09:00:00Z")).toBe(1);
  });

  it("23:30 ora României și a doua zi 00:30 înseamnă zi nouă", async () => {
    const { zileLaBucuresti } = await import("./saptamana");
    // 23:30 la București (UTC+2 în noiembrie) = 21:30 UTC; 00:30 = 22:30 UTC
    expect(zileLaBucuresti("2026-11-02T21:30:00Z", new Date("2026-11-02T22:30:00Z"))).toBe(1);
  });

  it("trecerea la ora de iarnă nu mută numărul", async () => {
    // ultima duminică din octombrie 2026 = 25 oct
    expect(await s("2026-10-19T09:00:00Z", "2026-10-26T09:00:00Z")).toBe(2);
    expect(await s("2026-10-19T09:00:00Z", "2026-10-25T22:30:00Z")).toBe(2);
    expect(await s("2026-10-19T09:00:00Z", "2026-10-25T21:30:00Z")).toBe(1);
  });
});
