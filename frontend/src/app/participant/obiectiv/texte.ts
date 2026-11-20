// Plicul 232: textele de pe ecran ale obiectivului, aprobate de Andrei (20 nov,
// [obiective-texte-ecran]). Nu se reformulează aici.
export const TEXTE = {
  T1: "Ce vrei să aplici de mâine?",
  T2: "Alege un singur obiectiv din trainingul tău. Îl poți schimba oricând.",
  T3: "Alege obiectivul",
  T4: "Obiectivul tău",
  T5: (x: number) => `Săptămâna ${x} din 8`,
  T6: "Cele 8 săptămâni s-au încheiat.",
  T7: (situatie: string) => `Situația: ${situatie}`,
  T8: (semn: string) => `A reușit dacă: ${semn}`,
  T9: "Exersează pe obiectiv",
  T10: "Schimbă obiectivul",
  T11: "Bifează întâi acordul de mai jos.",
  T12: {
    eyebrow: "Antrenament cu Cody",
    title: "Ce vrei să aplici de mâine?",
    description:
      "Alege obiectivul pe care îl aplici în cele 8 săptămâni de după training. Îl poți schimba oricând.",
  },
  T13: "Aleg acest obiectiv",
  T14: "Obiectivul tău acum",
  T16: "Nu am putut salva alegerea. Încearcă din nou.",
  T17: "Nu am putut încărca obiectivele. Încearcă din nou mai târziu.",
  T18: "Trainingul tău nu are încă obiective de ales.",
  T19: "Înapoi la Exersează",
  T20: "Se încarcă obiectivele…",
} as const;
