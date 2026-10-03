/** Textele plicului 178, comparate șir cu șir (cu diacritice). */
import { describe, expect, it } from "vitest";

import { DESCRIERE_ALTE_COMPETENTE, TITLU_ALTE_COMPETENTE } from "./texte-178";

describe("texte-178 — texte propuse, Andrei le vede pe probă", () => {
  it("titlul și descrierea, exact", () => {
    expect(TITLU_ALTE_COMPETENTE).toBe("Alte competențe exersate");
    expect(DESCRIERE_ALTE_COMPETENTE).toBe("Nu sunt în lista acestui program, dar punctele lor intră în total.");
  });
});
