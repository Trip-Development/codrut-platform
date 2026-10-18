/** Textele plicului 177, comparate șir cu șir (inclusiv linia lungă „—” și diacriticele). */
import { describe, expect, it } from "vitest";

import { PRAG_AFISARE_IMPINGERE, textImpingere, textImpingereAzi, textPuncteCastigate } from "./texte-177";

describe("texte-177 — texte aprobate de Andrei (panoul din 10 oct, [mesaje-deja-puncte] = da)", () => {
  it("mesajul (a) și mesajul (b), exact", () => {
    expect(textImpingere("Ascultare activă", 55)).toBe("Ascultare activă: nota 55 azi — încă 5 până la primele puncte");
    expect(textImpingere("Feedback", 59)).toBe("Feedback: nota 59 azi — încă 1 până la primele puncte");
    expect(textPuncteCastigate("Ascultare activă", 15)).toBe("+15 puncte la Ascultare activă");
    expect(PRAG_AFISARE_IMPINGERE).toBe(50);
  });

  it("cine are deja puncte din alte zile: „până la puncte azi” — plicul 193", () => {
    expect(textImpingereAzi("Claritate", 55)).toBe("Claritate: nota 55 azi — încă 5 până la puncte azi");
    expect(textImpingereAzi("Feedback", 59)).toBe("Feedback: nota 59 azi — încă 1 până la puncte azi");
  });
});
