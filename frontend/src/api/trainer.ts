export type TrainerStat = {
  label: string;
  value: number;
  detail: string;
  tone?: "default" | "success" | "warning" | "danger";
};

export type TrainerSurfaceCard = {
  title: string;
  description: string;
  meta: string;
};

export type TrainerDashboardSummary = {
  stats: TrainerStat[];
  cards: TrainerSurfaceCard[];
};

export async function getTrainerDashboardSummary(): Promise<TrainerDashboardSummary> {
  return {
    stats: [
      {
        label: "Companii",
        value: 8,
        detail: "Lista clientilor si statusul pregatirii pentru intake.",
      },
      {
        label: "Participanti",
        value: 42,
        detail: "Roster, conturi, roluri si stari de invitatie.",
        tone: "success",
      },
      {
        label: "Chestionare",
        value: 12,
        detail: "Sarcini asignate, pornite, trimise si validate.",
        tone: "warning",
      },
      {
        label: "Email",
        value: 3,
        detail: "Invitatii, remindere, erori de livrare si test-mode.",
        tone: "danger",
      },
    ],
    cards: [
      {
        title: "Companii",
        description: "Lista companiilor si statusul pregatirii pentru intake.",
        meta: "Platform",
      },
      {
        title: "Participanti",
        description: "Roster, conturi, roluri si stari de invitatie.",
        meta: "Identity",
      },
      {
        title: "Chestionare",
        description: "Sarcini asignate, pornite, trimise si validate.",
        meta: "Forms",
      },
      {
        title: "Email",
        description: "Invitatii, remindere, erori de livrare si test-mode.",
        meta: "Comms",
      },
    ],
  };
}
