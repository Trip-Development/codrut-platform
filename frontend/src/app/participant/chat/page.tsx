import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";
import { RecoveredView } from "@/components/shell/recovered-view";

export default function ParticipantChatPage() {
  return (
    <AppShell
      audience="participant"
      eyebrow="Chat"
      title="Codrut coaching chat"
      description="Suprafata recuperata pentru chat, quiz, role-play si sumar sesiune. Integrarea AI ramane separata de fluxul urgent de chestionare."
      navItems={participantNavItems}
      activeHref="/participant/chat"
    >
      <RecoveredView
        sections={[
          {
            title: "Moduri conversatie",
            description: "Pastreaza optiunile vechi ca inventar de functionalitati.",
            items: ["Role-play", "Quiz cunostinte", "Coaching pe situatie reala", "Reflectie si sumar"],
          },
          {
            title: "Controale chat",
            description: "Elemente UI care pot fi migrate ulterior ca implementare reala.",
            items: ["Mesaje streaming", "Voice-to-text", "Selector quiz", "Inchidere sesiune"],
          },
          {
            title: "Guardrails",
            description: "Comportamente din vechiul chat de pastrat ca cerinte.",
            items: ["Blocare Test OUT cand este activ", "Prompt adaptat proiectului", "Semnale de dificultate", "Nu expune warning intern"],
          },
          {
            title: "Rezultate",
            description: "Date ce vor trebui scrise de backendul nou daca pastram chatul.",
            items: ["Scoruri competenta", "Evolution logs", "Insight moments", "Session samples"],
          },
        ]}
      />
    </AppShell>
  );
}
