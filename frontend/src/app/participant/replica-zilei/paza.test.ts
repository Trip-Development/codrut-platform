import fs from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

// Plicul 251, §6.5 + corecția 1: replica zilei e numai a omului; textele stau numai în texte.ts.
const src = path.resolve(__dirname, "..", "..", "..");
const aici = __dirname;

function fisiere(dir: string): string[] {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((intrare) => {
    const cale = path.join(dir, intrare.name);
    return intrare.isDirectory() ? fisiere(cale) : [cale];
  });
}
const cod = (cale: string) => /\.(ts|tsx)$/.test(cale);
const test = (cale: string) => /\.test\.(ts|tsx)$/.test(cale);
const citeste = (cale: string) => fs.readFileSync(cale, "utf8");
// Importul textelor e făcut la rulare (nu analizat dinainte), ca primele trei paze să meargă și
// pe baza fără ecran (roșul-înainte, §7): ele nu au nevoie de texte.
const MODULUL_TEXTELOR = "./texte";
async function texte(): Promise<Record<string, unknown>> {
  return ((await import(/* @vite-ignore */ MODULUL_TEXTELOR)) as { TEXTE: Record<string, unknown> }).TEXTE;
}

describe("paza replicii zilei — plicul 251", () => {
  it("partea trainerului nu cere și nu arată replica zilei", () => {
    const deVerificat = [
      ...fisiere(path.join(src, "app", "trainer")).filter(cod),
      path.join(src, "api", "trainer.ts"),
      path.join(src, "api", "companies.ts"),
    ];
    const interzise = ["replica-zilei", "replicaZilei", "ReplicaZilei", "getReplicaZilei"];
    const gasite = deVerificat.flatMap((cale) =>
      interzise.filter((c) => citeste(cale).includes(c)).map((c) => `${path.relative(src, cale)}: ${c}`),
    );
    expect(gasite).toEqual([]);
  });

  it("numai fișiere din app/participant/ importă @/api/replicaZilei", () => {
    const importatori = fisiere(src)
      .filter((cale) => cod(cale) && !test(cale))
      .filter((cale) => citeste(cale).includes("@/api/replicaZilei"))
      .map((cale) => path.relative(src, cale));
    for (const cale of importatori) expect(cale.startsWith(path.join("app", "participant")), cale).toBe(true);
  });

  it("Tabloul și pagina de start a omului nu ating replica zilei; replica zilei nu ia punctele Tabloului", () => {
    const deVerificat = ["dashboard", "tablou"].flatMap((d) => fisiere(path.join(src, "app", "participant", d)).filter(cod));
    for (const cale of deVerificat) {
      const text = citeste(cale);
      expect(text.includes("@/api/replicaZilei"), cale).toBe(false);
      expect(text.includes("replica-zilei"), cale).toBe(false);
    }
    if (fs.existsSync(aici)) {
      for (const cale of fisiere(aici).filter((c) => cod(c) && !test(c))) expect(citeste(cale).includes("texte-177"), cale).toBe(false);
    }
  });

  it("api/replicaZilei.ts nu vorbește despre trainer, firmă, HR sau export", () => {
    // Cuvântul-cheie TypeScript `export` din declarații nu e „export” de date (ca la 232).
    const text = citeste(path.join(src, "api", "replicaZilei.ts")).replace(
      /^export\s+(?:async\s+)?(?:function|type|const|class|interface)\b/gm,
      "",
    );
    for (const cuvant of ["trainer", "company", "hr", "export"]) {
      expect(new RegExp(`\\b${cuvant}\\b`, "i").test(text), cuvant).toBe(false);
    }
  });

  it("meniul omului nu primește intrare nouă", () => {
    expect(citeste(path.join(src, "app", "participant", "participant-context.ts")).includes("replica-zilei")).toBe(false);
  });

  it("corecția 1a: niciun text din TEXTE scris direct în ecrane sau în api", async () => {
    const TEXTE = await texte();
    const bucati: string[] = [];
    for (const [cheie, valoare] of Object.entries(TEXTE)) {
      if (typeof valoare === "string") bucati.push(valoare);
      else if (cheie === "T10") bucati.push("Din obiectivul tău:");
      else if (cheie === "T11") bucati.push("Din trainingul tău:");
      else if (cheie === "T21") bucati.push("Nota ta:");
      else if (cheie === "T24") bucati.push("Seria ta:");
    }
    const ecrane = [
      path.join(aici, "ReplicaZilei.tsx"),
      path.join(aici, "CartonasulReplicaZilei.tsx"),
      path.join(aici, "page.tsx"),
      path.join(src, "api", "replicaZilei.ts"),
    ];
    const gasite = ecrane.flatMap((cale) =>
      bucati.filter((b) => citeste(cale).includes(b)).map((b) => `${path.relative(src, cale)}: „${b}”`),
    );
    expect(gasite).toEqual([]);
  });

  it("corecția 1b: T1, T14–T17, T28, T34 sunt literă cu literă textele de azi", async () => {
    const TEXTE = (await texte()) as Record<string, string>;
    const exerseaza = citeste(path.join(src, "app", "participant", "practice", "PracticeWorkspace.tsx"));
    for (const cheie of ["T14", "T15", "T16", "T17", "T34"]) {
      expect(exerseaza.includes(`"${TEXTE[cheie]}"`), cheie).toBe(true);
    }
    const obiectiv = citeste(path.join(src, "app", "participant", "obiectiv", "texte.ts"));
    expect(obiectiv.includes(`T19: "${TEXTE.T28}"`)).toBe(true);
    const paginaExerseaza = citeste(path.join(src, "app", "participant", "practice", "page.tsx"));
    expect(paginaExerseaza.includes(`"${TEXTE.T1}"`)).toBe(true);
  });
});
