export type ParticipantWorkspaceCard = {
  title: string;
  description: string;
};

export type ParticipantWorkspaceSummary = {
  cards: ParticipantWorkspaceCard[];
  emptyState: {
    title: string;
    description: string;
  };
};

export async function getParticipantWorkspaceSummary(): Promise<ParticipantWorkspaceSummary> {
  return {
    cards: [
      {
        title: "Cont",
        description: "Confirmare profil, companie si acces securizat.",
      },
      {
        title: "Task-uri",
        description: "Chestionare de completat si deadline-uri.",
      },
      {
        title: "Ajutor",
        description: "Mesaje clare pentru urmatorul pas, fara informatii sensibile in email.",
      },
    ],
    emptyState: {
      title: "Fara chestionare finalizate inca",
      description:
        "Cand participantul are sarcini active, acest loc poate afisa un call-to-action si un sumar clar al pasului urmator.",
    },
  };
}
