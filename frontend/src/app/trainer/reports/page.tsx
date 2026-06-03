import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { RecoveredView } from "@/components/shell/recovered-view";

export default function TrainerReportsPage() {
  return (
    <AppShell
      audience="trainer"
      eyebrow="Rapoarte"
      title="Rapoarte, progres si vizibilitate"
      description="Suprafata pentru rapoarte de companie, echipa si participant, cu reguli explicite de anonimizare pentru cei evaluati."
      navItems={trainerNavItems}
      activeHref="/trainer/reports"
    >
      <RecoveredView
        actions={[{ label: "Raport participant demo", href: "/trainer/projects/demo-project/participants/demo-participant" }]}
        sections={[
          {
            title: "Rapoarte trainer",
            description: "Trainerul/ownerul poate vedea detaliu operational pentru a conduce programul.",
            items: ["Raspunsuri individuale", "Status completare", "Semnale de risc", "Istoric reminder"],
          },
          {
            title: "Rapoarte pentru evaluati",
            description: "Persoanele evaluate nu trebuie sa afle cine le-a evaluat.",
            items: ["Agregare pe prag minim", "Fara identitate evaluator", "Fara randuri individuale", "Mesaje de confidentialitate"],
          },
          {
            title: "Rapoarte echipa",
            description: "Vizualizari pentru Lencioni si progres de grup.",
            items: ["Leadership team", "Echipe asociate", "Comparatii intre valuri", "Export owner"],
          },
          {
            title: "Rapoarte campanie",
            description: "Pregatire pentru emailuri custom cu video catre clienti potentiali sau trecuti.",
            items: ["Recipienti", "Template-uri", "Livrare", "Unsubscribe si suppressions"],
          },
        ]}
      />
    </AppShell>
  );
}
