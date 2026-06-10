import { getApiBaseUrl } from "./runtime";
import type { ApiRequestOptions } from "./companies";

export type EmailSurfaceStub = {
  id: string;
  name: string;
  lane: "transactional" | "campaign";
};

export type EmailTemplate = {
  id: string;
  baseKey: string;
  version: number;
  name: string;
  subject: string;
  body: string;
  lane: "transactional" | "campaign";
  placeholders: string[];
};

const SEEDED_TEMPLATES: EmailTemplate[] = [
  {
    id: "account_setup",
    baseKey: "account_setup",
    version: 1,
    name: "Invitatie inrolare",
    subject: "Activeaza contul Codrut pentru {company_name}",
    lane: "transactional",
    placeholders: ["{participant_name}", "{trainer_name}", "{company_name}", "{action_url}"],
    body: `<p>Buna, {participant_name}.</p><p>{trainer_name} te-a invitat in Codrut pentru {company_name}.</p><p><a href="{action_url}">Activeaza contul si vezi sarcinile</a></p>`
  },
  {
    id: "assignment_bundle",
    baseKey: "assignment_bundle",
    version: 1,
    name: "Sarcini de completat",
    subject: "Ai chestionare Codrut de completat pentru {company_name}",
    lane: "transactional",
    placeholders: ["{participant_name}", "{company_name}", "{task_count}", "{action_url}"],
    body: `<p>Buna, {participant_name}.</p><p>Ai {task_count} sarcini de assessment pregatite in Codrut.</p><p><a href="{action_url}">Deschide sarcinile mele</a></p>`
  }
];

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function backendToFrontendTemplate(b: any): EmailTemplate {
  const placeholders = (b.variables || []).map((v: string) => `{${v}}`);
  const subject = (b.subject || "").replace(/\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "{$1}");
  const body = (b.html_body || "").replace(/\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "{$1}");

  return {
    id: b.id || `${b.key}@${b.version}`,
    baseKey: b.key,
    version: b.version,
    name: b.key === "account_setup" ? "Invitatie inrolare" : b.key === "assignment_bundle" ? "Sarcini de completat" : b.key,
    subject,
    body,
    lane: b.audience === "campaign" ? "campaign" : "transactional",
    placeholders,
  };
}

function frontendToBackendTemplate(f: EmailTemplate) {
  const variables = (f.placeholders || []).map((p: string) => p.replace(/[{}]/g, ""));
  const subject = (f.subject || "").replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "$${$1}");
  const html_body = (f.body || "").replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "$${$1}");
  const text_body = html_body.replace(/<[^>]*>/g, "");

  return {
    key: f.baseKey,
    subject,
    html_body,
    text_body,
    variables,
    audience: f.lane,
    active: true,
  };
}

export async function listEmailTemplatesOnServer(includeRetired: boolean = false): Promise<EmailTemplate[]> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/communications/templates?include_retired=${includeRetired}`, {
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      return SEEDED_TEMPLATES;
    }
    const data = await response.json();
    return data.map(backendToFrontendTemplate);
  } catch (e) {
    console.error("Error fetching email templates", e);
    return SEEDED_TEMPLATES;
  }
}

export async function getEmailTemplateOnServer(key: string, version?: number): Promise<EmailTemplate | null> {
  try {
    const url = version
      ? `${getApiBaseUrl()}/communications/templates/${key}?version=${version}`
      : `${getApiBaseUrl()}/communications/templates/${key}`;
    const response = await fetch(url, {
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) return null;
    const data = await response.json();
    return backendToFrontendTemplate(data);
  } catch (e) {
    console.error("Error fetching email template", e);
    return null;
  }
}

export async function createEmailTemplateOnServer(template: EmailTemplate): Promise<EmailTemplate> {
  const payload = frontendToBackendTemplate(template);
  const response = await fetch(`${getApiBaseUrl()}/communications/templates`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Nu am putut crea șablonul pe server.");
  }
  const data = await response.json();
  return backendToFrontendTemplate(data);
}

export async function updateEmailTemplateOnServer(template: EmailTemplate): Promise<EmailTemplate> {
  const payload = frontendToBackendTemplate(template);
  const response = await fetch(`${getApiBaseUrl()}/communications/templates/${template.baseKey}?version=${template.version}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Nu am putut actualiza șablonul pe server.");
  }
  const data = await response.json();
  return backendToFrontendTemplate(data);
}

export async function activateEmailTemplateOnServer(key: string, version: number): Promise<EmailTemplate> {
  const response = await fetch(`${getApiBaseUrl()}/communications/templates/${key}/versions/${version}/activate`, {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Nu am putut activa versiunea șablonului.");
  }
  const data = await response.json();
  return backendToFrontendTemplate(data);
}

export async function deleteEmailTemplateOnServer(key: string, version?: number): Promise<EmailTemplate> {
  const url = version
    ? `${getApiBaseUrl()}/communications/templates/${key}?version=${version}`
    : `${getApiBaseUrl()}/communications/templates/${key}`;
  const response = await fetch(url, {
    method: "DELETE",
    credentials: "include",
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Nu am putut pensiona șablonul.");
  }
  const data = await response.json();
  return backendToFrontendTemplate(data);
}

export type EmailDeliveryMetric = {
  label: string;
  value: string;
  detail: string;
};

export type AssessmentDeliveryRow = {
  id: string;
  company_id: string;
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

export async function getEmailOpsSummary(options: ApiRequestOptions = {}): Promise<EmailOpsSummary> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/communications/ops-summary`, {
      cache: "no-store",
      credentials: "include",
      ...options,
    });
    if (!response.ok) {
      throw new Error(`Server returned status ${response.status}`);
    }
    return await response.json();
  } catch (e) {
    console.error("Error fetching email ops summary, using fallback data", e);
    return {
      metrics: [
        { label: "Invitatii trimise", value: "0", detail: "Conturi lideri si linkuri securizate membri." },
        { label: "Au intrat in app", value: "0", detail: "Click pe link sau autentificare cont." },
        { label: "Completate", value: "0", detail: "Toate task-urile din bundle finalizate." },
        { label: "Reminder azi", value: "0", detail: "Invitati sau inceputi fara submit." },
      ],
      assessmentRows: [],
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
        recipients: [],
        weeklyReport: {
          cadence: "Saptamanal",
          metrics: ["open rate", "click rate", "view rate"],
          notification: "Andrei primeste email/Telegram cu link catre raport.",
        },
      },
    };
  }
}
