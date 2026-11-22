// Plicul 252: textele notificării zilnice, aprobate de Andrei (22 nov 09:14, Mostre m09,
// [notificare-texte]), literă cu literă. Nu se reformulează aici. T16 și T17 sunt scrise și în
// `public/sw.js` (testul le compară). {ora} se completează numai prin funcțiile de mai jos.

export const TEXTE_NOTIFICARE = {
  T1: "Notificarea zilnică",
  T2: "Îți putem aminti o dată pe zi de situația zilei, la ora pe care o alegi. Notificarea e oprită până o pornești tu.",
  T3: "Ora",
  T4: "{ora}:00",
  T5: "Pornește notificarea",
  T6: "Se pornește…",
  T7: "Notificarea e pornită: în fiecare zi la {ora}:00.",
  T8: "Dacă ai trimis deja replica de azi, nu te mai anunțăm.",
  T9: "Oprește notificarea",
  T10: "Pe iPhone, notificarea merge numai dacă deschizi Cody de pe ecranul principal. În Safari apasă Partajează, apoi «Adaugă pe ecranul principal».",
  T11: "Pe acest telefon sau în acest browser, Cody nu poate trimite notificări.",
  T12: "Notificările pentru Cody sunt blocate. Le poți permite din setările telefonului, apoi încearcă din nou.",
  T13: "Nu am putut porni notificarea. Încearcă din nou.",
  T14: "Nu am putut opri notificarea. Încearcă din nou.",
  T15: "Notificarea nu conține numele tău și nici replicile tale.",
  T16: "O replică pe zi",
  T17: "Situația de azi te așteaptă. Durează un minut.",
} as const;

export function textulOrei(ora: number): string {
  return TEXTE_NOTIFICARE.T4.replace("{ora}", String(ora));
}

export function textulPornita(ora: number): string {
  return TEXTE_NOTIFICARE.T7.replace("{ora}", String(ora));
}
