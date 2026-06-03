export type InviteTaskStatus = "not_started" | "in_progress" | "completed";

export type InviteTask = {
  id: string;
  title: string;
  status: InviteTaskStatus;
  detail: string;
  href: string;
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
  if (token === "expired-demo") {
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
        detail: "Completare fara cont, asociata emailului tau.",
        href: "/participant/questionnaires/lencioni",
      },
      {
        id: "boss-360",
        title: "360 pentru manager",
        status: "in_progress",
        detail: "Raspunsurile nu sunt vizibile persoanei evaluate.",
        href: "/participant/questionnaires/boss_360",
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
