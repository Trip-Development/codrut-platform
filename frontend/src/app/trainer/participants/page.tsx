import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { PlaceholderCard } from "@/components/shell/placeholder-card";

export default function TrainerParticipantsPage() {
  return (
    <AppShell
      audience="trainer"
      eyebrow="Participanti"
      title="Roster si conturi"
      description="Suprafata pentru import, verificare profil PCM optional, invitatii si asociere cu compania corecta."
      navItems={trainerNavItems}
      activeHref="/trainer/participants"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <PlaceholderCard title="Import roster" description="Name, Reports To, Position, Location, email si Profil PCM optional." />
        <PlaceholderCard title="Conturi" description="Invitatie email primara plus access-code self-registration." />
        <PlaceholderCard title="Status" description="Invitat, activat, inceput, trimis, reminder necesar." />
      </div>
    </AppShell>
  );
}
