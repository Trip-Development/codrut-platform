import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { RecoveredView } from "@/components/shell/recovered-view";

export default function TrainerProjectsPage() {
  return (
    <AppShell
      audience="trainer"
      eyebrow="Proiecte"
      title="Proiecte si programe active"
      description="Suprafata recuperata din vechiul admin pentru programe, access codes, perioade, competente si status de rollout."
      navItems={trainerNavItems}
      activeHref="/trainer/projects"
    >
      <RecoveredView
        actions={[
          { label: "Detaliu proiect", href: "/trainer/projects/demo-project" },
          { label: "Participant demo", href: "/trainer/projects/demo-project/participants/demo-participant" },
        ]}
        metrics={[
          { label: "Proiecte", value: "8", detail: "Clienti si programe configurabile." },
          { label: "In desfasurare", value: "5", detail: "Au roster si sarcini active.", tone: "success" },
          { label: "Necesita setup", value: "3", detail: "Lipsesc date, formulare sau email.", tone: "warning" },
          { label: "Finale active", value: "1", detail: "Evaluare finala activata.", tone: "danger" },
        ]}
        sections={[
          {
            title: "Configurare proiect",
            description: "Pastreaza forma veche de lucru, fara dependinta de Supabase.",
            items: ["Client si tema programului", "Perioada de training", "Competente sau chestionare asociate", "Coduri si linkuri de acces"],
          },
          {
            title: "Operatiuni trainer",
            description: "Instrumente care trebuie expuse clar pentru un trainer non-tehnic.",
            items: ["Creare proiect", "Import participanti", "Activare evaluare finala", "Export sau inspectie rapoarte"],
          },
        ]}
      />
    </AppShell>
  );
}
