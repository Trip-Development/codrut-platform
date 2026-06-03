import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";
import { RecoveredView } from "@/components/shell/recovered-view";

export default function ParticipantDashboardPage() {
  return (
    <AppShell
      audience="participant"
      eyebrow="Dashboard"
      title="Progres personal"
      description="Dashboard recuperat din vechiul participant app pentru progres, insight-uri si evidenta dupa completari."
      navItems={participantNavItems}
      activeHref="/participant/dashboard"
    >
      <RecoveredView
        metrics={[
          { label: "Task-uri", value: "4", detail: "Asignari active." },
          { label: "Completate", value: "1", detail: "Trimise cu succes.", tone: "success" },
          { label: "In lucru", value: "2", detail: "Drafturi sau sesiuni incepute.", tone: "warning" },
          { label: "Deadline", value: "3 zile", detail: "Urmatorul termen.", tone: "danger" },
        ]}
        sections={[
          {
            title: "Rezumat personal",
            description: "Pastreaza ideea veche de dashboard personal, adaptata la chestionare si assignments.",
            items: ["Chestionare asignate", "Status pe fiecare sarcina", "Confirmare trimitere", "Urmatorul pas clar"],
          },
          {
            title: "Insight-uri",
            description: "Zona pentru feedback personal care nu expune datele altora.",
            items: ["Recomandari personale", "Evolutie", "Istoric completari", "Ajutor contextual"],
          },
        ]}
      />
    </AppShell>
  );
}
