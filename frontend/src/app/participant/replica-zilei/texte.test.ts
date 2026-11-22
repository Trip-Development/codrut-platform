import { describe, expect, it } from "vitest";
import { TEXTE, formateazaNota, textulSituatiei } from "./texte";

// Plicul 251, §6.1. Blocul de mai jos e scris de .audit/cody-plic251/unelte/genereaza_texte_test.py
// din J0 (textele plicului, copiate de script, cu T12 = „Ce-i spui?” — corecția 5). Nu se tastează.
const J0_SIMPLE = {
  T1: "Antrenament cu Cody",
  T2: "O replică pe zi",
  T3: "O situație scurtă, o singură replică și răspunsul lui Cody. Durează un minut.",
  T4: "O replică pe zi",
  T5: "Situația de azi te așteaptă. Durează un minut.",
  T6: "Răspunde la situația de azi",
  T7: "Ai trimis replica de azi. Revino mâine.",
  T8: "Vezi răspunsul lui Cody",
  T9: "Situația de azi",
  T12: "Ce-i spui?",
  T13: "Scrie replica ta aici, așa cum ai spune-o cu voce tare.",
  T14: "Ascult... vorbește liber...",
  T15: "Se transcrie mesajul audio...",
  T16: "Vorbește (microfon)",
  T17: "Oprește înregistrarea",
  T18: "Trimite replica",
  T19: "Cody citește replica ta…",
  T20: "Răspunsul lui Cody",
  T22: "Replica ta",
  T23: "Ai terminat replica de azi. Revino mâine pentru situația următoare.",
  T25: "O zi sărită pe săptămână nu rupe seria.",
  T26: "Replica zilei nu e încă pornită pe acest proiect.",
  T27: "Înainte de replica zilei, citește și bifează acordul de pe pagina Exersează.",
  T28: "Înapoi la Exersează",
  T29: "Se încarcă situația de azi…",
  T30: "Nu am putut încărca replica zilei. Încearcă din nou mai târziu.",
  T31: "Replica zilei nu se poate trimite acum: s-a atins limita de cost a programului. Spune-i trainerului tău.",
  T32: "Cody îți răspunde deja în altă fereastră. Așteaptă puțin și încearcă din nou.",
  T33: "Replica e prea lungă. Scurteaz-o și trimite din nou.",
  T34: "Cody e în pauză. Revine în curând.",
  T35: "Nu am putut trimite replica. Încearcă din nou.",
} as const;
const J0_T10 = "Din obiectivul tău: {titlul obiectivului}";
const J0_T11 = "Din trainingul tău: {titlul obiectivului}";
const J0_T21 = "Nota ta: {nota}/10";
const J0_T24 = ["Seria ta: 1 zi", "Seria ta: {n} zile", "Seria ta: {n} de zile"] as const;
// sfârșitul blocului generat

const INTERZISE = ["clasament", "pierdut", "PCM", "360", "HR", "puncte", "Tablou"];

function toateTextele(): string[] {
  return [
    ...Object.values(J0_SIMPLE),
    TEXTE.T10("Spune nu fără vină"),
    TEXTE.T11("Spune nu fără vină"),
    TEXTE.T21("7,5"),
    ...[1, 2, 19, 20, 21, 100, 101, 120].map((n) => TEXTE.T24(n)),
  ];
}

describe("textele „O replică pe zi” — plicul 251", () => {
  it("T1–T35: fiecare text simplu literă cu literă ca în plic (J0)", () => {
    for (const [cheie, text] of Object.entries(J0_SIMPLE)) {
      expect(TEXTE[cheie as keyof typeof J0_SIMPLE], cheie).toBe(text);
    }
    // 35 de chei: 31 simple + T10, T11, T21, T24
    expect(Object.keys(TEXTE).filter((k) => /^T\d+$/.test(k)).sort()).toEqual(
      Array.from({ length: 35 }, (_, i) => `T${i + 1}`).sort(),
    );
  });

  it("T10, T11, T21 cu un exemplu", () => {
    expect(TEXTE.T10("Spune nu fără vină")).toBe(J0_T10.replace("{titlul obiectivului}", "Spune nu fără vină"));
    expect(TEXTE.T11("Spune nu fără vină")).toBe(J0_T11.replace("{titlul obiectivului}", "Spune nu fără vină"));
    expect(TEXTE.T21("7,5")).toBe(J0_T21.replace("{nota}", "7,5"));
  });

  it("T24: 1 zi, zile, de zile", () => {
    const [unu, zile, deZile] = J0_T24;
    const cu = (sablon: string, n: number) => sablon.replace("{n}", String(n));
    expect(TEXTE.T24(1)).toBe(unu);
    expect(TEXTE.T24(2)).toBe(cu(zile, 2));
    expect(TEXTE.T24(19)).toBe(cu(zile, 19));
    expect(TEXTE.T24(20)).toBe(cu(deZile, 20));
    expect(TEXTE.T24(21)).toBe(cu(deZile, 21));
    expect(TEXTE.T24(100)).toBe(cu(deZile, 100));
    expect(TEXTE.T24(101)).toBe(cu(zile, 101));
    expect(TEXTE.T24(120)).toBe(cu(deZile, 120));
  });

  it("diacritice cu virgulă, nu cu sedilă", () => {
    for (const text of toateTextele()) expect(/[şţŞŢ]/.test(text), text).toBe(false);
  });

  it("niciun cuvânt interzis (vorbă întreagă, literele exact)", () => {
    for (const text of toateTextele()) {
      for (const cuvant of INTERZISE) {
        expect(new RegExp(`(^|[^\\p{L}\\p{N}])${cuvant}($|[^\\p{L}\\p{N}])`, "u").test(text), `${cuvant} în „${text}”`).toBe(false);
      }
    }
  });

  it("nota: o zecimală, virgulă, fără „,0”", () => {
    expect(formateazaNota(7)).toBe("7");
    expect(formateazaNota(7.5)).toBe("7,5");
    expect(formateazaNota(8.0)).toBe("8");
    expect(formateazaNota(6.25)).toBe("6,3");
  });

  it("K1: situația începe cu literă mare la afișare; textul din bază nu se schimbă", () => {
    const dinBaza = "cineva îți cere ceva ce nu poți face";
    expect(textulSituatiei(dinBaza)).toBe("Cineva îți cere ceva ce nu poți face");
    expect(textulSituatiei("Șeful îți cere")).toBe("Șeful îți cere");
    expect(textulSituatiei("ștefan îți cere")).toBe("Ștefan îți cere");
    expect(dinBaza).toBe("cineva îți cere ceva ce nu poți face");
  });
});
