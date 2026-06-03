export type EmailSurfaceStub = {
  id: string;
  name: string;
  lane: "transactional" | "campaign";
};

export type EmailDeliveryMetric = {
  label: string;
  value: string;
  detail: string;
};

export type AssessmentDeliveryRow = {
  id: string;
  participant: string;
  email: string;
  audience: "leadership_account" | "secure_link";
  project: string;
  tasks: string;
  delivery: "draft" | "sent" | "delivered" | "opened" | "failed";
  reminder: "today" | "tomorrow" | "paused" | "none";
  completion: "not_started" | "in_progress" | "completed";
  nextAction: string;
};

export type EmailOpsSummary = {
  metrics: EmailDeliveryMetric[];
  assessmentRows: AssessmentDeliveryRow[];
  rules: string[];
};

export async function listEmailSurfaceStubs(): Promise<EmailSurfaceStub[]> {
  return [
    { id: "assessment-invites", name: "Invitatii assessment", lane: "transactional" },
    { id: "assessment-reminders", name: "Remindere assessment", lane: "transactional" },
    { id: "video-campaigns", name: "Campaign video links", lane: "campaign" },
  ];
}

export async function getEmailOpsSummary(): Promise<EmailOpsSummary> {
  return {
    metrics: [
      { label: "Invitatii trimise", value: "42", detail: "Conturi lideri si linkuri securizate membri." },
      { label: "Au intrat in app", value: "31", detail: "Click pe link sau autentificare cont." },
      { label: "Completate", value: "18", detail: "Toate task-urile din bundle finalizate." },
      { label: "Reminder azi", value: "9", detail: "Invitati sau inceputi fara submit." },
    ],
    assessmentRows: [
      {
        id: "andrei-popescu",
        participant: "Andrei Popescu",
        email: "andrei.popescu@client.ro",
        audience: "leadership_account",
        project: "Intake Iunie",
        tasks: "4/5",
        delivery: "opened",
        reminder: "tomorrow",
        completion: "in_progress",
        nextAction: "Reminder bland pentru distress drivers",
      },
      {
        id: "mihai-matei",
        participant: "Mihai Matei",
        email: "mihai.matei@client.ro",
        audience: "secure_link",
        project: "Intake Iunie",
        tasks: "1/2",
        delivery: "delivered",
        reminder: "today",
        completion: "in_progress",
        nextAction: "Trimite reminder pentru 360 manager",
      },
      {
        id: "ana-stan",
        participant: "Ana Stan",
        email: "ana.stan@client.ro",
        audience: "secure_link",
        project: "Intake Iunie",
        tasks: "0/2",
        delivery: "sent",
        reminder: "today",
        completion: "not_started",
        nextAction: "Verifica daca linkul a fost accesat",
      },
      {
        id: "elena-radu",
        participant: "Elena Radu",
        email: "elena.radu@client.ro",
        audience: "leadership_account",
        project: "Leadership pilot",
        tasks: "0/5",
        delivery: "failed",
        reminder: "paused",
        completion: "not_started",
        nextAction: "Corecteaza emailul in roster inainte de retrimitere",
      },
    ],
    rules: [
      "Liderii primesc email de cont si pot reveni la task-uri.",
      "Membrii fara cont primesc link securizat per proiect, valabil pana la deadline.",
      "Reminderul se trimite pentru status invitat sau inceput, nu pentru task finalizat.",
      "Emailurile nu includ raspunsuri confidentiale, doar linkuri si status operational.",
    ],
  };
}
