/**
 * Texte aprobate de Andrei (panoul din 10 oct: `[culori-texte-noi-live]`, `[mesaje-sub-50]`,
 * `[mesaje-peste-60]`, `[mesaje-deja-puncte]` = da).
 *
 * Plicul 177. Forma mesajului (a) e adaptarea arhitectului după mostra văzută de Andrei
 * („Ultima discuție: nota 55. Încă 5 până la primele puncte.”): „azi” în loc de „ultima discuție”,
 * fiindcă punctele vin din cea mai mare notă a zilei.
 */
import { NOTA_MINIMA } from "@/lib/praguri-puncte";

/** Sub 50 nu se arată — hotărât de Andrei (`[mesaje-sub-50]`). */
export const PRAG_AFISARE_IMPINGERE = 50;

/** (a) pe Tablou: „{Competență}: nota {nota} azi — încă {60 − nota} până la primele puncte”. */
export function textImpingere(competenta: string, nota: number): string {
  return `${competenta}: nota ${nota} azi — încă ${NOTA_MINIMA - nota} până la primele puncte`;
}

/**
 * (a) pe Tablou, pentru cine are deja puncte din alte zile — plicul 193 (`[mesaje-deja-puncte]`):
 * „{Competență}: nota {nota} azi — încă {60 − nota} până la puncte azi”.
 */
export function textImpingereAzi(competenta: string, nota: number): string {
  return `${competenta}: nota ${nota} azi — încă ${NOTA_MINIMA - nota} până la puncte azi`;
}

/** (b) după „Încheie sesiunea”: „+{N} puncte la {competență}”. */
export function textPuncteCastigate(competenta: string, n: number): string {
  return `+${n} puncte la ${competenta}`;
}
