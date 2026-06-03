import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";
import { RecoveredView } from "@/components/shell/recovered-view";

export default function ParticipantOnboardingPage() {
  return (
    <AppShell
      audience="participant"
      eyebrow="Onboarding"
      title="Intrare participant si evaluare initiala"
      description="Flux recuperat pentru welcome screen, cont securizat si prima evaluare. In urgent intake, linkul email trebuie sa deschida toate sarcinile participantului."
      navItems={participantNavItems}
      activeHref="/participant/onboarding"
    >
      <RecoveredView
        sections={[
          {
            title: "Welcome screen",
            description: "Pastreaza introducerea prietenoasa pentru participant.",
            items: ["Salut personalizat", "Context program", "Ce urmeaza", "Confidentialitate"],
          },
          {
            title: "Setup cont",
            description: "Toti respondentii primesc emailuri diferite pentru setarea contului.",
            items: ["Email corporate", "Parola", "Asociere companie", "Bundle de sarcini"],
          },
          {
            title: "Evaluare initiala",
            description: "Model recuperat pentru Test IN, dar noul flux va folosi chestionarele aprobate.",
            items: ["PCM base", "Phase", "Lencioni unde este cazul", "360 unde este asignat"],
          },
          {
            title: "Dupa submit",
            description: "Redirect si confirmare fara expunere de informatii sensibile.",
            items: ["Dashboard personal", "Status completare", "Urmatorul task", "Confirmare email optionala"],
          },
        ]}
      />
    </AppShell>
  );
}
