// Plicul 232: „Săptămâna X din 8”, numărată de la PRIMA alegere (programul omului, nu
// obiectivul curent), pe calendarul de la București.
const ZI_LA_BUCURESTI = new Intl.DateTimeFormat("en-CA", {
  timeZone: "Europe/Bucharest",
  year: "numeric",
  month: "2-digit",
  day: "2-digit",
});

function ziCalendaristica(moment: Date): number {
  const [an, luna, zi] = ZI_LA_BUCURESTI.format(moment).split("-").map(Number);
  return Date.UTC(an, luna - 1, zi) / 86_400_000;
}

export function zileLaBucuresti(primaAlegereLa: string, acum: Date): number {
  return ziCalendaristica(acum) - ziCalendaristica(new Date(primaAlegereLa));
}

export function saptamanaDin8(primaAlegereLa: string, acum: Date): number | null {
  const zile = zileLaBucuresti(primaAlegereLa, acum);
  if (zile < 0) return 1;
  if (zile >= 56) return null;
  return Math.floor(zile / 7) + 1;
}
