import { getApiBaseUrl, isDemoFallbackEnabled } from "./runtime";

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
      participantFullName: string;
      anonymousName?: string | null;
      isLeadership: boolean;
      alreadyRegistered: boolean;
      deadlineLabel: string;
      expiresAt?: string;
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

type BackendInviteVerifyResponse = {
  email: string;
  full_name: string;
  anonymous_name?: string | null;
  is_leadership: boolean;
  already_registered: boolean;
  project_id?: string;
  project_name: string;
  expires_at?: string;
  token_status?: "active";
  tasks: InviteTask[];
};

type BackendErrorResponse = {
  error?: {
    code?: string;
    message?: string;
  };
};

export async function resolveInviteBundle(token: string): Promise<InviteBundle> {
  const demoFallbackEnabled = isDemoFallbackEnabled();

  if (token === "expired-demo") {
    if (!demoFallbackEnabled) {
      return {
        state: "not_found",
        token,
        message: "Nu am găsit o invitație activă pentru acest link.",
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

  if (token === "demo-token" && !demoFallbackEnabled) {
    return {
      state: "not_found",
      token,
      message: "Nu am găsit o invitație activă pentru acest link.",
    };
  }

  if (token === "demo-token") {
    return {
      state: "valid",
      token,
      projectName: "Intake Iunie",
      participantEmail: "participant@companie.ro",
      participantFullName: "Participant demo",
      anonymousName: "CuriousSoap2121",
      isLeadership: false,
      alreadyRegistered: false,
      deadlineLabel: "deadline-ul proiectului",
      tasks: [
        {
          id: "lencioni-team",
          title: "Lencioni pentru echipa ta",
          status: "not_started",
          detail: "Răspuns pentru echipa din care faci parte.",
          href: "/participant/questionnaires/lencioni?assignmentId=11111111-1111-4111-8111-111111111111&access=secure",
          assignmentId: "11111111-1111-4111-8111-111111111111",
          targetLabel: "Echipa operațională",
          estimatedMinutes: 12,
          questionnaireKey: "lencioni",
        },
        {
          id: "boss-360",
          title: "360 pentru manager",
          status: "in_progress",
          detail: "Feedback confidențial pentru persoana către care raportezi.",
          href: "/participant/questionnaires/boss_360?assignmentId=22222222-2222-4222-8222-222222222222&access=secure",
          assignmentId: "22222222-2222-4222-8222-222222222222",
          targetLabel: "Manager direct",
          estimatedMinutes: 10,
          questionnaireKey: "boss_360",
        },
        {
          id: "leadership-lencioni",
          title: "Lencioni pentru direcție",
          status: "completed",
          detail: "Task finalizat pentru demo-ul de progres.",
          href: "/participant/questionnaires/lencioni?assignmentId=33333333-3333-4333-8333-333333333333&access=secure",
          assignmentId: "33333333-3333-4333-8333-333333333333",
          targetLabel: "Echipa de direcție",
          estimatedMinutes: 12,
          questionnaireKey: "lencioni",
        },
      ],
    };
  }

  return resolveBackendInviteBundle(token);
}

async function resolveBackendInviteBundle(token: string): Promise<InviteBundle> {
  const response = await fetch(`${getApiBaseUrl()}/auth/invite/verify?token=${encodeURIComponent(token)}`, {
    cache: "no-store",
    credentials: "include",
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as BackendErrorResponse | null;
    const code = errorBody?.error?.code;
    const message = errorBody?.error?.message ?? "Nu am găsit o invitație activă pentru acest link.";

    if (code === "task_link_expired" || code === "task_link_revoked") {
      return {
        state: "expired",
        token,
        projectName: "Proiect",
        deadlineLabel: "deadline-ul proiectului",
        message,
      };
    }

    return {
      state: "not_found",
      token,
      message,
    };
  }

  const data = (await response.json()) as BackendInviteVerifyResponse;
  return {
    state: "valid",
    token,
    projectName: data.project_name,
    participantEmail: data.email,
    participantFullName: data.full_name,
    anonymousName: data.anonymous_name,
    isLeadership: data.is_leadership,
    alreadyRegistered: data.already_registered,
    deadlineLabel: data.expires_at ? formatInviteDeadline(data.expires_at) : "finalul evaluării",
    expiresAt: data.expires_at,
    tasks: data.tasks,
  };
}

function formatInviteDeadline(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return "deadline-ul proiectului";
  }

  return new Intl.DateTimeFormat("ro-RO", {
    day: "2-digit",
    month: "long",
    year: "numeric",
  }).format(date);
}

export function inviteStatusLabel(status: InviteTaskStatus): string {
  if (status === "completed") {
    return "Completat";
  }

  if (status === "in_progress") {
    return "În progres";
  }

  return "Neînceput";
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
