import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { PlaceholderCard } from "@/components/shell/placeholder-card";

export default function TrainerEmailPage() {
  return (
    <AppShell
      audience="trainer"
      eyebrow="Email"
      title="Invitatii, remindere si campanii"
      description="Suprafata owner-friendly pentru email transactional de assessment si, mai tarziu, outreach cu video links."
      navItems={trainerNavItems}
      activeHref="/trainer/email"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <PlaceholderCard title="Invitatii assessment" description="Emailuri pentru cont si chestionarele asignate." meta="June" />
        <PlaceholderCard title="Remindere" description="Reguli configurabile pentru necompletare inainte de deadline." meta="June" />
        <PlaceholderCard title="Campaign readiness" description="Separat de participant data: clienti trecuti, potentiali clienti, video links." meta="Later" />
      </div>
    </AppShell>
  );
}
