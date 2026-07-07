import { validatePasswordPolicy } from "./password-policy";
import { getApiBaseUrl, isSeededDemoFallbackEnabled } from "./runtime";

export type CurrentUser = {
  id: string;
  name: string;
  email?: string;
  role: "trainer" | "participant";
};

export type SessionState = {
  state: "authenticated" | "fallback";
  user: CurrentUser;
  message?: string;
};

type AuthApiResponse = {
  user_id: string;
  email: string;
  role: "trainer" | "participant";
};

type SessionPrincipalResponse = {
  user_id: string;
  email: string;
  role: "trainer" | "participant";
};

type AuthSessionUnavailableContext = {
  expectedRole: "trainer" | "participant";
  status?: number;
  reason: "network" | "server" | "payload";
};

export class AuthSessionUnavailableError extends Error {
  context: AuthSessionUnavailableContext;

  constructor(context: AuthSessionUnavailableContext) {
    super("Nu am putut verifica sesiunea. Reîncearcă în câteva momente.");
    this.name = "AuthSessionUnavailableError";
    this.context = context;
  }
}

export function isAuthSessionUnavailableError(error: unknown): error is AuthSessionUnavailableError {
  return error instanceof AuthSessionUnavailableError;
}

function logSessionUnavailable(context: AuthSessionUnavailableContext): void {
  console.warn("[auth] Session check unavailable.", context);
}

export async function loginWithPassword(email: string, password: string): Promise<SessionState> {
  const response = await fetch(`${getApiBaseUrl()}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message = payload?.error?.message ?? "Autentificarea a eșuat. Verifică emailul și parola.";
    throw new Error(message);
  }

  const user = (await response.json()) as AuthApiResponse;
  return {
    state: "authenticated",
    user: {
      id: user.user_id,
      name: user.email.split("@")[0],
      email: user.email,
      role: user.role,
    },
  };
}

export async function requestPasswordReset(email: string): Promise<void> {
  const response = await fetch(`${getApiBaseUrl()}/auth/reset-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message = payload?.error?.message ?? "Emailul de resetare nu a putut fi trimis.";
    throw new Error(message);
  }
}

export async function confirmPasswordReset(token: string, password: string): Promise<void> {
  const passwordError = validatePasswordPolicy(password);
  if (passwordError) throw new Error(passwordError);

  const response = await fetch(`${getApiBaseUrl()}/auth/reset-password/confirm`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ token, password }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message = payload?.error?.message ?? "Parola nu a putut fi resetată.";
    throw new Error(message);
  }
}

export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  const passwordError = validatePasswordPolicy(newPassword);
  if (passwordError) throw new Error(passwordError);

  const response = await fetch(`${getApiBaseUrl()}/auth/change-password`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message = payload?.error?.message ?? "Parola nu a putut fi actualizată.";
    throw new Error(message);
  }
}

async function getSessionFromApi(expectedRole: "trainer" | "participant"): Promise<SessionState | null> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/auth/me`, {
      cache: "no-store",
      credentials: "include",
    });
    if (response.status === 401 || response.status === 403) return null;
    if (!response.ok) {
      const context: AuthSessionUnavailableContext = {
        expectedRole,
        status: response.status,
        reason: "server",
      };
      logSessionUnavailable(context);
      throw new AuthSessionUnavailableError(context);
    }
    const user = (await response.json()) as SessionPrincipalResponse;
    if (!user.user_id || !user.email || !user.role) {
      const context: AuthSessionUnavailableContext = { expectedRole, reason: "payload" };
      logSessionUnavailable(context);
      throw new AuthSessionUnavailableError(context);
    }
    if (user.role !== expectedRole) return null;
    return {
      state: "authenticated",
      user: {
        id: user.user_id,
        name: user.email.split("@")[0],
        email: user.email,
        role: user.role,
      },
    };
  } catch (error) {
    if (isAuthSessionUnavailableError(error)) throw error;
    const context: AuthSessionUnavailableContext = { expectedRole, reason: "network" };
    logSessionUnavailable(context);
    throw new AuthSessionUnavailableError(context);
  }
}

export async function getCurrentTrainer(): Promise<CurrentUser> {
  return getTrainerSession().then((session) => session.user);
}

export async function getCurrentParticipant(): Promise<CurrentUser> {
  return getParticipantSession().then((session) => session.user);
}

export async function getTrainerSession(): Promise<SessionState> {
  let session: SessionState | null = null;
  try {
    session = await getSessionFromApi("trainer");
  } catch (error) {
    if (!isSeededDemoFallbackEnabled()) throw error;
  }
  if (session) return session;

  if (!isSeededDemoFallbackEnabled()) {
    throw new Error("Trainer authentication required.");
  }

  return {
    state: "fallback",
    user: {
      id: "trainer-local",
      name: "Andrei",
      role: "trainer",
    },
  };
}

export async function getParticipantSession(): Promise<SessionState> {
  let session: SessionState | null = null;
  try {
    session = await getSessionFromApi("participant");
  } catch (error) {
    if (!isSeededDemoFallbackEnabled()) throw error;
  }
  if (session) return session;

  if (!isSeededDemoFallbackEnabled()) {
    throw new Error("Participant authentication required.");
  }

  return {
    state: "fallback",
    user: {
      id: "participant-local",
      name: "Mihai Matei",
      role: "participant",
    },
  };
}

export function audienceAccessNote(audience: "trainer" | "participant" | "invitee"): string {
  if (audience === "trainer") {
    return "Acces trainer: cont necesar în producție; demo fallback activ în prototip.";
  }

  if (audience === "participant") {
    return "Leadership: cont necesar pentru progres persistent și sarcini recurente.";
  }

  return "Invitați fără cont: linkul securizat strânge toate sarcinile proiectului pentru emailul primit.";
}
