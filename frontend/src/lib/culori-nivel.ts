/**
 * Culorile celor patru niveluri — plicul 175, paleta A. Numai jetoane din `globals.css`.
 *
 * Ecranul alege culoarea după nivel, nu după `color` venit de la server (acela rămâne pe server,
 * neatins): culorile vechi dădeau text alb pe fond de 3,4–3,9 : 1.
 * `fond` + `text` = eticheta (≥ 4,5 pe ambele teme, verificat în `paleta-a.test.ts`);
 * `punct` = grafică (puncte, bare, legendă); `cerneala` = textul colorat după nivel (scoruri).
 */
export type Nivel = "CONȘTIENTIZARE" | "APLICARE" | "CONSOLIDARE" | "INTEGRARE";

export type CuloareNivel = { fond: string; text: string; punct: string; cerneala: string };

export const CULOARE_NIVEL: Record<Nivel, CuloareNivel> = {
  CONȘTIENTIZARE: {
    fond: "bg-track",
    text: "text-muted-foreground",
    punct: "var(--muted-foreground)",
    cerneala: "var(--muted-foreground)",
  },
  APLICARE: { fond: "bg-gold-soft", text: "text-gold-ink", punct: "var(--gold)", cerneala: "var(--gold-ink)" },
  CONSOLIDARE: {
    fond: "bg-burgundy-soft",
    text: "text-brand-text",
    punct: "var(--burgundy)",
    cerneala: "var(--brand-text)",
  },
  INTEGRARE: {
    fond: "bg-success-soft",
    text: "text-success-ink",
    punct: "var(--brand-green)",
    cerneala: "var(--success-ink)",
  },
};

/** Nivelul vine ca text de la server; un nivel necunoscut se arată ca primul nivel. */
export function culoareNivel(nivel: string): CuloareNivel {
  return CULOARE_NIVEL[nivel as Nivel] ?? CULOARE_NIVEL["CONȘTIENTIZARE"];
}
