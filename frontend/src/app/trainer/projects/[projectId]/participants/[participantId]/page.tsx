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
          { label: "Înapoi la proiect", href: `/trainer/projects/${projectId}` },
          { label: "Rapoarte", href: "/trainer/reports" },
        ]}
        metrics={[
          { label: "Test IN", value: "54", detail: "Baseline teoretic." },
          { label: "Progres", value: "72%", detail: "Evidence acumulat.", tone: "success" },
          { label: "Test OUT", value: "-", detail: "În așteptare.", tone: "warning" },
          { label: "Sesiuni", value: "9", detail: "Practică aplicată." },
        ]}
        sections={[
          {
            title: "Teorie",
            description: "Recuperează comparația Test IN / Test OUT.",
            items: ["Scor pe competență", "Delta final", "Zone unde a crescut", "Zone unde rămâne sub prag"],
          },
          {
            title: "Practică",
            description: "Recuperează evidence radar și evoluție din sesiuni.",
            items: ["Radar evidence", "Linie de evoluție", "Insight moments", "Mostre de învățare"],
          },
          {
            title: "Note trainer",
            description: "Spațiu pentru observații operaționale private.",
            items: ["Observații manuale", "Recomandări următoare", "Riscuri de engagement", "Follow-up"],
          },
          {
            title: "Vizibilitate",
            description: "Trainerul poate inspecta răspunsurile, dar persoana evaluată nu vede identitatea evaluatorilor.",
            items: ["Acces trainer complet", "Raport manager agregat", "360 anonim", "Audit de acces"],
          },
        ]}
      />
    </AppShell>
  );
}
