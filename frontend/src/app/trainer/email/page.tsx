import { getTrainerSession } from "@/api/auth-server";
import { getEmailOpsSummary } from "@/api/email";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { EmailWorkspace } from "./EmailWorkspace";

export default async function TrainerEmailPage() {
  const requestOptions = await getServerApiRequestOptions();
  const [trainer, summary] = await Promise.all([
    getTrainerSession(),
    getEmailOpsSummary(requestOptions),
  ]);

  return (
    <AppShell
      audience="trainer"
      eyebrow="Email"
      title="Șabloane email și arhivă globală"
      description="Biblioteca de texte pentru invitații și remindere. Trimiterea și statusul operațional se gestionează din spațiul fiecărei companii."
      navItems={trainerNavItems}
      activeHref="/trainer/email"
      userLabel={trainer.user.name}
      session={trainer}
    >
      <EmailWorkspace initialSummary={summary} />
    </AppShell>
  );
}
