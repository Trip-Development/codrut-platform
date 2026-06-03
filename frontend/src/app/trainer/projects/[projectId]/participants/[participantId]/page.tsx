import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { RecoveredView } from "@/components/shell/recovered-view";

type TrainerParticipantReportPageProps = {
  params: Promise<{ projectId: string; participantId: string }>;
};

export default async function TrainerParticipantReportPage({ params }: TrainerParticipantReportPageProps) {
  const { projectId, participantId } = await params;

  return (
    <AppShell
      audience="trainer"
      eyebrow="Raport participant"
      title={`Participant ${participantId}`}
      description="Raport recuperat pentru trainer/owner. Pentru persoanele evaluate, accesul final trebuie agregat si anonimizat."
      navItems={trainerNavItems}
      activeHref="/trainer/reports"
    >
      <RecoveredView
        actions={[
          { label: "Inapoi la proiect", href: `/trainer/projects/${projectId}` },
          { label: "Rapoarte", href: "/trainer/reports" },
        ]}
        metrics={[
          { label: "Test IN", value: "54", detail: "Baseline teoretic." },
          { label: "Progres", value: "72%", detail: "Evidence acumulat.", tone: "success" },
          { label: "Test OUT", value: "-", detail: "In asteptare.", tone: "warning" },
          { label: "Sesiuni", value: "9", detail: "Practica aplicata." },
        ]}
        sections={[
          {
            title: "Teorie",
            description: "Recupereaza comparatia Test IN / Test OUT.",
            items: ["Scor pe competenta", "Delta final", "Zone unde a crescut", "Zone unde ramane sub prag"],
          },
          {
            title: "Practica",
            description: "Recupereaza evidence radar si evolutie din sesiuni.",
            items: ["Radar evidence", "Linie de evolutie", "Insight moments", "Mostre de invatare"],
          },
          {
            title: "Note trainer",
            description: "Spatiu pentru observatii operationale private.",
            items: ["Observatii manuale", "Recomandari urmatoare", "Riscuri de engagement", "Follow-up"],
          },
          {
            title: "Vizibilitate",
            description: "Trainerul poate inspecta raspunsuri, dar persoana evaluata nu vede identitatea evaluatorilor.",
            items: ["Acces trainer complet", "Raport manager agregat", "360 anonim", "Audit de acces"],
          },
        ]}
      />
    </AppShell>
  );
}
