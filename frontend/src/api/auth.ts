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
    if (!response.ok) return null;
    const user = (await response.json()) as SessionPrincipalResponse;
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
  } catch {
    return null;
  }
}

export async function getCurrentTrainer(): Promise<CurrentUser> {
  return getTrainerSession().then((session) => session.user);
}

export async function getCurrentParticipant(): Promise<CurrentUser> {
  return getParticipantSession().then((session) => session.user);
}

export async function getTrainerSession(): Promise<SessionState> {
  const session = await getSessionFromApi("trainer");
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
  const session = await getSessionFromApi("participant");
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
