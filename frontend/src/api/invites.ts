import { isDemoFallbackEnabled } from "./runtime";

export type InviteTaskStatus = "not_started" | "in_progress" | "completed";

export type InviteTask = {
  id: string;
  title: string;
  status: InviteTaskStatus;
  detail: string;
  href: string;
  assignmentId: string;
  targetLabel: string;
  estimatedMinutes: number;
  questionnaireKey: string;
};

export type InviteBundle =
  | {
      state: "valid";
      token: string;
      projectName: string;
      participantEmail: string;
      deadlineLabel: string;
      tasks: InviteTask[];
    }
  | {
      state: "expired";
      token: string;
      projectName: string;
      deadlineLabel: string;
      message: string;
    }
  | {
      state: "not_found";
      token: string;
      message: string;
    };

export async function resolveInviteBundle(token: string): Promise<InviteBundle> {
  const demoFallbackEnabled = isDemoFallbackEnabled();

  if (token === "expired-demo") {
    if (!demoFallbackEnabled) {
      return {
        state: "not_found",
        token,
        message: "Nu am gasit o invitatie activa pentru acest link.",
      };
    }

    return {
      state: "expired",
      token,
      projectName: "Intake Iunie",
      deadlineLabel: "deadline proiect",
      message: "Linkul a expirat la deadline-ul proiectului. Cere un link nou de la trainer.",
    };
  }

  if (token !== "demo-token") {
    return {
      state: "not_found",
      token,
      message: "Nu am gasit o invitatie activa pentru acest link.",
    };
  }

  if (!demoFallbackEnabled) {
    return {
      state: "not_found",
      token,
      message: "Nu am gasit o invitatie activa pentru acest link.",
    };
  }

  return {
    state: "valid",
    token,
    projectName: "Intake Iunie",
    participantEmail: "participant@companie.ro",
    deadlineLabel: "deadline-ul proiectului",
    tasks: [
      {
        id: "lencioni-team",
        title: "Lencioni pentru echipa ta",
        status: "not_started",
        detail: "Raspuns pentru echipa din care faci parte.",
        href: "/participant/questionnaires/lencioni?assignmentId=11111111-1111-4111-8111-111111111111",
        assignmentId: "11111111-1111-4111-8111-111111111111",
        targetLabel: "Echipa Operational",
        estimatedMinutes: 12,
        questionnaireKey: "lencioni",
      },
      {
        id: "boss-360",
        title: "360 pentru manager",
        status: "in_progress",
        detail: "Feedback confidential pentru persoana catre care raportezi.",
        href: "/participant/questionnaires/boss_360?assignmentId=22222222-2222-4222-8222-222222222222",
        assignmentId: "22222222-2222-4222-8222-222222222222",
        targetLabel: "Manager direct",
        estimatedMinutes: 10,
        questionnaireKey: "boss_360",
      },
      {
        id: "leadership-lencioni",
        title: "Lencioni pentru directie",
        status: "completed",
        detail: "Task finalizat pentru demo-ul de progres.",
        href: "/participant/questionnaires/lencioni?assignmentId=33333333-3333-4333-8333-333333333333",
        assignmentId: "33333333-3333-4333-8333-333333333333",
        targetLabel: "Echipa de directie",
        estimatedMinutes: 12,
        questionnaireKey: "lencioni",
      },
    ],
  };
}

export function inviteStatusLabel(status: InviteTaskStatus): string {
  if (status === "completed") {
    return "Completat";
  }

  if (status === "in_progress") {
    return "In progres";
  }

  return "Neinceput";
}

export function inviteTaskProgress(tasks: InviteTask[]): {
  completed: number;
  total: number;
  percent: number;
  nextTask?: InviteTask;
} {
  const completed = tasks.filter((task) => task.status === "completed").length;
  const total = tasks.length;
  const nextTask = tasks.find((task) => task.status !== "completed");

  return {
    completed,
    total,
    percent: total > 0 ? Math.round((completed / total) * 100) : 0,
    nextTask,
  };
}
