export type ShellNavItem = {
  href: string;
  label: string;
  shortLabel?: string;
};

export const trainerNavItems: ShellNavItem[] = [
  { href: "/trainer", label: "Acasă", shortLabel: "Acasă" },
  { href: "/trainer/companies", label: "Companii", shortLabel: "Co." },
  { href: "/trainer/projects", label: "Proiecte", shortLabel: "Proj." },
  { href: "/trainer/questionnaires", label: "Chestionare", shortLabel: "Forme" },
  { href: "/trainer/email", label: "Comunicare", shortLabel: "Email" },
  { href: "/trainer/settings", label: "Setări", shortLabel: "Setări" },
];

export const participantNavItems: ShellNavItem[] = [
  { href: "/participant", label: "Acasă", shortLabel: "Acasă" },
  // Tabloul si exersarea NU stau aici — plicul 113.
  //
  // Comentariul de mai jos spunea de la inceput ca „pentru orice alt tip de proiect meniul
  // ramane exact cel de pana acum", dar codul le punea in AMANDOUA meniurile: tipul proiectului
  // alegea doar daca dispar „Chestionare" si „Rezultate". Mutarea codului ar fi adaugat doua
  // intrari noi in meniul fiecarui participant din fiecare proiect — cei 216 oameni de la
  // Michelin inclusi. N-ar fi putut porni nimic (poarta de la `service.py:159` ii opreste), dar
  // ar fi VAZUT tabul. `nav.test.ts` spunea asta de la plicul 83, si l-am citit ca test vechi.
  { href: "/participant/questionnaires", label: "Chestionare", shortLabel: "Forme" },
  { href: "/participant/results", label: "Rezultate", shortLabel: "Rez." },
  { href: "/participant/account", label: "Cont", shortLabel: "Cont" },
];

/**
 * Tipul proiectului e comutatorul meniului, nu o etichetă.
 *
 * Un om dintr-un proiect de `training` nu are ce căuta în ecranele de coaching:
 * „Chestionare" și „Rezultate" sunt ale celuilalt flux. Pentru orice alt tip de
 * proiect meniul rămâne exact cel de până acum — nimic nu se schimbă pentru ei.
 */
export const TRAINING_PROJECT_TYPE = "training";

export const participantTrainingNavItems: ShellNavItem[] = [
  { href: "/participant", label: "Acasă", shortLabel: "Acasă" },
  { href: "/participant/tablou", label: "Tablou Competențe", shortLabel: "Tablou" },
  { href: "/participant/practice", label: "Exersează (Cody)", shortLabel: "Cody" },
  { href: "/participant/account", label: "Cont", shortLabel: "Cont" },
];

export function participantNavItemsForType(
  projectType?: string | null,
): ShellNavItem[] {
  return projectType === TRAINING_PROJECT_TYPE
    ? participantTrainingNavItems
    : participantNavItems;
}
