/**
 * Texte propuse — Andrei le vede pe probă (STARE `[culori-texte-noi]`). Pe live numai după «da»-ul lui.
 *
 * Plicul 177. Forma mesajului (a) e adaptarea arhitectului după mostra văzută de Andrei
 * („Ultima discuție: nota 55. Încă 5 până la primele puncte.”): „azi” în loc de „ultima discuție”,
 * fiindcă punctele vin din cea mai mare notă a zilei.
 */
import { NOTA_MINIMA } from "@/lib/praguri-puncte";

/** Propunerea arhitectului (ca în 175, §3.D): sub 50 nu se arată — de hotărât de Andrei. */
export const PRAG_AFISARE_IMPINGERE = 50;

/** (a) pe Tablou: „{Competență}: nota {nota} azi — încă {60 − nota} până la primele puncte”. */
export function textImpingere(competenta: string, nota: number): string {
  return `${competenta}: nota ${nota} azi — încă ${NOTA_MINIMA - nota} până la primele puncte`;
}

/** (b) după „Încheie sesiunea”: „+{N} puncte la {competență}”. */
export function textPuncteCastigate(competenta: string, n: number): string {
  return `+${n} puncte la ${competenta}`;
}
