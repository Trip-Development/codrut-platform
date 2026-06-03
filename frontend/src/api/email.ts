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
  campaign: CampaignOpsSummary;
};

export type CampaignRecipientRow = {
  id: string;
  company: string;
  firstName?: string;
  lastName?: string;
  email: string;
  clientType: "tip_1" | "tip_2" | "tip_3" | "tip_4";
  status: "ready" | "needs_contact_name" | "suppressed" | "sent";
  openRate?: string;
  clickRate?: string;
  viewRate?: string;
  outcome?: "intalnire" | "ofertare" | "contract";
};

export type CampaignOpsSummary = {
  videoHost: {
    provider: string;
    status: "ready" | "needs_upload";
    note: string;
  };
  template: {
    subject: string;
    personalization: string;
    ctaPrimary: string;
    ctaSecondary: string;
  };
  recipients: CampaignRecipientRow[];
  weeklyReport: {
    cadence: string;
    metrics: string[];
    notification: string;
  };
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
    campaign: {
      videoHost: {
        provider: "Codrut watch page + Cloudflare R2",
        status: "needs_upload",
        note: "Emailul trimite thumbnail si CTA catre pagina Codrut; video-ul nu este redat direct in email.",
      },
      template: {
        subject: "O idee practica pentru echipa ta, ${first_name}",
        personalization: "Prenumele se completeaza automat cand exista nume in baza.",
        ctaPrimary: "Programeaza o discutie",
        ctaSecondary: "Vreau sa fiu contactat",
      },
      recipients: [
        {
          id: "rec-1",
          company: "Client activ",
          firstName: "Maria",
          lastName: "Pop",
          email: "maria.pop@clientactiv.ro",
          clientType: "tip_1",
          status: "ready",
          openRate: "72%",
          clickRate: "18%",
          viewRate: "12%",
          outcome: "intalnire",
        },
        {
          id: "rec-2",
          company: "Client trecut cunoscut",
          firstName: "Sorin",
          lastName: "Dima",
          email: "sorin.dima@clienttrecut.ro",
          clientType: "tip_2",
          status: "sent",
          openRate: "54%",
          clickRate: "9%",
          viewRate: "7%",
          outcome: "ofertare",
        },
        {
          id: "rec-3",
          company: "Client trecut fara contact",
          email: "office@companie.ro",
          clientType: "tip_3",
          status: "needs_contact_name",
        },
        {
          id: "rec-4",
          company: "Prospect nou",
          firstName: "Irina",
          lastName: "Muresan",
          email: "irina@prospect.ro",
          clientType: "tip_4",
          status: "suppressed",
        },
      ],
      weeklyReport: {
        cadence: "Saptamanal",
        metrics: ["open rate", "click rate", "view rate"],
        notification: "Andrei primeste email/Telegram cu link catre raport.",
      },
    },
  };
}
