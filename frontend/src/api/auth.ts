export type CurrentUser = {
  id: string;
  name: string;
  role: "trainer" | "participant";
};

export async function getCurrentTrainer(): Promise<CurrentUser> {
  return {
    id: "trainer-local",
    name: "Andrei",
    role: "trainer",
  };
}

export async function getCurrentParticipant(): Promise<CurrentUser> {
  return {
    id: "participant-local",
    name: "Participant",
    role: "participant",
  };
}
