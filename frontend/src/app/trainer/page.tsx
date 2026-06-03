import { audienceAccessNote, getTrainerSession } from "@/api/auth";
import { getTrainerDashboardSummary } from "@/api/trainer";
import { StatCard } from "@/components/presentation/stat-card";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { PlaceholderCard } from "@/components/shell/placeholder-card";

export default async function TrainerDashboardPage() {
  const [trainer, summary] = await Promise.all([getTrainerSession(), getTrainerDashboardSummary()]);

  return (
    <AppShell
      audience="trainer"
      eyebrow="Trainer"
      title="Panou pentru rollout si monitorizare"
      description="Suprafata pentru Andrei: companii, participanti, organigrama, chestionare, invitatii email si progres operational."
      navItems={trainerNavItems}
      activeHref="/trainer"
      userLabel={trainer.user.name}
      session={trainer}
      accessNote={audienceAccessNote("trainer")}
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {summary.stats.map((stat) => (
          <StatCard key={stat.label} {...stat} />
        ))}
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {summary.cards.map((card) => (
          <PlaceholderCard key={card.title} {...card} />
        ))}
      </div>
    </AppShell>
  );
}
