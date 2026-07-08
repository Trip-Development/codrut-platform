import "server-only";

import { cookies } from "next/headers";

import {
  AuthRoleMismatchError,
  AuthSessionUnavailableError,
  isAuthRoleMismatchError,
  isAuthSessionUnavailableError,
  type CurrentUser,
  type SessionState,
} from "./auth";
import { getApiBaseUrl, isSeededDemoFallbackEnabled } from "./runtime";

type SessionPrincipalResponse = {
  user_id: string;
  email: string;
  role: "trainer" | "participant";
};

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
    if (response.status === 401 || response.status === 403) return null;
    if (!response.ok) {
      const context = { expectedRole, status: response.status, reason: "server" as const };
      console.warn("[auth] Server session check unavailable.", context);
      throw new AuthSessionUnavailableError(context);
    }
    user = (await response.json()) as SessionPrincipalResponse;
    if (!user.user_id || !user.email || !user.role) {
      const context = { expectedRole, reason: "payload" as const };
      console.warn("[auth] Server session check returned an invalid payload.", context);
      throw new AuthSessionUnavailableError(context);
    }
  } catch (error) {
    if (isAuthSessionUnavailableError(error) || isAuthRoleMismatchError(error)) throw error;
    const context = { expectedRole, reason: "network" as const };
    console.warn("[auth] Server session check failed before a response.", context);
    throw new AuthSessionUnavailableError(context);
  }

  if (user.role !== expectedRole) {
    throw new AuthRoleMismatchError({ expectedRole, actualRole: user.role });
  }

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
    if (isAuthRoleMismatchError(error)) throw error;
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
    if (isAuthRoleMismatchError(error)) throw error;
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
