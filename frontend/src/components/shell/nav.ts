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
  { href: "/participant/tablou", label: "Tablou Competențe", shortLabel: "Tablou" },
  { href: "/participant/practice", label: "Exersează (Cody)", shortLabel: "Cody" },
  { href: "/participant/questionnaires", label: "Chestionare", shortLabel: "Forme" },
  { href: "/participant/results", label: "Rezultate", shortLabel: "Rez." },
  { href: "/participant/account", label: "Cont", shortLabel: "Cont" },
];
