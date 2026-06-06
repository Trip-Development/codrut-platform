export type ShellNavItem = {
  href: string;
  label: string;
  shortLabel?: string;
};

export const trainerNavItems: ShellNavItem[] = [
  { href: "/trainer", label: "Dashboard", shortLabel: "Home" },
  { href: "/trainer/companies", label: "Companii", shortLabel: "Co." },
  { href: "/trainer/org", label: "Organigrama", shortLabel: "Org" },
  { href: "/trainer/questionnaires", label: "Chestionare", shortLabel: "Forms" },
  { href: "/trainer/email", label: "Email & invitatii", shortLabel: "Email" },
  { href: "/trainer/reports", label: "Rapoarte", shortLabel: "Reports" },
  { href: "/trainer/settings", label: "Setări", shortLabel: "Setări" },
];

export const participantNavItems: ShellNavItem[] = [
  { href: "/participant", label: "Dashboard", shortLabel: "Dash" },
  { href: "/participant/questionnaires", label: "Chestionare", shortLabel: "Forms" },
  { href: "/participant/chat", label: "Practica", shortLabel: "Practica" },
  { href: "/participant/final-evaluation", label: "Evaluare finala", shortLabel: "Final" },
  { href: "/participant/account", label: "Cont", shortLabel: "Cont" },
];
