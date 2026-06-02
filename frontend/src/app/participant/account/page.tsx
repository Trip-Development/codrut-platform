import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";
import { PlaceholderCard } from "@/components/shell/placeholder-card";

export default function ParticipantAccountPage() {
  return (
    <AppShell
      audience="participant"
      eyebrow="Cont"
      title="Profil si acces"
      description="Suprafata pentru contul participantului, legatura cu compania si starea invitatiei."
      navItems={participantNavItems}
      activeHref="/participant/account"
    >
      <PlaceholderCard title="Profil participant" description="Datele reale vor veni din FastAPI dupa implementarea identity/company." />
    </AppShell>
  );
}
