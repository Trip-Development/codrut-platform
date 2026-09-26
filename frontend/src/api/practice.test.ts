import { readFileSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

/**
 * Lacătul: nicio cale relativă în `src/api/practice.ts`.
 *
 * DE CE EXISTĂ, ca să știe cine îl citește peste o lună:
 *
 * Pe 31 august fila „Evoluție competențe" crăpa pe orice proiect, cu
 * „Nu am putut încărca zona trainer, Ref: 1367209788". În jurnalul frontendului:
 *
 *     TypeError: Failed to parse URL from /api/practice/projects/…/evolution
 *     code: 'ERR_INVALID_URL'
 *
 * Cauza: `practice.ts` era singurul fișier din `api/` care scria adresa relativ
 * (`apiFetch("/api/practice/…")`). În browser merge. **Pe server nu**: `fetch` n-are
 * de la ce porni o cale relativă și aruncă înainte să ceară ceva. Restul aplicației
 * folosește `getApiBaseUrl()`, care pe server întoarce o adresă absolută
 * (`INTERNAL_API_BASE_URL`, altfel `http://backend:8000/api`).
 *
 * S-a văzut doar la fila de evoluție fiindcă e singura pagină din zona practice
 * randată pe server; celelalte sunt `"use client"`. Următoarea pagină randată pe
 * server ar fi căzut la fel, și n-am fi știut de ce.
 *
 * ATENȚIE la capcană: `getApiBaseUrl()` **include deja `/api`**. Calea corectă e
 * `${getApiBaseUrl()}/practice/…`, nu `${getApiBaseUrl()}/api/practice/…` — altfel
 * primești 404 și crezi că ai reparat.
 */
const SURSA = readFileSync(join(__dirname, "practice.ts"), "utf8");

describe("practice API paths", () => {
  it("never builds a relative /api path — those throw during server rendering", () => {
    const relative = [...SURSA.matchAll(/apiFetch\(\s*(["'`])\/api\//g)];
    expect(
      relative.map((m) => m[0]),
      "Folosește `${getApiBaseUrl()}/practice/…`. O cale relativă crapă la randarea " +
        "pe server cu ERR_INVALID_URL, cum s-a întâmplat la fila de evoluție.",
    ).toEqual([]);
  });

  it("does not double the /api prefix", () => {
    const doubled = [...SURSA.matchAll(/getApiBaseUrl\(\)\}\/api\//g)];
    expect(
      doubled.map((m) => m[0]),
      "getApiBaseUrl() include deja /api; încă unul dă 404.",
    ).toEqual([]);
  });

  it("routes every call through getApiBaseUrl()", () => {
    const calls = [...SURSA.matchAll(/apiFetch\(\s*[`"']([^`"']*)/g)].map((m) => m[1]);
    expect(calls.length).toBeGreaterThan(0);
    for (const call of calls) {
      expect(call, `apelul "${call}" nu trece prin getApiBaseUrl()`).toContain(
        "${getApiBaseUrl()}",
      );
    }
  });
});
