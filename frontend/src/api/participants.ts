import { resolveInviteBundle, type InviteTask } from "./invites";

export type ParticipantWorkspaceCard = {
  title: string;
  description: string;
  meta?: string;
};

export type ParticipantWorkspaceSummary = {
  projectName: string;
  participantEmail: string;
  deadlineLabel: string;
  tasks: InviteTask[];
  cards: ParticipantWorkspaceCard[];
  emptyState: {
    title: string;
    description: string;
  };
};

export async function getParticipantWorkspaceSummary(): Promise<ParticipantWorkspaceSummary> {
  const bundle = await resolveInviteBundle("demo-token");
  const tasks = bundle.state === "valid" ? bundle.tasks : [];

  return {
    projectName: bundle.state === "valid" ? bundle.projectName : "Proiect demo",
    participantEmail: bundle.state === "valid" ? bundle.participantEmail : "participant@companie.ro",
    deadlineLabel: bundle.state === "valid" ? bundle.deadlineLabel : "deadline-ul proiectului",
    tasks,
    cards: [
      {
        title: "De completat",
        description: `${tasks.filter((task) => task.status !== "completed").length} sarcini active`,
        meta: "Astăzi",
      },
      {
        title: "Confidențial",
        description: "Managerii evaluați nu văd răspunsuri individuale.",
        meta: "Regula",
      },
      {
        title: "Fără cont",
        description: "Linkul securizat strânge toate sarcinile pentru emailul tău.",
        meta: "Acces",
      },
    ],
    emptyState: {
      title: "Fără chestionare finalizate încă",
      description:
        "Când participantul are sarcini active, acest loc poate afișa un call-to-action și un sumar clar al pasului următor.",
    },
  };
}
