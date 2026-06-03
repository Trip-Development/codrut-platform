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

export async function getCurrentTrainer(): Promise<CurrentUser> {
  return getTrainerSession().then((session) => session.user);
}

export async function getCurrentParticipant(): Promise<CurrentUser> {
  return getParticipantSession().then((session) => session.user);
}

export async function getTrainerSession(): Promise<SessionState> {
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
