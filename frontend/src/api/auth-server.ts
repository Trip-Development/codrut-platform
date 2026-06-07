import "server-only";

import { cookies } from "next/headers";

import type { CurrentUser, SessionState } from "./auth";
import { getApiBaseUrl } from "./runtime";

type SessionPrincipalResponse = {
  user_id: string;
  email: string;
  role: "trainer" | "participant";
};

function isDemoFallbackEnabled(): boolean {
  return process.env.CODRUT_FRONTEND_DEMO_FALLBACK === "true";
}

async function getSessionFromApi(expectedRole: "trainer" | "participant"): Promise<SessionState | null> {
  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get("codrut_session");
  if (!sessionCookie?.value) return null;

  let user: SessionPrincipalResponse;
  try {
    const response = await fetch(`${getApiBaseUrl()}/auth/me`, {
      cache: "no-store",
      headers: {
        Cookie: `codrut_session=${sessionCookie.value}`,
      },
    });
    if (!response.ok) return null;
    user = (await response.json()) as SessionPrincipalResponse;
  } catch {
    return null;
  }

  if (user.role !== expectedRole) return null;

  return {
    state: "authenticated",
    user: {
      id: user.user_id,
      name: user.email.split("@")[0],
      role: user.role,
    },
  };
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
    message: "Sesiune temporară de lucru activă.",
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
    message: "Sesiune temporară de lucru activă.",
  };
}
