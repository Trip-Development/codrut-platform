// Plicul 251: textele ecranului replicii zilei, aprobate de Andrei (21 nov 21:13, Mostre m08,
// [replica-zilei-texte-ecran]), cu T12 din corecția 5. Nu se reformulează aici.
// Mesajele serverului (S1–S5, plicul 236) și ale microfonului (TEXTE_MICROFON, plicul 170) vin cum sunt.

// „de” când ultimele două cifre sunt 00 sau de la 20 în sus.
function cuDe(n: number): boolean {
  const ultimele = n % 100;
  return ultimele === 0 || ultimele >= 20;
}

export const TEXTE = {
  T1: "Antrenament cu Cody",
  T2: "O replică pe zi",
  T3: "O situație scurtă, o singură replică și răspunsul lui Cody. Durează un minut.",
  T4: "O replică pe zi",
  T5: "Situația de azi te așteaptă. Durează un minut.",
  T6: "Răspunde la situația de azi",
  T7: "Ai trimis replica de azi. Revino mâine.",
  T8: "Vezi răspunsul lui Cody",
  T9: "Situația de azi",
  T10: (titlu: string) => `Din obiectivul tău: ${titlu}`,
  T11: (titlu: string) => `Din trainingul tău: ${titlu}`,
  T12: "Ce-i spui?",
  T13: "Scrie replica ta aici, așa cum ai spune-o cu voce tare.",
  T14: "Ascult... vorbește liber...",
  T15: "Se transcrie mesajul audio...",
  T16: "Vorbește (microfon)",
  T17: "Oprește înregistrarea",
  T18: "Trimite replica",
  T19: "Cody citește replica ta…",
  T20: "Răspunsul lui Cody",
  T21: (nota: string) => `Nota ta: ${nota}/10`,
  T22: "Replica ta",
  T23: "Ai terminat replica de azi. Revino mâine pentru situația următoare.",
  T24: (n: number) => (n === 1 ? "Seria ta: 1 zi" : cuDe(n) ? `Seria ta: ${n} de zile` : `Seria ta: ${n} zile`),
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

/** Nota cu o zecimală, virgulă în loc de punct, fără „,0” (7 → „7”, 7.5 → „7,5”). */
export function formateazaNota(nota: number): string {
  return String(Math.round(nota * 10) / 10).replace(".", ",");
}

/** K1 (Andrei, 21 nov): prima literă mare la afișare; textul din bază rămâne cum e. */
export function textulSituatiei(text: string): string {
  return text ? text.charAt(0).toLocaleUpperCase("ro-RO") + text.slice(1) : text;
}
