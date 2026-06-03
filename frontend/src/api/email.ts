export type EmailSurfaceStub = {
  id: string;
  name: string;
  lane: "transactional" | "campaign";
};

export async function listEmailSurfaceStubs(): Promise<EmailSurfaceStub[]> {
  return [
    { id: "assessment-invites", name: "Invitatii assessment", lane: "transactional" },
    { id: "assessment-reminders", name: "Remindere assessment", lane: "transactional" },
    { id: "video-campaigns", name: "Campaign video links", lane: "campaign" },
  ];
}
