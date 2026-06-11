export type ShellNavItem = {
  href: string;
  label: string;
  shortLabel?: string;
};

export const trainerNavItems: ShellNavItem[] = [
  { href: "/trainer", label: "Acasă", shortLabel: "Acasă" },
  { href: "/trainer/companies", label: "Companii", shortLabel: "Co." },
  { href: "/trainer/questionnaires", label: "Chestionare", shortLabel: "Forms" },
  { href: "/trainer/email", label: "Șabloane email", shortLabel: "Email" },
  { href: "/trainer/settings", label: "Setări", shortLabel: "Setări" },
];

export const participantNavItems: ShellNavItem[] = [
  { href: "/participant", label: "Acasă", shortLabel: "Acasă" },
  { href: "/participant/questionnaires", label: "Chestionare", shortLabel: "Forms" },
  { href: "/participant/chat", label: "Practică", shortLabel: "Practică" },
  { href: "/participant/final-evaluation", label: "Evaluare finală", shortLabel: "Final" },
  { href: "/participant/account", label: "Cont", shortLabel: "Cont" },
];
