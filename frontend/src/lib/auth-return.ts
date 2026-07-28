const TRAINER_HOME = "/trainer";
const TRAINER_LOGIN = "/trainer/login";
const INTERNAL_ORIGIN = "https://codrut.invalid";
const PARTICIPANT_HOME = "/participant";

export function safeTrainerReturnTo(value: string | null | undefined): string {
  if (!value) return TRAINER_HOME;

  try {
    const target = new URL(value, INTERNAL_ORIGIN);
    const isInternal = target.origin === INTERNAL_ORIGIN;
    const isTrainerRoute =
      target.pathname === TRAINER_HOME || target.pathname.startsWith(`${TRAINER_HOME}/`);
    const isLoginRoute = target.pathname === TRAINER_LOGIN;

    if (!isInternal || !isTrainerRoute || isLoginRoute) {
      return TRAINER_HOME;
    }

    return `${target.pathname}${target.search}`;
  } catch {
    return TRAINER_HOME;
  }
}

export function trainerLoginHref(returnTo: string | null | undefined): string {
  const safeReturnTo = safeTrainerReturnTo(returnTo);
  if (safeReturnTo === TRAINER_HOME) return TRAINER_LOGIN;

  return `${TRAINER_LOGIN}?returnTo=${encodeURIComponent(safeReturnTo)}`;
}

export function safeParticipantReturnTo(value: string | null | undefined): string {
  if (!value) return PARTICIPANT_HOME;

  try {
    const target = new URL(value, INTERNAL_ORIGIN);
    const isInternal = target.origin === INTERNAL_ORIGIN;
    const isAllowedRoute =
      target.pathname === PARTICIPANT_HOME
      || target.pathname.startsWith(`${PARTICIPANT_HOME}/`)
      || target.pathname.startsWith("/invite/");
    if (!isInternal || !isAllowedRoute || target.pathname === "/login") {
      return PARTICIPANT_HOME;
    }
    return `${target.pathname}${target.search}`;
  } catch {
    return PARTICIPANT_HOME;
  }
}
