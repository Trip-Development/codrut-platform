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
        description: `${tasks.filter((task) => task.status !== "completed").length} task-uri active`,
        meta: "Astazi",
      },
      {
        title: "Confidential",
        description: "Managerii evaluati nu vad raspunsuri individuale.",
        meta: "Regula",
      },
      {
        title: "Fara cont",
        description: "Linkul securizat strange toate task-urile pentru emailul tau.",
        meta: "Acces",
      },
    ],
    emptyState: {
      title: "Fara chestionare finalizate inca",
      description:
        "Cand participantul are sarcini active, acest loc poate afisa un call-to-action si un sumar clar al pasului urmator.",
    },
  };
}
