export type ShellNavItem = {
  href: string;
  label: string;
  shortLabel?: string;
};

export const trainerNavItems: ShellNavItem[] = [
  { href: "/trainer", label: "Dashboard", shortLabel: "Home" },
  { href: "/trainer/org-chart", label: "Organigrama", shortLabel: "Org" },
  { href: "/trainer/participants", label: "Participanti", shortLabel: "Users" },
  { href: "/trainer/questionnaires", label: "Chestionare", shortLabel: "Forms" },
  { href: "/trainer/email", label: "Email & invitatii", shortLabel: "Email" },
];

export const participantNavItems: ShellNavItem[] = [
  { href: "/participant", label: "Sarcinile mele", shortLabel: "Tasks" },
  { href: "/participant/questionnaires", label: "Chestionare", shortLabel: "Forms" },
  { href: "/participant/account", label: "Cont", shortLabel: "Cont" },
];
