/**
 * Pragurile punctelor pe competență — plicul 175 (bara de pe Tablou).
 *
 * Copie a `backend/src/codrut/modules/practice/scoring.py:185-187` — se schimbă împreună.
 * Nivelul mai cere și tipuri de interlocutor (și zile, la Integrare); bara arată numai punctele,
 * iar „De ce nu e mai sus?” spune restul.
 */
export const PRAG_APLICARE = 100;
export const PRAG_CONSOLIDARE = 400;
export const PRAG_INTEGRARE = 1000;

const PRAGUL_URMATOR: Record<string, number | null> = {
  CONȘTIENTIZARE: PRAG_APLICARE,
  APLICARE: PRAG_CONSOLIDARE,
  CONSOLIDARE: PRAG_INTEGRARE,
  INTEGRARE: null,
};

/** Cât din drumul spre pragul nivelului următor, 0–100. La Integrare: 100. */
export function procentPanaLaPragulUrmator(puncte: number, nivel: string): number {
  const prag = PRAGUL_URMATOR[nivel];
  if (prag === null) return 100;
  return Math.max(0, Math.min(100, (puncte / (prag ?? PRAG_APLICARE)) * 100));
}
