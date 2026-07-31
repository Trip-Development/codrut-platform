import { apiFetch } from "./http";
import { validatePasswordPolicy } from "./password-policy";
import { getApiBaseUrl, isLocalSeededDemoFallbackEnabled, isSeededDemoFallbackEnabled } from "./runtime";
import { CURRENT_TERMS_VERSION } from "./terms";

export type CurrentUser = {
  id: string;
  name: string;
  email?: string;
  role: "trainer" | "participant";
  accountType?: "guest" | "registered";
  availableWorkspaces?: Array<"trainer" | "participant">;
  defaultWorkspace?: "trainer" | "participant";
  avatarPaletteKey?: number | null;
  accessMode?: "account" | "secure_link";
  termsAcceptedAt?: string | null;
  termsVersion?: string | null;
  consentCurrent?: boolean;
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
  account_type?: "guest" | "registered";
  available_workspaces?: Array<"trainer" | "participant">;
  default_workspace?: "trainer" | "participant";
  avatar_palette_key?: number | null;
  access_mode?: "account" | "secure_link";
  terms_accepted_at?: string | null;
  terms_version?: string | null;
  consent_current?: boolean;
};

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

type AuthSessionUnavailableContext = {
  expectedRole: "trainer" | "participant";
  status?: number;
  reason: "network" | "server" | "payload";
};

type AuthRoleMismatchContext = {
  expectedRole: "trainer" | "participant";
  actualRole: "trainer" | "participant";
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

export class AuthRoleMismatchError extends Error {
  context: AuthRoleMismatchContext;

  constructor(context: AuthRoleMismatchContext) {
    super(`Sesiunea activă este pentru ${context.actualRole}, nu pentru ${context.expectedRole}.`);
    this.name = "AuthRoleMismatchError";
    this.context = context;
  }
}

export function isAuthRoleMismatchError(error: unknown): error is AuthRoleMismatchError {
  return error instanceof AuthRoleMismatchError;
}

function logSessionUnavailable(context: AuthSessionUnavailableContext): void {
  console.warn("[auth] Session check unavailable.", context);
}

export async function loginWithPassword(email: string, password: string): Promise<SessionState> {
  const response = await apiFetch(`${getApiBaseUrl()}/auth/login`, {
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
      accountType: user.account_type ?? "registered",
      availableWorkspaces: user.available_workspaces ?? [user.role],
      defaultWorkspace: user.default_workspace ?? user.role,
      avatarPaletteKey: user.avatar_palette_key,
      accessMode: user.access_mode ?? "account",
      termsAcceptedAt: user.terms_accepted_at,
      termsVersion: user.terms_version,
      consentCurrent: user.consent_current ?? false,
    },
  };
}

function sessionStateFromPrincipal(user: SessionPrincipalResponse): SessionState {
  return {
    state: "authenticated",
    user: {
      id: user.user_id,
      name: user.email.split("@")[0],
      email: user.email,
      role: user.role,
      accountType: user.account_type ?? "registered",
      availableWorkspaces: user.available_workspaces ?? [user.role],
      defaultWorkspace: user.default_workspace ?? user.role,
      avatarPaletteKey: user.avatar_palette_key,
      accessMode: user.access_mode ?? "account",
      termsAcceptedAt: user.terms_accepted_at,
      termsVersion: user.terms_version,
      consentCurrent: user.consent_current ?? false,
    },
  };
}

export function dashboardHrefForRole(role: CurrentUser["role"]): "/trainer" | "/participant" {
  return role === "trainer" ? "/trainer" : "/participant";
}

export function canAccessWorkspace(
  user: CurrentUser,
  workspace: "trainer" | "participant",
): boolean {
  return (user.availableWorkspaces ?? [user.role]).includes(workspace);
}

export async function getAuthenticatedSession(): Promise<SessionState | null> {
  try {
    const response = await apiFetch(`${getApiBaseUrl()}/auth/me`, {
      cache: "no-store",
      credentials: "include",
    });
    if (response.status === 401 || response.status === 403 || !response.ok) return null;
    const user = (await response.json()) as SessionPrincipalResponse;
    if (!user.user_id || !user.email || !user.role) return null;
    return sessionStateFromPrincipal(user);
  } catch {
    return null;
  }
}

export async function requestPasswordReset(email: string): Promise<void> {
  const response = await apiFetch(`${getApiBaseUrl()}/auth/reset-password`, {
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

  const response = await apiFetch(`${getApiBaseUrl()}/auth/reset-password/confirm`, {
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

  const response = await apiFetch(`${getApiBaseUrl()}/auth/change-password`, {
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

export async function acceptCurrentTerms(): Promise<CurrentUser> {
  const response = await apiFetch(`${getApiBaseUrl()}/auth/consent`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      terms_accepted: true,
      terms_version: CURRENT_TERMS_VERSION,
    }),
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const message = payload?.error?.message ?? "Acordul nu a putut fi salvat.";
    throw new Error(message);
  }
  const user = (await response.json()) as AuthApiResponse;
  return sessionStateFromPrincipal(user).user;
}

async function getSessionFromApi(expectedRole: "trainer" | "participant"): Promise<SessionState | null> {
  try {
    const response = await apiFetch(`${getApiBaseUrl()}/auth/me`, {
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
    const availableWorkspaces = user.available_workspaces ?? [user.role];
    if (!availableWorkspaces.includes(expectedRole)) {
      throw new AuthRoleMismatchError({ expectedRole, actualRole: user.role });
    }
    return sessionStateFromPrincipal(user);
  } catch (error) {
    if (isAuthSessionUnavailableError(error) || isAuthRoleMismatchError(error)) throw error;
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
}

export async function getParticipantSession(): Promise<SessionState> {
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
}
