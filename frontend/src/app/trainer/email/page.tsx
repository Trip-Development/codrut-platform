import { getTrainerSession } from "@/api/auth-server";
import { getEmailOpsSummary } from "@/api/email";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { LazyEmailWorkspace } from "./LazyEmailWorkspace";

export default async function TrainerEmailPage() {
  const requestOptions = await getServerApiRequestOptions();
  const [trainer, summary] = await Promise.all([
    getTrainerSession(),
    getEmailOpsSummary(requestOptions),
  ]);

  return (
    <AppShell
      audience="trainer"
      eyebrow=""
      title="Comunicare"
      description=""
      navItems={trainerNavItems}
      activeHref="/trainer/email"
      userLabel={trainer.user.name}
      session={trainer}
      showHeader={false}
    >
      <LazyEmailWorkspace initialSummary={summary} />
    </AppShell>
  );
}
