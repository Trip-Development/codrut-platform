import "server-only";

import { cookies, headers } from "next/headers";
import { cache } from "react";

import {
  AuthRoleMismatchError,
  AuthSessionUnavailableError,
  isAuthRoleMismatchError,
  isAuthSessionUnavailableError,
  type CurrentUser,
  type SessionState,
} from "./auth";
import {
  getApiBaseUrl,
  isLocalAuthBypassEnabled,
  isLocalSeededDemoFallbackEnabled,
  isSeededDemoFallbackEnabled,
  LOCAL_AUTH_ROLE_HEADER,
} from "./runtime";

type SessionPrincipalResponse = {
  user_id: string;
  email: string;
  role: "trainer" | "participant";
  account_type?: "guest" | "registered";
  available_workspaces?: Array<"trainer" | "participant">;
  default_workspace?: "trainer" | "participant";
  avatar_palette_key?: number | null;
  access_mode?: "account" | "secure_link";
  terms_accepted_at?: string | null;
  terms_version?: string | null;
  consent_current?: boolean;
};

const getSessionFromApi = cache(async function getSessionFromApi(
  expectedRole: "trainer" | "participant",
): Promise<SessionState | null> {
  const cookieStore = await cookies();
  const sessionCookie = cookieStore.get("codrut_session");
  const incomingHeaders = await headers();
  const requestHost =
    incomingHeaders.get("x-forwarded-host") ?? incomingHeaders.get("host") ?? "";
  const localAuthBypassEnabled = isLocalAuthBypassEnabled(requestHost);
  if (!sessionCookie?.value && !localAuthBypassEnabled) return null;

  const requestHeaders = new Headers();
  if (sessionCookie?.value) {
    requestHeaders.set("Cookie", `codrut_session=${sessionCookie.value}`);
  }
  if (localAuthBypassEnabled) {
    requestHeaders.set(LOCAL_AUTH_ROLE_HEADER, expectedRole);
  }

  let user: SessionPrincipalResponse;
  try {
    const response = await fetch(`${getApiBaseUrl()}/auth/me`, {
      cache: "no-store",
      headers: requestHeaders,
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

  const availableWorkspaces = user.available_workspaces ?? [user.role];
  if (!availableWorkspaces.includes(expectedRole)) {
    throw new AuthRoleMismatchError({ expectedRole, actualRole: user.role });
  }

  return {
    state: "authenticated",
    user: {
      id: user.user_id,
      name: user.email.split("@")[0],
      email: user.email,
      role: user.role,
      accountType: user.account_type ?? "registered",
      availableWorkspaces,
      defaultWorkspace: user.default_workspace ?? user.role,
      avatarPaletteKey: user.avatar_palette_key,
      accessMode: user.access_mode ?? "account",
      termsAcceptedAt: user.terms_accepted_at,
      termsVersion: user.terms_version,
      consentCurrent: user.consent_current ?? false,
    },
  };
});

export const getTrainerSession = cache(async function getTrainerSession(): Promise<SessionState> {
  let session: SessionState | null = null;
  try {
    session = await getSessionFromApi("trainer");
  } catch (error) {
    if (isAuthRoleMismatchError(error) && !isLocalSeededDemoFallbackEnabled()) throw error;
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
});

export const getParticipantSession = cache(async function getParticipantSession(): Promise<SessionState> {
  let session: SessionState | null = null;
  try {
    session = await getSessionFromApi("participant");
  } catch (error) {
    if (isAuthRoleMismatchError(error) && !isLocalSeededDemoFallbackEnabled()) throw error;
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
});

export const getCurrentTrainer = cache(async function getCurrentTrainer(): Promise<CurrentUser> {
  return getTrainerSession().then((session) => session.user);
});

export const getCurrentParticipant = cache(async function getCurrentParticipant(): Promise<CurrentUser> {
  return getParticipantSession().then((session) => session.user);
});
