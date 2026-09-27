/**
 * Textele paginii de bun venit — ale lui Andrei, 27 septembrie (plicul 160, partea B).
 *
 * Stau toate aici, într-un singur loc, ca să le poată schimba fără să caute prin cod.
 * Titlul e fără nume și fără poreclă: pagina stă peste ambele proiecte, iar numele ar contrazice
 * anonimatul promis la Cody.
 */
export const BUN_VENIT = {
  titlu: "Bun venit!",
  numarProiecte: (n: number) => `Ești în ${n} proiecte:`,
  tipTraining: "Exersează cu Cody",
  tipAltul: "Chestionare și rezultate",
  buton: "Intră în proiect",
  ajutor: "Poți trece oricând de la un proiect la altul din lista de sus, din meniul din stânga.",
};

export const CITATE: ReadonlyArray<{ text: string; autor: string }> = [
  { text: "„O călătorie de o mie de mile începe cu un singur pas.”", autor: "Lao Zi" },
  { text: "„Cât timp trăiești, învață cum să trăiești.”", autor: "Seneca" },
  {
    text: "„Nu e de ajuns să știi, trebuie să și aplici. Nu e de ajuns să vrei, trebuie să și faci.”",
    autor: "Goethe",
  },
];

/** Citatul zilei: unul din trei, prin rotație după zi. */
export function citatulZilei(acum: Date = new Date()) {
  const zi = Math.floor(acum.getTime() / 86_400_000);
  return CITATE[((zi % CITATE.length) + CITATE.length) % CITATE.length];
}
