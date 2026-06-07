import { getApiBaseUrl, isDemoFallbackEnabled } from "./runtime";

export type CurrentUser = {
  id: string;
  name: string;
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
      role: user.role,
    },
  };
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

  if (!isDemoFallbackEnabled()) {
    throw new Error("Trainer authentication required.");
  }

  return {
    state: "fallback",
    user: {
      id: "trainer-local",
      name: "Andrei",
      role: "trainer",
    },
    message: "Sesiune demo trainer pana cand login-ul FastAPI este conectat complet in frontend.",
  };
}

export async function getParticipantSession(): Promise<SessionState> {
  const session = await getSessionFromApi("participant");
  if (session) return session;

  if (!isDemoFallbackEnabled()) {
    throw new Error("Participant authentication required.");
  }

  return {
    state: "fallback",
    user: {
      id: "participant-local",
      name: "Leadership demo",
      role: "participant",
    },
    message: "Sesiune demo leadership. Membrii invitati fara cont intra prin link securizat.",
  };
}

export function audienceAccessNote(audience: "trainer" | "participant" | "invitee"): string {
  if (audience === "trainer") {
    return "Acces trainer: cont necesar in productie; demo fallback activ in prototip.";
  }

  if (audience === "participant") {
    return "Leadership: cont necesar pentru progres persistent si sarcini recurente.";
  }

  return "Invitati fara cont: linkul securizat strange toate sarcinile proiectului pentru emailul primit.";
}
