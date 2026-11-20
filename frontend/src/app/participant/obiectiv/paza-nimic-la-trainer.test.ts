import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

// Plicul 232, paza 7: trainerul și HR-ul nu văd obiectivul nimănui.
const src = path.resolve(__dirname, "..", "..", "..");

function fisiere(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((intrare) => {
    const cale = path.join(dir, intrare.name);
    return intrare.isDirectory() ? fisiere(cale) : [cale];
  });
}
const cod = (cale: string) => /\.(ts|tsx)$/.test(cale);
const test = (cale: string) => /\.test\.(ts|tsx)$/.test(cale);

describe("nimic despre obiectiv la trainer", () => {
  it("partea trainerului nu cere și nu arată obiectivul omului", () => {
    const deVerificat = [
      ...fisiere(path.join(src, "app", "trainer")).filter(cod),
      path.join(src, "api", "trainer.ts"),
      path.join(src, "api", "companies.ts"),
    ];
    const interzise = [/api\/obiective/, /\/obiectiv["?`]/, /objective_id/, /ObiectivulCurent/, /getObiectiv/];
    const gasite = deVerificat.flatMap((cale) => {
      const text = fs.readFileSync(cale, "utf8");
      return interzise.filter((r) => r.test(text)).map((r) => `${path.relative(src, cale)}: ${r}`);
    });
    expect(gasite).toEqual([]);
  });

  it("numai paginile participantului folosesc @/api/obiective", () => {
    const importatori = fisiere(src)
      .filter((cale) => cod(cale) && !test(cale))
      .filter((cale) => fs.readFileSync(cale, "utf8").includes("@/api/obiective"))
      .map((cale) => path.relative(src, cale));
    expect(importatori.length).toBeGreaterThan(0);
    for (const cale of importatori) expect(cale.startsWith(path.join("app", "participant"))).toBe(true);
  });

  it("api/obiective.ts nu vorbește despre trainer, firmă, HR sau export", () => {
    // Cuvântul-cheie TypeScript `export` din declarații nu e „export” de date: fără el
    // modulul n-ar putea da funcțiile ecranului. Se scoate numai el, înainte de căutare.
    const text = fs
      .readFileSync(path.join(src, "api", "obiective.ts"), "utf8")
      .replace(/^export\s+(?:async\s+)?(?:function|type|const|class|interface)\b/gm, "");
    for (const cuvant of ["trainer", "company", "hr", "export"]) {
      expect(new RegExp(`\\b${cuvant}\\b`, "i").test(text), cuvant).toBe(false);
    }
  });
});
