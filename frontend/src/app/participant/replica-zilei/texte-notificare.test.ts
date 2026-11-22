import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { TEXTE_NOTIFICARE, textulOrei, textulPornita } from "./texte-notificare";

// Generat de .audit/cody-plic252/unelte/genereaza_texte_test.py din raw/J0-texte.txt (§5 al plicului 252).
const APROBATE: Record<string, string> = {
  T1: "Notificarea zilnică",
  T2: "Îți putem aminti o dată pe zi de situația zilei, la ora pe care o alegi. Notificarea e oprită până o pornești tu.",
  T3: "Ora",
  T4: "{ora}:00",
  T5: "Pornește notificarea",
  T6: "Se pornește…",
  T7: "Notificarea e pornită: în fiecare zi la {ora}:00.",
  T8: "Dacă ai trimis deja replica de azi, nu te mai anunțăm.",
  T9: "Oprește notificarea",
  T10: "Pe iPhone, notificarea merge numai dacă deschizi Cody de pe ecranul principal. În Safari apasă Partajează, apoi «Adaugă pe ecranul principal».",
  T11: "Pe acest telefon sau în acest browser, Cody nu poate trimite notificări.",
  T12: "Notificările pentru Cody sunt blocate. Le poți permite din setările telefonului, apoi încearcă din nou.",
  T13: "Nu am putut porni notificarea. Încearcă din nou.",
  T14: "Nu am putut opri notificarea. Încearcă din nou.",
  T15: "Notificarea nu conține numele tău și nici replicile tale.",
  T16: "O replică pe zi",
  T17: "Situația de azi te așteaptă. Durează un minut.",
};

const SW = readFileSync(path.resolve(__dirname, "../../../../public/sw.js"), "utf8");

describe("textele notificării zilnice — plicul 252", () => {
  it("T1–T17 sunt exact cele aprobate, literă cu literă", () => {
    expect(Object.keys(TEXTE_NOTIFICARE).sort()).toEqual(Object.keys(APROBATE).sort());
    for (const [cheie, text] of Object.entries(APROBATE)) {
      expect(TEXTE_NOTIFICARE[cheie as keyof typeof TEXTE_NOTIFICARE], cheie).toBe(text);
    }
  });

  it("T4 și T7 cu 7 și 21", () => {
    expect(textulOrei(7)).toBe("7:00");
    expect(textulOrei(21)).toBe("21:00");
    expect(textulPornita(7)).toBe("Notificarea e pornită: în fiecare zi la 7:00.");
    expect(textulPornita(21)).toBe("Notificarea e pornită: în fiecare zi la 21:00.");
  });

  it("diacritice cu virgulă, fără cuvinte interzise", () => {
    const tot = Object.values(TEXTE_NOTIFICARE).join("\n");
    expect(tot).not.toMatch(/[şţŞŢ]/);
    for (const cuvant of ["clasament", "pierdut", "serie", "PCM", "360", "HR", "puncte", "Tablou", "{nume"]) {
      expect(tot.toLowerCase(), cuvant).not.toContain(cuvant.toLowerCase());
    }
  });

  it("sw.js conține T16 și T17 exact o dată fiecare", () => {
    for (const t of [TEXTE_NOTIFICARE.T16, TEXTE_NOTIFICARE.T17]) {
      expect(SW.split(t).length - 1, t).toBe(1);
    }
  });
});
