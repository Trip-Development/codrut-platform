import { getTrainerSession } from "@/api/auth-server";
import { AccountSettingsPanel } from "@/components/settings/account-settings-panel";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";

export default async function TrainerSettingsPage() {
  const trainer = await getTrainerSession();
  const sessionLabel = trainer.state === "authenticated" ? "Autentificat" : "Demo local";
  const email = trainer.user.email ?? "Email disponibil după autentificare";

  return (
    <AppShell
      audience="trainer"
      title="Setări"
      navItems={trainerNavItems}
      activeHref="/trainer/settings"
      userLabel={trainer.user.name}
      session={trainer}
    >
      <AccountSettingsPanel
        passwordEnabled={trainer.state === "authenticated"}
        accountRows={[
          { label: "Email", value: email, tone: "accent" },
          { label: "Rol", value: "Trainer" },
          { label: "Sesiune", value: sessionLabel },
        ]}
      />
    </AppShell>
  );
}
