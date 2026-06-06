import { getTrainerSession } from "@/api/auth-server";
import { getEmailOpsSummary } from "@/api/email";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { EmailWorkspace } from "./EmailWorkspace";

export default async function TrainerEmailPage() {
  const [trainer, summary] = await Promise.all([getTrainerSession(), getEmailOpsSummary()]);

  return (
    <AppShell
      audience="trainer"
      eyebrow="Email"
      title="Invitații, remindere și șabloane"
      description="Suprafață owner-friendly pentru livrare assessment: cine a primit emailul, cine a intrat în app și configurarea șabloanelor."
      navItems={trainerNavItems}
      activeHref="/trainer/email"
      userLabel={trainer.user.name}
      session={trainer}
    >
      <EmailWorkspace initialSummary={summary} />
    </AppShell>
  );
}
