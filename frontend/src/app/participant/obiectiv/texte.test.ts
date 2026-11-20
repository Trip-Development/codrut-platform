import { describe, expect, it } from "vitest";

// Plicul 232: textele de pe ecran, aprobate de Andrei (20 nov, [obiective-texte-ecran]),
// caracter cu caracter.
describe("textele obiectivului", () => {
  it("sunt exact cele aprobate", async () => {
    const { TEXTE } = await import("./texte");
    expect(TEXTE.T1).toBe("Ce vrei să aplici de mâine?");
    expect(TEXTE.T2).toBe("Alege un singur obiectiv din trainingul tău. Îl poți schimba oricând.");
    expect(TEXTE.T3).toBe("Alege obiectivul");
    expect(TEXTE.T4).toBe("Obiectivul tău");
    expect(TEXTE.T5(3)).toBe("Săptămâna 3 din 8");
    expect(TEXTE.T6).toBe("Cele 8 săptămâni s-au încheiat.");
    expect(TEXTE.T7("x.")).toBe("Situația: x.");
    expect(TEXTE.T8("y.")).toBe("A reușit dacă: y.");
    expect(TEXTE.T9).toBe("Exersează pe obiectiv");
    expect(TEXTE.T10).toBe("Schimbă obiectivul");
    expect(TEXTE.T11).toBe("Bifează întâi acordul de mai jos.");
    expect(TEXTE.T12).toEqual({
      eyebrow: "Antrenament cu Cody",
      title: "Ce vrei să aplici de mâine?",
      description: "Alege obiectivul pe care îl aplici în cele 8 săptămâni de după training. Îl poți schimba oricând.",
    });
    expect(TEXTE.T13).toBe("Aleg acest obiectiv");
    expect(TEXTE.T14).toBe("Obiectivul tău acum");
    expect(TEXTE.T16).toBe("Nu am putut salva alegerea. Încearcă din nou.");
    expect(TEXTE.T17).toBe("Nu am putut încărca obiectivele. Încearcă din nou mai târziu.");
    expect(TEXTE.T18).toBe("Trainingul tău nu are încă obiective de ales.");
    expect(TEXTE.T19).toBe("Înapoi la Exersează");
    expect(TEXTE.T20).toBe("Se încarcă obiectivele…");
  });

  it("au diacritice cu virgulă și niciun cuvânt interzis", async () => {
    const { TEXTE } = await import("./texte");
    const toate = Object.values(TEXTE)
      .map((t) => (typeof t === "function" ? t(1 as never) : typeof t === "string" ? t : Object.values(t).join(" ")))
      .join(" ");
    expect(toate).not.toMatch(/[şţŞŢ]/);
    for (const interzis of ["PCM", "360", "notă", "evaluare", "HR"]) {
      expect(toate).not.toContain(interzis);
    }
  });
});
