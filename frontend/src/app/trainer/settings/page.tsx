import { audienceAccessNote } from "@/api/auth";
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
      eyebrow="Setări"
      title="Cont și preferințe"
      description="Detalii de acces, context operațional și securitate pentru contul de trainer."
      navItems={trainerNavItems}
      activeHref="/trainer/settings"
      userLabel={trainer.user.name}
      session={trainer}
      accessNote={audienceAccessNote("trainer")}
    >
      <AccountSettingsPanel
        eyebrow="Cont trainer"
        title={trainer.user.name}
        description="Setările de aici afectează contul cu care intri în spațiul trainer. Configurările de proiect, invitații și șabloane rămân în zonele lor dedicate."
        passwordEnabled={trainer.state === "authenticated"}
        accountRows={[
          { label: "Email", value: email, tone: "accent" },
          { label: "Rol", value: "Trainer / owner" },
          { label: "Sesiune", value: sessionLabel },
          { label: "Acces", value: "Companii, proiecte, participanți, rapoarte și emailuri" },
        ]}
        contextRows={[
          { label: "Spațiu implicit", value: "Companii" },
          { label: "Rapoarte", value: "Vizibile trainerului la nivel de proiect și companie" },
          { label: "Invitații", value: "Gestionate separat în tabul Invitații al proiectului" },
          { label: "Șabloane", value: "Administrate din Șabloane email" },
        ]}
        notes={[
          "Tema aleasă se salvează local între pagini.",
          "Managerii și participanții nu văd răspunsuri brute ale altor persoane.",
          "Resetarea parolei rămâne disponibilă din ecranul de autentificare dacă nu mai știi parola curentă.",
        ]}
      />
    </AppShell>
  );
}
