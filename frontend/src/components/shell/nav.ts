export type ShellNavItem = {
  href: string;
  label: string;
  shortLabel?: string;
};

export const trainerNavItems: ShellNavItem[] = [
  { href: "/trainer", label: "Dashboard", shortLabel: "Home" },
  { href: "/trainer/companies", label: "Companii", shortLabel: "Co." },
  { href: "/trainer/roster", label: "Roster", shortLabel: "Roster" },
  { href: "/trainer/org", label: "Organigrama", shortLabel: "Org" },
  { href: "/trainer/questionnaires", label: "Chestionare", shortLabel: "Forms" },
  { href: "/trainer/email", label: "Email & invitatii", shortLabel: "Email" },
  { href: "/trainer/reports", label: "Rapoarte", shortLabel: "Reports" },
];

export const participantNavItems: ShellNavItem[] = [
  { href: "/participant", label: "Sarcinile mele", shortLabel: "Tasks" },
  { href: "/participant/dashboard", label: "Dashboard", shortLabel: "Dash" },
  { href: "/participant/questionnaires", label: "Chestionare", shortLabel: "Forms" },
  { href: "/participant/chat", label: "Chat", shortLabel: "Chat" },
  { href: "/participant/onboarding", label: "Onboarding", shortLabel: "Start" },
  { href: "/participant/final-evaluation", label: "Evaluare finala", shortLabel: "Final" },
  { href: "/participant/account", label: "Cont", shortLabel: "Cont" },
];
