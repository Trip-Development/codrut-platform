import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { PlaceholderCard } from "@/components/shell/placeholder-card";

export default function TrainerOrgChartPage() {
  return (
    <AppShell
      audience="trainer"
      eyebrow="Organigrama"
      title="Harta ierarhiei clientului"
      description="Aici vor fi validate relatiile din coloana Reports To si structura folosita pentru assignment si monitorizare."
      navItems={trainerNavItems}
      activeHref="/trainer/org-chart"
    >
      <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <PlaceholderCard
          title="Org chart"
          description="Placeholder vizual pentru ierarhie. Datele reale vin dupa schema de companii, participanti si reporting relationships."
          meta="Trainer only"
        />
        <PlaceholderCard
          title="Validari"
          description="Persoane fara manager, manageri inexistenti, duplicate si linii de raportare circulare vor aparea aici."
          meta="Roster"
        />
      </div>
    </AppShell>
  );
}
