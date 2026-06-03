import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";
import { RecoveredView } from "@/components/shell/recovered-view";

export default function ParticipantFinalEvaluationPage() {
  return (
    <AppShell
      audience="participant"
      eyebrow="Evaluare finala"
      title="Evaluare finala si task-uri blocate"
      description="Flux recuperat pentru Test OUT si gating. Poate ramane separat sau poate deveni un tip de assignment in noul model."
      navItems={participantNavItems}
      activeHref="/participant/final-evaluation"
    >
      <RecoveredView
        metrics={[
          { label: "Intrebari", value: "21", detail: "Model vechi Test OUT." },
          { label: "Progres", value: "0%", detail: "Nimic completat in mock.", tone: "warning" },
          { label: "Status", value: "Blocat", detail: "Activat de trainer.", tone: "danger" },
        ]}
        sections={[
          {
            title: "Gating",
            description: "Comportamentul vechi oprea chatul pana la finalizarea evaluarii.",
            items: ["Trainer activeaza evaluarea", "Participant vede CTA unic", "Dupa completare revine dashboardul", "Nu poate sari peste cand este obligatorie"],
          },
          {
            title: "Formular",
            description: "Structura poate fi reutilizata pentru chestionarele versionate.",
            items: ["Progres raspunsuri", "Radio options", "Validare toate intrebarile", "Submit cu stare clara"],
          },
        ]}
      />
    </AppShell>
  );
}
