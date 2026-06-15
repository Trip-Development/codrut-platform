import { getApiBaseUrl, isDemoFallbackEnabled } from "./runtime";
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
    name: "Invitație înrolare",
    subject: "Invitație Codruț: activează contul pentru {company_name}",
    lane: "transactional",
    placeholders: ["{participant_name}", "{trainer_name}", "{company_name}", "{action_url}"],
    body: `<p>Bună, {participant_name}.</p><p>{trainer_name} te-a invitat în Codruț pentru {company_name}. După activare vei vedea dashboardul tău de participant și sarcinile pregătite pentru proiect.</p><p><a href="{action_url}">Activează contul</a></p>`
  },
  {
    id: "assignment_bundle",
    baseKey: "assignment_bundle",
    version: 1,
    name: "Sarcini de completat",
    subject: "Chestionarele tale Codruț pentru {company_name}",
    lane: "transactional",
    placeholders: ["{participant_name}", "{company_name}", "{task_count}", "{action_url}"],
    body: `<p>Bună, {participant_name}.</p><p>Pentru {company_name}, trainerul a pregătit {task_count} sarcini într-un link securizat. Răspunsurile sunt tratate confidențial și folosite în agregare.</p><p><a href="{action_url}">Deschide chestionarele</a></p>`
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
    name: b.key === "account_setup" ? "Invitație înrolare" : b.key === "assignment_bundle" ? "Sarcini de completat" : b.key,
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
    if (response.status === 401) {
      throw new Error("Nu sunteți autentificat. Vă rugăm să vă reconectați.");
    }
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
    if (response.status === 401) {
      throw new Error("Nu sunteți autentificat. Vă rugăm să vă reconectați.");
    }
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Nu am putut activa versiunea șablonului.");
  }
  const data = await response.json();
  return backendToFrontendTemplate(data);
}

export async function deleteEmailTemplateOnServer(key: string, version?: number): Promise<EmailTemplate | null> {
  const url = version
    ? `${getApiBaseUrl()}/communications/templates/${key}?version=${version}`
    : `${getApiBaseUrl()}/communications/templates/${key}`;
  const response = await fetch(url, {
    method: "DELETE",
    credentials: "include",
  });
  if (!response.ok) {
    if (response.status === 401) {
      if (isDemoFallbackEnabled()) return null;
      throw new Error("Nu sunteți autentificat. Vă rugăm să vă reconectați.");
    }
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Nu am putut pensiona șablonul.");
  }
  const text = await response.text();
  if (!text) return null;
  const data = JSON.parse(text);
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
    { id: "assessment-invites", name: "Invitații assessment", lane: "transactional" },
    { id: "assessment-reminders", name: "Remindere assessment", lane: "transactional" },
    { id: "video-campaigns", name: "Campanii cu link video", lane: "campaign" },
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
      metrics: [],
      assessmentRows: [],
      rules: [],
      campaign: {
        videoHost: {
          provider: "Codruț watch page + Cloudflare R2",
          status: "needs_upload",
          note: "Emailul trimite thumbnail și CTA către pagina Codruț; video-ul nu este redat direct în email.",
        },
        template: {
          subject: "O idee practică pentru echipa ta, ${first_name}",
          personalization: "Prenumele se completează automat când există nume în bază.",
          ctaPrimary: "Programează o discuție",
          ctaSecondary: "Vreau să fiu contactat",
        },
        recipients: [],
        weeklyReport: {
          cadence: "Săptămânal",
          metrics: ["open rate", "click rate", "view rate"],
          notification: "Andrei primește email/Telegram cu link către raport.",
        },
      },
    };
  }
}

export type CampaignRecipientCreate = {
  email: string;
  contact_name?: string;
  organization_name?: string;
  segment: "past_customer" | "potential_customer";
  source?: string;
};

export async function bulkCreateCampaignRecipientsOnServer(recipients: CampaignRecipientCreate[]) {
  try {
    const response = await fetch(`${getApiBaseUrl()}/communications/campaigns/recipients/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recipients }),
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) {
        return { success: true, count: recipients.length };
      }
      throw new Error(`Failed to upload recipients: ${response.status}`);
    }
    return await response.json();
  } catch (err) {
    if (isDemoFallbackEnabled()) {
      return { success: true, count: recipients.length };
    }
    throw err;
  }
}

export type CampaignCreate = {
  name: string;
  segment: "past_customer" | "potential_customer";
  subject: string;
  html_body: string;
  text_body: string;
  video_url?: string;
  thumbnail_url?: string;
  landing_page_url?: string;
};

export async function createCampaignOnServer(campaign: CampaignCreate) {
  try {
    const response = await fetch(`${getApiBaseUrl()}/communications/campaigns`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(campaign),
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) {
        return { id: "campaign_" + Date.now(), ...campaign };
      }
      throw new Error(`Failed to create campaign: ${response.status}`);
    }
    return await response.json();
  } catch (err) {
    if (isDemoFallbackEnabled()) {
      return { id: "campaign_" + Date.now(), ...campaign };
    }
    throw err;
  }
}

export async function listCampaignsOnServer() {
  try {
    const response = await fetch(`${getApiBaseUrl()}/communications/campaigns`, {
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) return [];
      throw new Error(`Failed to fetch campaigns: ${response.status}`);
    }
    return await response.json();
  } catch (err) {
    if (isDemoFallbackEnabled()) return [];
    throw err;
  }
}
