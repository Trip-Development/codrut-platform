export const CANONICAL_COMPETENCIES = [
  "Ascultare activă",
  "Reformulare activă",
  "Verificarea înțelegerii",
  "Exprimarea asertivă a nevoilor și limitelor",
  "Gestionarea propriilor reacții emoționale",
  "Gestionarea reacțiilor celorlalți",
  "Feedback constructiv",
] as const;

export type CanonicalCompetency = (typeof CANONICAL_COMPETENCIES)[number];

export const COMPETENCY_ALIASES: Record<string, string> = {
  // 1. Ascultare activă
  "ascultare activa": "Ascultare activă",
  "ascultare activă": "Ascultare activă",
  "ascultare": "Ascultare activă",
  "active listening": "Ascultare activă",
  "active_listening": "Ascultare activă",
  "active-listening": "Ascultare activă",
  "listening": "Ascultare activă",

  // 2. Reformulare activă
  "reformulare activa": "Reformulare activă",
  "reformulare activă": "Reformulare activă",
  "reformulare": "Reformulare activă",
  "reformularea": "Reformulare activă",
  "active reframing": "Reformulare activă",
  "paraphrasing": "Reformulare activă",
  "reformulation": "Reformulare activă",

  // 3. Verificarea înțelegerii
  "verificarea intelegerii": "Verificarea înțelegerii",
  "verificarea înțelegerii": "Verificarea înțelegerii",
  "verificare intelegere": "Verificarea înțelegerii",
  "verificare înțelegere": "Verificarea înțelegerii",
  "verificarea": "Verificarea înțelegerii",
  "checking understanding": "Verificarea înțelegerii",
  "check understanding": "Verificarea înțelegerii",
  "clarification": "Verificarea înțelegerii",

  // 4. Exprimarea asertivă a nevoilor și limitelor
  "exprimarea asertiva a nevoilor si limitelor": "Exprimarea asertivă a nevoilor și limitelor",
  "exprimarea asertivă a nevoilor și limitelor": "Exprimarea asertivă a nevoilor și limitelor",
  "exprimare asertiva": "Exprimarea asertivă a nevoilor și limitelor",
  "exprimare asertivă": "Exprimarea asertivă a nevoilor și limitelor",
  "asertivitate": "Exprimarea asertivă a nevoilor și limitelor",
  "asertiv": "Exprimarea asertivă a nevoilor și limitelor",
  "assertiveness": "Exprimarea asertivă a nevoilor și limitelor",
  "nevoi si limite": "Exprimarea asertivă a nevoilor și limitelor",
  "nevoi și limite": "Exprimarea asertivă a nevoilor și limitelor",
  "limite": "Exprimarea asertivă a nevoilor și limitelor",

  // 5. Gestionarea propriilor reacții emoționale
  "gestionarea propriilor reactii emotionale": "Gestionarea propriilor reacții emoționale",
  "gestionarea propriilor reacții emoționale": "Gestionarea propriilor reacții emoționale",
  "gestionare emotii proprii": "Gestionarea propriilor reacții emoționale",
  "gestionare emoții proprii": "Gestionarea propriilor reacții emoționale",
  "emotii proprii": "Gestionarea propriilor reacții emoționale",
  "emoții proprii": "Gestionarea propriilor reacții emoționale",
  "reactii emotionale": "Gestionarea propriilor reacții emoționale",
  "reacții emoționale": "Gestionarea propriilor reacții emoționale",
  "autocontrol": "Gestionarea propriilor reacții emoționale",
  "self emotional management": "Gestionarea propriilor reacții emoționale",
  "managing own emotions": "Gestionarea propriilor reacții emoționale",
  "emotional regulation": "Gestionarea propriilor reacții emoționale",

  // 6. Gestionarea reacțiilor celorlalți
  "gestionarea reactiilor celorlalti": "Gestionarea reacțiilor celorlalți",
  "gestionarea reacțiilor celorlalți": "Gestionarea reacțiilor celorlalți",
  "gestionare reactii ceilalti": "Gestionarea reacțiilor celorlalți",
  "gestionare reacții ceilalți": "Gestionarea reacțiilor celorlalți",
  "reactii ceilalti": "Gestionarea reacțiilor celorlalți",
  "reacții ceilalți": "Gestionarea reacțiilor celorlalți",
  "gestionarea interlocutorului": "Gestionarea reacțiilor celorlalți",
  "managing others emotions": "Gestionarea reacțiilor celorlalți",
  "handling emotional reactions": "Gestionarea reacțiilor celorlalți",

  // 7. Feedback constructiv
  "feedback constructiv": "Feedback constructiv",
  "feedback": "Feedback constructiv",
  "constructive feedback": "Feedback constructiv",
  "oferire feedback": "Feedback constructiv",
  "feedback pozitiv si corectiv": "Feedback constructiv",
  "feedback pozitiv și corectiv": "Feedback constructiv",
};

export function stripAccents(text: string): string {
  return text.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
}

export function normalizeCompetencyName(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^\w\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export function matchComp(rawName?: string | null): string | null {
  if (!rawName) return null;
  const rawClean = rawName.trim();
  if (!rawClean) return null;

  const normLow = rawClean.toLowerCase();
  if (["quiz", "cunostinte", "cunoștințe", "test", "test in", "test out", "test-in", "test-out"].includes(normLow)) {
    return null;
  }

  for (const can of CANONICAL_COMPETENCIES) {
    if (rawClean === can) return can;
  }

  if (COMPETENCY_ALIASES[normLow]) {
    return COMPETENCY_ALIASES[normLow];
  }

  const normalized = normalizeCompetencyName(rawClean);
  if (COMPETENCY_ALIASES[normalized]) {
    return COMPETENCY_ALIASES[normalized];
  }

  const stripped = stripAccents(normalized);
  for (const [alias, canonical] of Object.entries(COMPETENCY_ALIASES)) {
    if (stripAccents(alias) === stripped) {
      return canonical;
    }
  }

  for (const can of CANONICAL_COMPETENCIES) {
    const canStripped = stripAccents(can.toLowerCase());
    if (canStripped.includes(stripped) || stripped.includes(canStripped)) {
      return can;
    }
  }

  return null;
}
