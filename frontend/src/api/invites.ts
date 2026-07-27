import { apiFetch } from "./http";
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
  projectId?: string | null;
  projectName?: string | null;
  assignmentRoundId?: string;
};

const questionnaireLabels: Record<string, string> = {
  lencioni: "Lencioni - evaluare echipă",
  lencioni_en: "Lencioni - evaluare echipă",
  distress_drivers: "Driveri de stres TA",
  distress_drivers_en: "Driveri de stres TA",
  boss_360: "iCARE 360 pentru manager",
  icare: "iCARE 360 pentru manager",
  pcm_base: "Baza și faza PCM",
  pcm_phase: "Baza și faza PCM",
  phase: "Baza și faza PCM",
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
      termsAcceptedAt?: string | null;
      termsVersion?: string | null;
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
  terms_accepted_at?: string | null;
  terms_version?: string | null;
  tasks: InviteTask[];
};

type BackendErrorResponse = {
  error?: {
    code?: string;
    message?: string;
  };
};

const inviteFailureMessages: Record<string, string> = {
  task_link_expired: "Linkul a expirat. Cere un link nou de la trainer.",
  task_link_invalid: "Linkul de invitație nu este valid. Cere un link nou de la trainer.",
  task_link_revoked: "Trainerul a înlocuit acest link. Folosește cea mai recentă invitație.",
};

function inviteFailureMessage(
  code: string | undefined,
  fallback = "Nu am găsit o invitație activă pentru acest link.",
): string {
  if (code && inviteFailureMessages[code]) {
    return inviteFailureMessages[code];
  }
  return fallback;
}

export class InviteSessionConflictError extends Error {
  readonly code = "invite_session_conflict";
}

export function isInviteSessionConflictError(
  error: unknown,
): error is InviteSessionConflictError {
  return error instanceof InviteSessionConflictError;
}

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
      projectName: "Leadership operațional Q3",
      participantEmail: "participant.demo@example.com",
      participantFullName: "Mihai Matei",
      anonymousName: "SignalHarbor5271",
      isLeadership: false,
      alreadyRegistered: false,
      deadlineLabel: "deadline-ul proiectului",
      tasks: normalizeInviteTasks([
        {
          id: "distress-drivers-self",
          title: "Driveri de stres TA",
          status: "not_started",
          detail: "Completează autoevaluarea pe scala 1-10 pentru a verifica interfața cu slider.",
          href: "/participant/questionnaires/distress_drivers?assignmentId=44444444-4444-4444-8444-444444444444",
          assignmentId: "44444444-4444-4444-8444-444444444444",
          targetLabel: "Autoevaluare",
          estimatedMinutes: 8,
          questionnaireKey: "distress_drivers",
        },
        {
          id: "lencioni-team",
          title: "Feedback pentru echipă",
          status: "not_started",
          detail: "Răspunde pentru echipa indicată în această sarcină.",
          href: "/participant/questionnaires/lencioni?assignmentId=11111111-1111-4111-8111-111111111111",
          assignmentId: "11111111-1111-4111-8111-111111111111",
          targetLabel: "Echipa operațională Atlas",
          estimatedMinutes: 12,
          questionnaireKey: "lencioni",
        },
        {
          id: "boss-360",
          title: "Feedback confidențial",
          status: "in_progress",
          detail: "Oferă feedback pentru persoana indicată în această sarcină.",
          href: "/participant/questionnaires/boss_360?assignmentId=22222222-2222-4222-8222-222222222222",
          assignmentId: "22222222-2222-4222-8222-222222222222",
          targetLabel: "Bianca Pavel",
          estimatedMinutes: 10,
          questionnaireKey: "boss_360",
        },
        {
          id: "leadership-lencioni",
          title: "Feedback pentru echipă",
          status: "completed",
          detail: "Sarcină finalizată pentru demo-ul de progres.",
          href: "/participant/questionnaires/lencioni?assignmentId=33333333-3333-4333-8333-333333333333",
          assignmentId: "33333333-3333-4333-8333-333333333333",
          targetLabel: "Echipa de direcție",
          estimatedMinutes: 12,
          questionnaireKey: "lencioni",
        },
      ]),
    };
  }

  return resolveBackendInviteBundle(token);
}

export async function exchangeInviteSession(
  token: string,
  options: { replaceExistingSession?: boolean } = {},
): Promise<void> {
  if (token === "demo-token" && isDemoFallbackEnabled()) return;

  const response = await apiFetch(`${getApiBaseUrl()}/auth/invite/exchange`, {
    method: "POST",
    cache: "no-store",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      token,
      ...(options.replaceExistingSession ? { replace_existing_session: true } : {}),
    }),
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as BackendErrorResponse | null;
    if (payload?.error?.code === "invite_session_conflict") {
      throw new InviteSessionConflictError("Invitația aparține unei alte sesiuni active.");
    }
    const localizedMessage = inviteFailureMessage(
      payload?.error?.code,
      "Nu am putut pregăti sesiunea invitației. Reîncearcă sau deschide linkul într-o fereastră privată.",
    );
    throw new Error(localizedMessage);
  }
}

async function resolveBackendInviteBundle(token: string): Promise<InviteBundle> {
  const response = await apiFetch(`${getApiBaseUrl()}/auth/invite/verify?token=${encodeURIComponent(token)}`, {
    cache: "no-store",
    credentials: "include",
  });

  if (!response.ok) {
    const errorBody = (await response.json().catch(() => null)) as BackendErrorResponse | null;
    const code = errorBody?.error?.code;
    const message = inviteFailureMessage(code);

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
    termsAcceptedAt: data.terms_accepted_at,
    termsVersion: data.terms_version,
    tasks: normalizeInviteTasks(data.tasks, token),
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

export function inviteQuestionnaireLabel(key: string): string {
  return questionnaireLabels[key] ?? "Chestionar";
}

export function participantTaskTypeLabel(key: string): string {
  if (key === "lencioni" || key === "lencioni_en") {
    return "Sarcină de echipă";
  }
  if (key === "boss_360" || key === "icare") {
    return "Feedback confidențial";
  }
  if (key === "distress_drivers" || key === "distress_drivers_en" || key === "pcm_base" || key === "pcm_phase" || key === "phase") {
    return "Formular individual";
  }
  return "Chestionar";
}

export function inviteTaskHref(
  task: InviteTask,
  options: { returnTo?: string; inviteToken?: string } = {},
): string {
  if (task.assignmentId && isSecureInviteTaskHref(task.href)) {
    return secureTaskHref(task, options);
  }

  const query: string[] = [];
  const hasReturnTo = task.href.includes("returnTo=");
  const hasTarget = task.href.includes("target=");
  if (options.returnTo && !hasReturnTo) {
    query.push(`returnTo=${encodeURIComponent(options.returnTo)}`);
  }
  if (task.targetLabel && !hasTarget) {
    query.push(`target=${encodeURIComponent(task.targetLabel)}`);
  }
  if (query.length === 0) {
    return task.href;
  }
  const separator = task.href.includes("?") ? "&" : "?";
  return `${task.href}${separator}${query.join("&")}`;
}

function isSecureInviteTaskHref(href: string): boolean {
  return href.includes("access=secure");
}

function normalizeInviteTasks(tasks: InviteTask[], inviteToken?: string): InviteTask[] {
  return tasks.map((task) =>
    task.assignmentId && isSecureInviteTaskHref(task.href)
      ? { ...task, href: secureTaskHref(task, { inviteToken }) }
      : task,
  );
}

function secureTaskHref(
  task: InviteTask,
  options: { returnTo?: string; inviteToken?: string } = {},
): string {
  const inviteToken = options.inviteToken ?? inviteTokenFromReturnTo(options.returnTo)
    ?? inviteTokenFromReturnTo(new URLSearchParams(task.href.split("?")[1] ?? "").get("returnTo"));
  const query = new URLSearchParams();
  if (options.returnTo) {
    query.set("returnTo", options.returnTo);
  } else {
    const existingReturnTo = new URLSearchParams(task.href.split("?")[1] ?? "").get("returnTo");
    if (existingReturnTo) query.set("returnTo", existingReturnTo);
  }
  if (task.targetLabel) {
    query.set("target", task.targetLabel);
  }
  const queryString = query.toString();
  if (!inviteToken) {
    return `/participant/tasks/${encodeURIComponent(task.assignmentId)}?access=secure${queryString ? `&${queryString}` : ""}`;
  }
  return `/invite/${encodeURIComponent(inviteToken)}/tasks/${encodeURIComponent(task.assignmentId)}${queryString ? `?${queryString}` : ""}`;
}

function inviteTokenFromReturnTo(returnTo: string | null | undefined): string | null {
  if (!returnTo) return null;
  const match = /^\/invite\/([^/?#]+)$/.exec(returnTo);
  return match ? decodeURIComponent(match[1]) : null;
}
