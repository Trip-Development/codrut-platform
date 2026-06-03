import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { RecoveredView } from "@/components/shell/recovered-view";

type TrainerProjectDetailPageProps = {
  params: Promise<{ projectId: string }>;
};

export default async function TrainerProjectDetailPage({ params }: TrainerProjectDetailPageProps) {
  const { projectId } = await params;

  return (
    <AppShell
      audience="trainer"
      eyebrow="Detaliu proiect"
      title={`Proiect ${projectId}`}
      description="Ecran recuperat pentru timeline, engagement, Test IN/OUT, scoruri per competenta si lista participantilor."
      navItems={trainerNavItems}
      activeHref="/trainer/projects"
    >
      <RecoveredView
        actions={[
          { label: "Inapoi la proiecte", href: "/trainer/projects" },
          { label: "Participant demo", href: `/trainer/projects/${projectId}/participants/demo-participant` },
        ]}
        metrics={[
          { label: "Participanti", value: "42", detail: "Roster si conturi." },
          { label: "Scor mediu", value: "68", detail: "Media raspunsurilor disponibile.", tone: "success" },
          { label: "Sesiuni", value: "126", detail: "Interventii si completari.", tone: "warning" },
          { label: "Inactivi", value: "6", detail: "Necesita reminder.", tone: "danger" },
        ]}
        sections={[
          {
            title: "Timeline proiect",
            description: "Recupereaza bara de progres si datele de start/end din vechiul admin.",
            items: ["Start program", "Astazi si procent de progres", "Final program", "Stare evaluare finala"],
          },
          {
            title: "Engagement",
            description: "Pastreaza zona operationala pentru completare si activitate.",
            items: ["Test IN completat", "Test OUT completat", "Activi in ultimele 7 zile", "Recurenti cu 3+ sesiuni"],
          },
          {
            title: "Analize echipa",
            description: "Locul pentru graficele vechi, urmand sa fie alimentate din noul backend.",
            items: ["Comparatie IN vs acum vs OUT", "Competente rapide si lente", "Concepte slabe din quiz"],
          },
          {
            title: "Tabel participanti",
            description: "Lista pentru inspectie individuala, status si intrare in raport participant.",
            items: ["Status activ/inactiv", "Sesiuni", "Scor mediu", "Link spre raport individual"],
          },
        ]}
      />
    </AppShell>
  );
}
