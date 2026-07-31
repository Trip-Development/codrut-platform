import { apiFetch } from "./http";
import { getApiBaseUrl, isDemoFallbackEnabled, isSeededDemoFallbackEnabled } from "./runtime";
import type { ApiRequestOptions } from "./companies";
import type { components } from "./generated/schema";

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
  textBody?: string;
  lane: "transactional" | "campaign";
  audience?: string | null;
  placeholders: string[];
};

type EmailTemplateResponse = components["schemas"]["EmailTemplateResponse"];

const SYNTHETIC_CAMPAIGN_PLACEHOLDERS = [
  "{first_name}",
  "{landing_page_url}",
  "{thumbnail_url}",
  "{unsubscribe_url}",
  "{legal_address}",
];
const SYNTHETIC_EVALUATION_PLACEHOLDERS = [
  "{participant_name}",
  "{company_name}",
  "{action_url}",
  "{due_date}",
  "{sender_name}",
];

const SEEDED_TEMPLATES: EmailTemplate[] = [
  {
    id: "preview_campaign_update@1",
    baseKey: "preview_campaign_update",
    version: 1,
    name: "Mostră campanie: actualizare",
    subject: "Actualizare demonstrativă pentru {first_name}",
    lane: "campaign",
    audience: "campaign:past_customer",
    placeholders: SYNTHETIC_CAMPAIGN_PLACEHOLDERS,
    body: '<h1>Actualizare demonstrativă</h1><p>Salut, {first_name}. Acesta este conținut sintetic pentru verificarea editorului.</p><p><a href="{landing_page_url}">Deschide materialul demonstrativ</a></p><p><a href="{unsubscribe_url}">Dezabonare</a></p><p>{legal_address}</p>',
    textBody: "Salut, {first_name}. Acesta este conținut sintetic pentru verificarea editorului. Material: {landing_page_url}. Dezabonare: {unsubscribe_url}. {legal_address}",
  },
  {
    id: "preview_campaign_intro@1",
    baseKey: "preview_campaign_intro",
    version: 1,
    name: "Mostră campanie: introducere",
    subject: "Mesaj demonstrativ pentru {first_name}",
    lane: "campaign",
    audience: "campaign:potential_customer",
    placeholders: SYNTHETIC_CAMPAIGN_PLACEHOLDERS,
    body: '<h1>Mesaj demonstrativ</h1><p>Salut, {first_name}. Folosește această mostră pentru a verifica previzualizarea și destinatarii.</p><p><a href="{landing_page_url}">Vezi exemplul</a></p><p><a href="{unsubscribe_url}">Dezabonare</a></p><p>{legal_address}</p>',
    textBody: "Salut, {first_name}. Folosește această mostră pentru a verifica previzualizarea și destinatarii. Exemplu: {landing_page_url}. Dezabonare: {unsubscribe_url}. {legal_address}",
  },
  {
    id: "preview_evaluation_invite@1",
    baseKey: "preview_evaluation_invite",
    version: 1,
    name: "Mostră invitație evaluare",
    subject: "Ai o activitate demonstrativă de completat",
    lane: "transactional",
    audience: "transactional:leadership",
    placeholders: SYNTHETIC_EVALUATION_PLACEHOLDERS,
    body: '<h1>Activitate demonstrativă</h1><p>Salut, {participant_name}. Deschide activitățile sintetice pentru {company_name} până la {due_date}.</p><p><a href="{action_url}">Deschide activitățile</a></p><p>{sender_name}</p>',
    textBody: "Salut, {participant_name}. Deschide activitățile sintetice pentru {company_name} până la {due_date}: {action_url}. {sender_name}",
  },
  {
    id: "preview_evaluation_reminder@1",
    baseKey: "preview_evaluation_reminder",
    version: 1,
    name: "Mostră reminder evaluare",
    subject: "Reminder demonstrativ pentru activitățile tale",
    lane: "transactional",
    audience: "transactional:team",
    placeholders: SYNTHETIC_EVALUATION_PLACEHOLDERS,
    body: '<h1>Reminder demonstrativ</h1><p>Salut, {participant_name}. Activitățile sintetice rămân disponibile până la {due_date}.</p><p><a href="{action_url}">Continuă activitățile</a></p><p>{sender_name}</p>',
    textBody: "Salut, {participant_name}. Activitățile sintetice rămân disponibile până la {due_date}: {action_url}. {sender_name}",
  },
];

function getSeededTemplates(): EmailTemplate[] {
  return SEEDED_TEMPLATES.map((template) => ({
    ...template,
    placeholders: [...template.placeholders],
  }));
}

function backendToFrontendTemplate(b: EmailTemplateResponse): EmailTemplate {
  const placeholders = (b.variables || []).map((v: string) => `{${v}}`);
  const subject = (b.subject || "").replace(/\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "{$1}");
  const body = (b.html_body || "").replace(/\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "{$1}");
  const textBody = (b.text_body || "").replace(/\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "{$1}");

  return {
    id: b.id || `${b.key}@${b.version}`,
    baseKey: b.key,
    version: b.version,
    name: templateDisplayName(b.key),
    subject,
    body,
    textBody,
    lane: String(b.audience || "").startsWith("campaign") ? "campaign" : "transactional",
    audience: b.audience ?? null,
    placeholders,
  };
}

function templateDisplayName(key: string): string {
  const names: Record<string, string> = {
    account_setup: "Invitație înrolare",
    assignment_bundle: "Sarcini de completat",
    promo_past_report_2022_2025: "Promo clienți vechi - raport 2022-2025",
    promo_past_reactivation: "Promo clienți vechi - reactivare",
    promo_current_programs: "Promo clienți existenți - programe noi",
    promo_potential_intro: "Promo prospect - prima interacțiune",
    evaluation_leadership_invite: "Evaluare leadership - invitație",
    evaluation_leadership_reminder: "Evaluare leadership - reminder",
    evaluation_team_invite: "Evaluare echipe - invitație",
    evaluation_team_reminder: "Evaluare echipe - reminder",
    local_preview_follow_up: "Urmărire evaluare",
  };
  return names[key] ?? key;
}

export function htmlToPlainText(html: string): string {
  return html
    .replace(/<script[\s\S]*?<\/script>/gi, "")
    .replace(/<style[\s\S]*?<\/style>/gi, "")
    .replace(
      /<a\b([^>]*?)href=(["'])(.*?)\2([^>]*)>([\s\S]*?)<\/a>/gi,
      (_match, _before: string, _quote: string, href: string, _after: string, label: string) => (
        label.includes(href) ? label : `${label} ${href}`
      ),
    )
    .replace(/<img\b[^>]*\balt=(["'])(.*?)\1[^>]*>/gi, "$2")
    .replace(/<\/td>\s*<td[^>]*>/gi, " ")
    .replace(/<br\s*\/?>/gi, "\n")
    .replace(/<\/(p|div|h[1-6]|li|tr|table|ul|ol)>/gi, "\n")
    .replace(/<[^>]*>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&amp;/g, "&")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&#9654;/g, "▶")
    .split("\n")
    .map((line) => line.replace(/[ \t]+/g, " ").trim())
    .filter(Boolean)
    .join("\n");
}

function extractEmailVariables(...values: Array<string | undefined>): string[] {
  const variables = new Set<string>();
  const pattern = /(?:\$\{|\{)([a-zA-Z_][a-zA-Z0-9_]*)(?:\}|\})/g;
  for (const value of values) {
    if (!value) continue;
    for (const match of value.matchAll(pattern)) {
      variables.add(match[1]);
    }
  }
  return Array.from(variables);
}

function frontendToBackendTemplate(f: EmailTemplate) {
  const subject = (f.subject || "").replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "$${$1}");
  const html_body = (f.body || "").replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "$${$1}");
  const text_body = f.textBody?.trim()
    ? f.textBody.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "$${$1}")
    : htmlToPlainText(html_body);
  const variables = extractEmailVariables(
    ...(f.placeholders || []),
    subject,
    html_body,
    text_body,
  );

  return {
    key: f.baseKey,
    subject,
    html_body,
    text_body,
    variables,
    audience: f.audience ?? f.lane,
    active: true,
  };
}

export async function listEmailTemplatesOnServer(includeRetired: boolean = false): Promise<EmailTemplate[]> {
  if (typeof window !== "undefined" && !process.env.VITEST && isDemoFallbackEnabled()) {
    return getSeededTemplates();
  }

  try {
    const response = await apiFetch(`${getApiBaseUrl()}/communications/templates?include_retired=${includeRetired}`, {
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isSeededDemoFallbackEnabled()) {
        return getSeededTemplates();
      }
      throw new Error(`Server returned status ${response.status}`);
    }
    const data = await response.json();
    return data.map(backendToFrontendTemplate);
  } catch (e) {
    if (isSeededDemoFallbackEnabled()) {
      return getSeededTemplates();
    }
    throw e;
  }
}

export async function getEmailTemplateOnServer(key: string, version?: number): Promise<EmailTemplate | null> {
  try {
    const url = version
      ? `${getApiBaseUrl()}/communications/templates/${key}?version=${version}`
      : `${getApiBaseUrl()}/communications/templates/${key}`;
    const response = await apiFetch(url, {
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
  if (typeof window !== "undefined" && !process.env.VITEST && isDemoFallbackEnabled()) {
    return {
      ...template,
      placeholders: [...template.placeholders],
    };
  }

  const payload = frontendToBackendTemplate(template);
  const response = await apiFetch(`${getApiBaseUrl()}/communications/templates`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    if (isDemoFallbackEnabled()) {
      return {
        ...template,
        placeholders: [...template.placeholders],
      };
    }
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Nu am putut crea șablonul pe server.");
  }
  const data = await response.json();
  return backendToFrontendTemplate(data);
}

export async function updateEmailTemplateOnServer(template: EmailTemplate): Promise<EmailTemplate> {
  if (typeof window !== "undefined" && !process.env.VITEST && isDemoFallbackEnabled()) {
    return {
      ...template,
      placeholders: [...template.placeholders],
    };
  }

  const payload = frontendToBackendTemplate(template);
  const response = await apiFetch(`${getApiBaseUrl()}/communications/templates/${template.baseKey}?version=${template.version}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    if (isDemoFallbackEnabled()) {
      return {
        ...template,
        placeholders: [...template.placeholders],
      };
    }
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
  const response = await apiFetch(`${getApiBaseUrl()}/communications/templates/${key}/versions/${version}/activate`, {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok) {
    if (response.status === 401) {
      if (isDemoFallbackEnabled()) {
        return {
          id: `${key}@${version}`,
          baseKey: key,
          version,
          name: key,
          subject: "",
          body: "",
          lane: "transactional",
          placeholders: [],
        };
      }
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
  const response = await apiFetch(url, {
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

export type EmailSendCapacity = {
  daily_cap: number;
  used_today: number;
  remaining_today: number;
};

export type CampaignRecipientRow = {
  id: string;
  company: string;
  firstName?: string;
  lastName?: string;
  email: string;
  clientType: "tip_1" | "tip_2" | "tip_3" | "tip_4";
  status: "ready" | "needs_contact_name" | "suppressed" | "unsubscribed" | "sent" | "archived";
  activationAllowed: boolean;
  archivedAt?: string | null;
  purgeAfter?: string | null;
  statusBeforeArchive?: "active" | "suppressed" | "unsubscribed" | null;
  openRate?: string;
  clickRate?: string;
  viewRate?: string;
  openCount?: number;
  clickCount?: number;
  viewCount?: number;
  replyCount?: number;
  calendlyClickCount?: number;
  source?: string | null;
  emailVariant?: string | null;
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

export type CampaignRecipientMembershipRow = CampaignRecipientRow & {
  membershipSource?: string | null;
  campaignDelivery?: "not_sent" | "queued" | "sent" | "failed";
};

const SEEDED_CAMPAIGN_RECIPIENTS: CampaignRecipientRow[] = [
  {
    id: "campaign-atlas-ceo",
    company: "Atlas Mobility",
    firstName: "Radu",
    lastName: "Munteanu",
    email: "radu.munteanu@atlas.example.com",
    clientType: "tip_1",
    status: "sent",
    activationAllowed: false,
    openCount: 3,
    clickCount: 2,
    viewCount: 1,
    replyCount: 1,
    calendlyClickCount: 1,
    emailVariant: "variant_a",
    outcome: "intalnire",
  },
  {
    id: "campaign-meridian-director",
    company: "Clinica Meridian",
    firstName: "Diana",
    lastName: "Ene",
    email: "diana.ene@meridian.example.com",
    clientType: "tip_1",
    status: "ready",
    activationAllowed: false,
    openCount: 1,
    clickCount: 1,
    viewCount: 1,
    replyCount: 0,
    calendlyClickCount: 0,
    emailVariant: "variant_b",
  },
  {
    id: "campaign-nova-retail",
    company: "Nova Retail Group",
    firstName: "Cristina",
    lastName: "Olaru",
    email: "cristina.olaru@nova.example.com",
    clientType: "tip_2",
    status: "needs_contact_name",
    activationAllowed: false,
    openCount: 0,
    clickCount: 0,
    viewCount: 0,
    replyCount: 0,
    calendlyClickCount: 0,
    emailVariant: "variant_a",
  },
  {
    id: "campaign-suppressed",
    company: "Fabrica Nord",
    email: "office@fabrica.example.com",
    clientType: "tip_2",
    status: "suppressed",
    activationAllowed: false,
    openCount: 0,
    clickCount: 0,
    viewCount: 0,
    replyCount: 0,
    calendlyClickCount: 0,
    emailVariant: "variant_c",
  },
];

function getSeededCampaignRecipients(): CampaignRecipientRow[] {
  return SEEDED_CAMPAIGN_RECIPIENTS.map((recipient) => ({ ...recipient }));
}

export async function listEmailSurfaceStubs(): Promise<EmailSurfaceStub[]> {
  return [
    { id: "assessment-invites", name: "Invitații assessment", lane: "transactional" },
    { id: "assessment-reminders", name: "Remindere assessment", lane: "transactional" },
    { id: "video-campaigns", name: "Campanii cu link video", lane: "campaign" },
  ];
}

export type EmailOpsSummaryOptions = ApiRequestOptions & {
  catalogScope?: "active" | "archived";
};

export async function getEmailOpsSummary(options: EmailOpsSummaryOptions = {}): Promise<EmailOpsSummary> {
  const { catalogScope = "active", ...requestOptions } = options;
  try {
    const search = new URLSearchParams({ catalog_scope: catalogScope });
    const response = await apiFetch(`${getApiBaseUrl()}/communications/ops-summary?${search}`, {
      cache: "no-store",
      credentials: "include",
      ...requestOptions,
    });
    if (!response.ok) {
      throw new Error(`Server returned status ${response.status}`);
    }
    return await response.json();
  } catch (e) {
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
    return {
      metrics: [],
      assessmentRows: [],
      rules: [],
      campaign: {
        videoHost: {
          provider: "Vimeo sau pagină Cody",
          status: "ready",
          note: "Emailul trimite thumbnail și CTA către linkul video. Pagina Cody este opțională pentru tracking sau CTA-uri dedicate.",
        },
        template: {
          subject: "O idee practică pentru echipa ta, ${first_name}",
          personalization: "Prenumele se completează automat când există nume în bază.",
          ctaPrimary: "Programează o discuție",
          ctaSecondary: "Vreau să fiu contactat",
        },
        recipients: readDemoCampaignRecipients().filter((recipient) =>
          catalogScope === "archived"
            ? recipient.status === "archived"
            : recipient.status !== "archived",
        ),
        weeklyReport: {
          cadence: "Săptămânal",
          metrics: ["deschideri", "clickuri", "vizualizări video", "reply-uri", "clickuri Calendly", "variantă email"],
          notification: "Andrei primește email/Telegram cu link către raport.",
        },
      },
    };
  }
}

export async function getEmailSendCapacity(): Promise<EmailSendCapacity> {
  try {
    const response = await apiFetch(
      `${getApiBaseUrl()}/communications/send-capacity`,
      {
        cache: "no-store",
        credentials: "include",
      },
    );
    if (!response.ok) {
      throw new Error(`Server returned status ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    if (!isDemoFallbackEnabled()) throw error;
    return {
      daily_cap: 2000,
      used_today: 0,
      remaining_today: 2000,
    };
  }
}

export type CampaignRecipientCreate = {
  email?: string;
  contact_name?: string;
  organization_name?: string;
  segment: "past_customer" | "potential_customer";
  status?: "active" | "suppressed";
  source?: string;
};

export type CampaignRecipientBulkCreateResponse = {
  status: "success";
  count: number;
  created?: number;
  updated?: number;
};

export type CampaignRecipientUpdate = Omit<Partial<CampaignRecipientCreate>, "status"> & {
  status?: "active" | "suppressed" | "unsubscribed";
};

export type CampaignRecipientArchiveResponse = {
  id: string;
  status: "archived";
  archived_at: string;
  purge_after: string;
  memberships_removed: number;
  cancelled: number;
  in_flight: number;
};

export type CampaignRecipientRestoreResponse = {
  id: string;
  status: "active" | "suppressed" | "unsubscribed";
  archived_at: null;
  purge_after: null;
};

export type CampaignRecipientPermanentDeleteResponse = {
  id: string;
  status: "deleted";
  cancelled: number;
  anonymized_sends: number;
};

function permanentDeleteContactErrorMessage(
  errorBody: unknown,
  fallback: string,
): string {
  const error = errorBody && typeof errorBody === "object"
    ? (errorBody as { error?: { code?: unknown; message?: unknown } }).error
    : undefined;
  if (error?.code === "campaign_recipient_purge_disabled") {
    return "Ștergerea definitivă va fi disponibilă după finalizarea actualizării de confidențialitate. Contactul rămâne în siguranță în Arhivă și nu poate fi folosit în campanii.";
  }
  return typeof error?.message === "string" && error.message.trim()
    ? error.message
    : fallback;
}

export async function bulkCreateCampaignRecipientsOnServer(
  recipients: CampaignRecipientCreate[],
): Promise<CampaignRecipientBulkCreateResponse> {
  try {
    const response = await apiFetch(`${getApiBaseUrl()}/communications/campaigns/recipients/bulk`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recipients }),
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) {
        return bulkCreateDemoCampaignRecipients(recipients);
      }
      throw new Error(`Failed to upload recipients: ${response.status}`);
    }
    return await response.json();
  } catch (err) {
    if (isDemoFallbackEnabled()) {
      return bulkCreateDemoCampaignRecipients(recipients);
    }
    throw err;
  }
}

export async function updateCampaignRecipientOnServer(
  recipientId: string,
  recipient: CampaignRecipientUpdate,
) {
  try {
    const response = await apiFetch(`${getApiBaseUrl()}/communications/campaigns/recipients/${recipientId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(recipient),
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) return updateDemoCampaignRecipient(recipientId, recipient);
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.error?.message ?? `Nu am putut actualiza contactul (${response.status}).`);
    }
    return await response.json();
  } catch (err) {
    if (isDemoFallbackEnabled()) return updateDemoCampaignRecipient(recipientId, recipient);
    throw err;
  }
}

export async function deleteCampaignRecipientOnServer(recipientId: string): Promise<void> {
  try {
    const response = await apiFetch(`${getApiBaseUrl()}/communications/campaigns/recipients/${recipientId}`, {
      method: "DELETE",
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) {
        deleteDemoCampaignRecipient(recipientId);
        return;
      }
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.error?.message ?? `Nu am putut șterge contactul (${response.status}).`);
    }
  } catch (err) {
    if (isDemoFallbackEnabled()) {
      deleteDemoCampaignRecipient(recipientId);
      return;
    }
    throw err;
  }
}

export async function archiveCampaignRecipientOnServer(
  recipientId: string,
): Promise<CampaignRecipientArchiveResponse> {
  try {
    const response = await apiFetch(
      `${getApiBaseUrl()}/communications/campaigns/recipients/${recipientId}/archive`,
      {
        method: "POST",
        cache: "no-store",
        credentials: "include",
      },
    );
    if (!response.ok) {
      if (isDemoFallbackEnabled()) return archiveDemoCampaignRecipient(recipientId);
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.error?.message ?? `Nu am putut arhiva contactul (${response.status}).`);
    }
    return await response.json();
  } catch (error) {
    if (isDemoFallbackEnabled()) return archiveDemoCampaignRecipient(recipientId);
    throw error;
  }
}

export async function restoreCampaignRecipientOnServer(
  recipientId: string,
): Promise<CampaignRecipientRestoreResponse> {
  try {
    const response = await apiFetch(
      `${getApiBaseUrl()}/communications/campaigns/recipients/${recipientId}/restore`,
      {
        method: "POST",
        cache: "no-store",
        credentials: "include",
      },
    );
    if (!response.ok) {
      if (isDemoFallbackEnabled()) return restoreDemoCampaignRecipient(recipientId);
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.error?.message ?? `Nu am putut restaura contactul (${response.status}).`);
    }
    return await response.json();
  } catch (error) {
    if (isDemoFallbackEnabled()) return restoreDemoCampaignRecipient(recipientId);
    throw error;
  }
}

export async function permanentlyDeleteCampaignRecipientOnServer(
  recipientId: string,
): Promise<CampaignRecipientPermanentDeleteResponse> {
  try {
    const response = await apiFetch(
      `${getApiBaseUrl()}/communications/campaigns/recipients/${recipientId}/permanent`,
      {
        method: "DELETE",
        cache: "no-store",
        credentials: "include",
      },
    );
    if (!response.ok) {
      if (isDemoFallbackEnabled()) return permanentlyDeleteDemoCampaignRecipient(recipientId);
      const errorBody = await response.json().catch(() => null);
      throw new Error(permanentDeleteContactErrorMessage(
        errorBody,
        `Nu am putut șterge definitiv contactul (${response.status}).`,
      ));
    }
    return await response.json();
  } catch (error) {
    if (isDemoFallbackEnabled()) return permanentlyDeleteDemoCampaignRecipient(recipientId);
    throw error;
  }
}

function campaignMembershipRowsFromPayload(payload: unknown): CampaignRecipientMembershipRow[] {
  if (Array.isArray(payload)) {
    return payload as CampaignRecipientMembershipRow[];
  }
  if (payload && typeof payload === "object" && Array.isArray((payload as { recipients?: unknown }).recipients)) {
    return (payload as { recipients: CampaignRecipientMembershipRow[] }).recipients;
  }
  return [];
}

export async function listCampaignRecipientMembershipOnServer(
  campaignId: string,
): Promise<CampaignRecipientMembershipRow[]> {
  try {
    const response = await apiFetch(`${getApiBaseUrl()}/communications/campaigns/${campaignId}/recipients`, {
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) return readDemoCampaignMembershipRows(campaignId);
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.error?.message ?? `Nu am putut încărca destinatarii campaniei (${response.status}).`);
    }
    return campaignMembershipRowsFromPayload(await response.json());
  } catch (err) {
    if (isDemoFallbackEnabled()) return readDemoCampaignMembershipRows(campaignId);
    throw err;
  }
}

export async function replaceCampaignRecipientMembershipOnServer(
  campaignId: string,
  recipientIds: string[],
): Promise<CampaignRecipientMembershipRow[]> {
  try {
    const response = await apiFetch(`${getApiBaseUrl()}/communications/campaigns/${campaignId}/recipients`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ recipient_ids: recipientIds }),
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) return replaceDemoCampaignMembershipRows(campaignId, recipientIds);
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.error?.message ?? `Nu am putut salva destinatarii campaniei (${response.status}).`);
    }
    if (response.status === 204) return [];
    return campaignMembershipRowsFromPayload(await response.json());
  } catch (err) {
    if (isDemoFallbackEnabled()) return replaceDemoCampaignMembershipRows(campaignId, recipientIds);
    throw err;
  }
}

export type CampaignCreate = {
  name: string;
  segment: "past_customer" | "potential_customer" | null;
  subject: string;
  html_body: string;
  text_body: string;
  video_url?: string;
  thumbnail_url?: string;
  landing_page_url?: string;
};

export type CampaignUpdate = Omit<Partial<CampaignCreate>, "video_url" | "thumbnail_url" | "landing_page_url"> & {
  status?: "draft" | "ready" | "paused" | "completed";
  video_url?: string | null;
  thumbnail_url?: string | null;
  landing_page_url?: string | null;
};

export type CampaignAssetUpload = {
  url: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
};

export type CampaignValidationDetail = {
  loc?: Array<string | number>;
  message?: string;
  type?: string;
};

export class CampaignPersistenceError extends Error {
  constructor(
    message: string,
    readonly status?: number,
    readonly code?: string,
    readonly details: CampaignValidationDetail[] = [],
    readonly requestId?: string,
  ) {
    super(message);
    this.name = "CampaignPersistenceError";
  }
}

function campaignPersistenceError(
  response: Response,
  payload: unknown,
  fallbackMessage: string,
): CampaignPersistenceError {
  const envelope = payload && typeof payload === "object" && "error" in payload
    ? (payload as { error?: unknown }).error
    : null;
  const error = envelope && typeof envelope === "object"
    ? envelope as Record<string, unknown>
    : {};
  const details = Array.isArray(error.details)
    ? error.details.flatMap((detail): CampaignValidationDetail[] => {
      if (!detail || typeof detail !== "object") return [];
      const row = detail as Record<string, unknown>;
      const location = Array.isArray(row.loc) ? row.loc : Array.isArray(row.path) ? row.path : undefined;
      return [{
        ...(location ? { loc: location.map((item) => typeof item === "number" ? item : String(item)) } : {}),
        ...(typeof row.message === "string" ? { message: row.message } : {}),
        ...(typeof row.type === "string" ? { type: row.type } : {}),
      }];
    })
    : [];
  return new CampaignPersistenceError(
    typeof error.message === "string" ? error.message : fallbackMessage,
    response.status,
    typeof error.code === "string" ? error.code : undefined,
    details,
    typeof error.request_id === "string"
      ? error.request_id
      : response.headers.get("X-Request-ID") ?? undefined,
  );
}

export async function uploadCampaignAssetOnServer(file: File): Promise<CampaignAssetUpload> {
  const response = await apiFetch(`${getApiBaseUrl()}/communications/campaign-assets`, {
    method: "POST",
    headers: {
      "Content-Type": file.type || "application/octet-stream",
      "X-File-Name": encodeURIComponent(file.name || "thumbnail"),
    },
    body: file,
    cache: "no-store",
    credentials: "include",
  });
  if (!response.ok) {
    const errorBody = await response.json().catch(() => null);
    throw new Error(errorBody?.error?.message ?? "Thumbnailul nu a putut fi încărcat.");
  }
  return await response.json();
}

export async function deleteCampaignAssetOnServer(fileName: string): Promise<void> {
  if (isDemoFallbackEnabled()) return;
  const response = await apiFetch(
    `${getApiBaseUrl()}/communications/campaign-assets/${encodeURIComponent(fileName)}`,
    {
      method: "DELETE",
      cache: "no-store",
      credentials: "include",
    },
  );
  if (!response.ok && response.status !== 404) {
    throw new Error(`Nu am putut curăța imaginea campaniei (${response.status}).`);
  }
}

export function campaignAssetFileNameFromUrl(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const url = new URL(value, "http://localhost");
    const marker = "/campaign-assets/";
    const markerIndex = url.pathname.lastIndexOf(marker);
    if (markerIndex === -1) return null;
    const fileName = decodeURIComponent(url.pathname.slice(markerIndex + marker.length));
    return /^[a-z0-9-]+\.(?:gif|jpe?g|png|webp)$/i.test(fileName) ? fileName : null;
  } catch {
    return null;
  }
}

export type CampaignVideoDraft = {
  name: string;
  segment: "past_customer" | "potential_customer" | null;
  subject: string;
  htmlBody?: string;
  textBody?: string;
  videoUrl?: string;
  thumbnailUrl?: string;
  landingUrl?: string;
};

function normalizeHttpUrl(value: string | undefined): string | null {
  if (!value?.trim()) return null;
  try {
    const url = new URL(value.trim());
    if (url.protocol !== "https:" && url.protocol !== "http:") return null;
    return url.toString();
  } catch {
    return null;
  }
}

function appendCampaignHtmlBlock(htmlBody: string, block: string): string {
  const footerMarker = '</div><div style="margin-top:24px;padding-top:24px;border-top:1px solid #eadfdb;';
  if (htmlBody.includes(footerMarker)) {
    return htmlBody.replace(footerMarker, `${block}${footerMarker}`);
  }
  const shellClose = "</div></div>";
  const trimmedBody = htmlBody.trimEnd();
  if (trimmedBody.endsWith(shellClose)) {
    return `${trimmedBody.slice(0, -shellClose.length)}${block}${shellClose}`;
  }
  return `${htmlBody}${block}`;
}

export function buildVideoCampaignCreatePayload(draft: CampaignVideoDraft): CampaignCreate | null {
  const trimmedName = draft.name.trim();
  const hasVideoInput = Boolean(draft.videoUrl?.trim());
  const hasThumbnailInput = Boolean(draft.thumbnailUrl?.trim());
  const hasLandingInput = Boolean(draft.landingUrl?.trim());
  const videoUrl = normalizeHttpUrl(draft.videoUrl);
  const thumbnailUrl = normalizeHttpUrl(draft.thumbnailUrl);
  const landingUrl = normalizeHttpUrl(draft.landingUrl) ?? videoUrl;
  const hasVideoBlock = Boolean(videoUrl && thumbnailUrl);
  const hasImageBlock = Boolean(thumbnailUrl && !videoUrl);

  if (!trimmedName) return null;
  if (hasVideoInput && !videoUrl) return null;
  if (hasThumbnailInput && !thumbnailUrl) return null;
  if (hasLandingInput && !normalizeHttpUrl(draft.landingUrl)) return null;
  if (hasVideoInput && !thumbnailUrl) return null;

  const videoMediaBlockHtml = hasVideoBlock
    ? [
        '<p><a href="${landing_page_url}" style="display:block;text-decoration:none;color:inherit;">',
        `<span style="display:block;position:relative;max-width:420px;border-radius:14px;overflow:hidden;background:#2b211f;">`,
        '<img src="${thumbnail_url}" alt="Previzualizare video" style="display:block;width:100%;max-width:420px;height:auto;border:0;border-radius:14px;" />',
        `<span style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:64px;height:64px;border-radius:999px;background:rgba(255,255,255,.9);box-shadow:0 14px 35px rgba(0,0,0,.22);text-align:center;line-height:64px;color:#890505;font-size:28px;font-weight:700;">&#9654;</span>`,
        "</span>",
        "</a></p>",
      ].join("")
    : "";
  const videoDefaultHtml = hasVideoBlock
    ? [
        "<p>Bună, ${first_name}.</p>",
        "<p>Am pregătit un material video scurt pentru contextul echipei tale.</p>",
        videoMediaBlockHtml,
      ].join("")
    : "";
  const imageBlockHtml = hasImageBlock
    ? '<p><img src="${thumbnail_url}" alt="Imagine campanie" style="display:block;width:100%;max-width:420px;height:auto;border:0;border-radius:14px;" /></p>'
    : "";
  const authoredHtmlBody = draft.htmlBody?.trim()
    ? draft.htmlBody.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "$${$1}")
    : "";
  const hasAuthoredThumbnail = /<img\b[^>]*\bsrc=(["'])[^"']*\$\{thumbnail_url\}[^"']*\1/i
    .test(authoredHtmlBody);
  const htmlBody = authoredHtmlBody
    ? hasVideoBlock && !hasAuthoredThumbnail
      ? appendCampaignHtmlBlock(authoredHtmlBody, videoMediaBlockHtml)
      : hasImageBlock && !hasAuthoredThumbnail
        ? appendCampaignHtmlBlock(authoredHtmlBody, imageBlockHtml)
        : authoredHtmlBody
    : hasVideoBlock
      ? videoDefaultHtml
      : hasImageBlock
        ? `<p>Bună, \${first_name}.</p>${imageBlockHtml}`
        : "<p>Bună, ${first_name}.</p><p>Dacă vrei, alege un slot în Calendly și stabilim o conversație.</p>";
  const textBody = draft.textBody?.trim()
    ? draft.textBody.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "$${$1}")
    : hasVideoBlock
      ? "Bună, ${first_name}. Vezi video-ul aici: ${landing_page_url}"
      : hasImageBlock
        ? "Bună, ${first_name}. Am pregătit o actualizare pentru tine."
      : "Bună, ${first_name}. Dacă vrei, alege un slot în Calendly și stabilim o conversație.";

  return {
    name: trimmedName,
    segment: draft.segment,
    subject: draft.subject.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "$${$1}"),
    html_body: htmlBody,
    text_body: textBody,
    video_url: videoUrl ?? undefined,
    thumbnail_url: thumbnailUrl ?? undefined,
    landing_page_url: landingUrl && landingUrl !== videoUrl ? landingUrl : undefined,
  };
}

export type EmailCampaign = CampaignCreate & {
  id: string;
  status: "draft" | "ready" | "paused" | "completed";
  media_kind?: "none" | "image" | "video";
};

const SEEDED_CAMPAIGNS: EmailCampaign[] = [
  {
    id: "demo-campaign-update",
    name: "Actualizare demonstrativă",
    segment: "past_customer",
    status: "ready",
    subject: "Actualizare demonstrativă pentru ${first_name}",
    html_body: SEEDED_TEMPLATES.find((template) => template.baseKey === "preview_campaign_update")?.body ?? "",
    text_body: "Salut, ${first_name}. Acesta este un mesaj demonstrativ.",
    thumbnail_url: "https://assets.example.com/campaign-update.png",
  },
  {
    id: "demo-campaign-intro",
    name: "Introducere demonstrativă",
    segment: "potential_customer",
    status: "draft",
    subject: "Mesaj demonstrativ pentru ${first_name}",
    html_body: SEEDED_TEMPLATES.find((template) => template.baseKey === "preview_campaign_intro")?.body ?? "",
    text_body: "Salut, ${first_name}. Folosește această mostră pentru verificarea editorului.",
  },
];

const DEMO_CAMPAIGN_STORAGE_KEY = "codrut_demo_campaigns";
const DEMO_CAMPAIGN_MEMBERSHIP_STORAGE_KEY = "codrut_demo_campaign_memberships";
const DEMO_CAMPAIGN_RECIPIENT_STORAGE_KEY = "codrut_demo_campaign_recipients";

function nextDemoId(prefix: string, existingIds: Iterable<string>): string {
  const existing = new Set(existingIds);
  let index = existing.size + 1;
  let candidate = `${prefix}-${index}`;

  while (existing.has(candidate)) {
    index += 1;
    candidate = `${prefix}-${index}`;
  }

  return candidate;
}

function getSeededCampaigns(): EmailCampaign[] {
  return SEEDED_CAMPAIGNS.map((campaign) => ({ ...campaign }));
}

function readDemoCampaignRecipients(): CampaignRecipientRow[] {
  if (typeof window === "undefined") return getSeededCampaignRecipients();

  try {
    const stored = window.localStorage.getItem(DEMO_CAMPAIGN_RECIPIENT_STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed)) {
        return parsed.map((recipient) => ({ ...recipient }));
      }
    }
  } catch {
    // Fall through to the seeded demo recipients if localStorage is unavailable or malformed.
  }

  const seeded = getSeededCampaignRecipients();
  writeDemoCampaignRecipients(seeded);
  return seeded;
}

function writeDemoCampaignRecipients(recipients: CampaignRecipientRow[]): void {
  if (typeof window === "undefined") return;

  try {
    window.localStorage.setItem(
      DEMO_CAMPAIGN_RECIPIENT_STORAGE_KEY,
      JSON.stringify(recipients.map((recipient) => ({ ...recipient }))),
    );
  } catch {
    // Demo fallback should keep browsing usable even when localStorage is unavailable.
  }
}

function demoRecipientClientType(segment: CampaignRecipientCreate["segment"]): CampaignRecipientRow["clientType"] {
  return segment === "past_customer" ? "tip_1" : "tip_2";
}

function splitDemoContactName(value: string | undefined): { firstName?: string; lastName?: string } {
  const [firstName, ...lastNameParts] = value?.trim().split(/\s+/).filter(Boolean) ?? [];
  return {
    firstName: firstName || undefined,
    lastName: lastNameParts.join(" ") || undefined,
  };
}

function demoRecipientStatus(
  status: CampaignRecipientCreate["status"] | CampaignRecipientUpdate["status"] | undefined,
  contactName: string | undefined,
  existingStatus: CampaignRecipientRow["status"] | undefined,
): CampaignRecipientRow["status"] {
  if (status === "suppressed") return "suppressed";
  if (status === "unsubscribed") return "unsubscribed";
  if (!status && existingStatus) return existingStatus;
  return contactName?.trim() ? "ready" : "needs_contact_name";
}

function buildDemoCampaignRecipient(
  id: string,
  payload: CampaignRecipientCreate | CampaignRecipientUpdate,
  existing?: CampaignRecipientRow,
): CampaignRecipientRow {
  const contactName = payload.contact_name ?? [existing?.firstName, existing?.lastName].filter(Boolean).join(" ");
  const splitName = splitDemoContactName(contactName);
  const nextEmail = payload.email?.trim() ?? existing?.email ?? "";
  const nextStatus = demoRecipientStatus(payload.status, contactName, existing?.status);
  const correctedSuppressedEmail =
    existing?.status === "suppressed"
    && nextStatus === "suppressed"
    && nextEmail.toLocaleLowerCase("ro-RO") !== existing.email.trim().toLocaleLowerCase("ro-RO");
  return {
    ...existing,
    id,
    company: payload.organization_name ?? existing?.company ?? "Companie necompletată",
    firstName: splitName.firstName,
    lastName: splitName.lastName,
    email: nextEmail,
    clientType: payload.segment ? demoRecipientClientType(payload.segment) : existing?.clientType ?? "tip_2",
    status: nextStatus,
    activationAllowed:
      nextStatus === "suppressed"
        ? correctedSuppressedEmail || existing?.activationAllowed === true
        : false,
  };
}

function bulkCreateDemoCampaignRecipients(
  recipients: CampaignRecipientCreate[],
): CampaignRecipientBulkCreateResponse {
  const nextRecipients = readDemoCampaignRecipients();
  let created = 0;
  let updated = 0;

  recipients.forEach((recipient) => {
    const emailKey = recipient.email?.trim().toLowerCase() ?? "";
    const existingIndex = emailKey
      ? nextRecipients.findIndex((item) => item.email.trim().toLowerCase() === emailKey)
      : -1;
    const existing = existingIndex >= 0 ? nextRecipients[existingIndex] : undefined;
    const id = existing?.id ?? nextDemoId("campaign-local", nextRecipients.map((item) => item.id));
    const nextRecipient = buildDemoCampaignRecipient(id, recipient, existing);

    if (existingIndex >= 0) {
      nextRecipients[existingIndex] = nextRecipient;
      updated += 1;
    } else {
      nextRecipients.push(nextRecipient);
      created += 1;
    }
  });

  writeDemoCampaignRecipients(nextRecipients);
  return { status: "success", count: recipients.length, created, updated };
}

function updateDemoCampaignRecipient(
  recipientId: string,
  recipient: CampaignRecipientUpdate,
): CampaignRecipientRow {
  const recipients = readDemoCampaignRecipients();
  const existing = recipients.find((item) => item.id === recipientId);
  const updated = buildDemoCampaignRecipient(recipientId, recipient, existing);
  writeDemoCampaignRecipients(
    existing
      ? recipients.map((item) => (item.id === recipientId ? updated : item))
      : [...recipients, updated],
  );
  return updated;
}

function deleteDemoCampaignRecipient(recipientId: string): void {
  writeDemoCampaignRecipients(readDemoCampaignRecipients().filter((recipient) => recipient.id !== recipientId));
  const memberships = readDemoCampaignMemberships();
  writeDemoCampaignMemberships(
    Object.fromEntries(
      Object.entries(memberships).map(([campaignId, recipientIds]) => [
        campaignId,
        recipientIds.filter((id) => id !== recipientId),
      ]),
    ),
  );
}

function archiveDemoCampaignRecipient(recipientId: string): CampaignRecipientArchiveResponse {
  const archivedAt = new Date();
  const purgeAfter = new Date(archivedAt);
  purgeAfter.setDate(purgeAfter.getDate() + 30);
  const recipients = readDemoCampaignRecipients();
  writeDemoCampaignRecipients(recipients.map((recipient) =>
    recipient.id === recipientId
      ? {
          ...recipient,
          status: "archived",
          statusBeforeArchive:
            recipient.statusBeforeArchive
            ?? demoRecipientProtectionStatus(recipient.status),
          archivedAt: archivedAt.toISOString(),
          purgeAfter: purgeAfter.toISOString(),
        }
      : recipient,
  ));
  const memberships = readDemoCampaignMemberships();
  let membershipsRemoved = 0;
  writeDemoCampaignMemberships(
    Object.fromEntries(
      Object.entries(memberships).map(([campaignId, recipientIds]) => {
        if (recipientIds.includes(recipientId)) membershipsRemoved += 1;
        return [campaignId, recipientIds.filter((id) => id !== recipientId)];
      }),
    ),
  );
  return {
    id: recipientId,
    status: "archived",
    archived_at: archivedAt.toISOString(),
    purge_after: purgeAfter.toISOString(),
    memberships_removed: membershipsRemoved,
    cancelled: 0,
    in_flight: 0,
  };
}

function restoreDemoCampaignRecipient(recipientId: string): CampaignRecipientRestoreResponse {
  const recipients = readDemoCampaignRecipients();
  const recipient = recipients.find((item) => item.id === recipientId);
  const restoredStatus = recipient?.statusBeforeArchive ?? "active";
  writeDemoCampaignRecipients(recipients.map((recipient) =>
    recipient.id === recipientId
      ? {
          ...recipient,
          status:
            restoredStatus === "suppressed" || restoredStatus === "unsubscribed"
              ? restoredStatus
              : campaignRecipientNameForDemo(recipient)
                ? "ready"
                : "needs_contact_name",
          activationAllowed:
            restoredStatus === "suppressed"
              ? recipient.activationAllowed === true
              : false,
          archivedAt: null,
          purgeAfter: null,
          statusBeforeArchive: null,
        }
      : recipient,
  ));
  return {
    id: recipientId,
    status: restoredStatus,
    archived_at: null,
    purge_after: null,
  };
}

function permanentlyDeleteDemoCampaignRecipient(
  recipientId: string,
): CampaignRecipientPermanentDeleteResponse {
  deleteDemoCampaignRecipient(recipientId);
  return {
    id: recipientId,
    status: "deleted",
    cancelled: 0,
    anonymized_sends: 0,
  };
}

function campaignRecipientNameForDemo(recipient: CampaignRecipientRow): string {
  return [recipient.firstName, recipient.lastName].filter(Boolean).join(" ").trim();
}

function demoRecipientProtectionStatus(
  status: CampaignRecipientRow["status"],
): NonNullable<CampaignRecipientRow["statusBeforeArchive"]> {
  if (status === "suppressed" || status === "unsubscribed") return status;
  return "active";
}

function readDemoCampaigns(): EmailCampaign[] {
  if (typeof window === "undefined") return getSeededCampaigns();

  try {
    const stored = window.localStorage.getItem(DEMO_CAMPAIGN_STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed)) {
        return parsed.map((campaign) => ({ ...campaign }));
      }
    }
  } catch {
    // Fall through to the seeded demo campaigns if localStorage is unavailable or malformed.
  }

  const seeded = getSeededCampaigns();
  writeDemoCampaigns(seeded);
  return seeded;
}

function writeDemoCampaigns(campaigns: EmailCampaign[]): void {
  if (typeof window === "undefined") return;

  try {
    window.localStorage.setItem(
      DEMO_CAMPAIGN_STORAGE_KEY,
      JSON.stringify(campaigns.map((campaign) => ({ ...campaign }))),
    );
  } catch {
    // Demo fallback should keep browsing usable even when localStorage is unavailable.
  }
}

function readDemoCampaignMemberships(): Record<string, string[]> {
  if (typeof window === "undefined") return {};

  try {
    const stored = window.localStorage.getItem(DEMO_CAMPAIGN_MEMBERSHIP_STORAGE_KEY);
    const parsed = stored ? JSON.parse(stored) : null;
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return Object.fromEntries(
        Object.entries(parsed).map(([campaignId, recipientIds]) => [
          campaignId,
          Array.isArray(recipientIds)
            ? recipientIds.filter((recipientId): recipientId is string => typeof recipientId === "string")
            : [],
        ]),
      );
    }
  } catch {
    // Demo fallback memberships are best-effort local state.
  }

  return {};
}

function writeDemoCampaignMemberships(memberships: Record<string, string[]>): void {
  if (typeof window === "undefined") return;

  try {
    window.localStorage.setItem(DEMO_CAMPAIGN_MEMBERSHIP_STORAGE_KEY, JSON.stringify(memberships));
  } catch {
    // Keep demo browsing usable if localStorage is unavailable.
  }
}

function demoRecipientSegment(recipient: CampaignRecipientRow): CampaignCreate["segment"] {
  return recipient.clientType === "tip_1" ? "past_customer" : "potential_customer";
}

function isDemoRecipientEligible(recipient: CampaignRecipientRow, segment: CampaignCreate["segment"]): boolean {
  return (
    segment !== null
    && demoRecipientSegment(recipient) === segment
    && recipient.status !== "suppressed"
    && recipient.status !== "unsubscribed"
    && Boolean(recipient.email.trim())
  );
}

function defaultDemoMembershipRecipientIds(segment: CampaignCreate["segment"]): string[] {
  return readDemoCampaignRecipients()
    .filter((recipient) => isDemoRecipientEligible(recipient, segment))
    .map((recipient) => recipient.id);
}

function demoMembershipRows(recipientIds: string[]): CampaignRecipientMembershipRow[] {
  const recipientsById = new Map(readDemoCampaignRecipients().map((recipient) => [recipient.id, recipient]));
  return recipientIds.map((recipientId) => {
    const recipient = recipientsById.get(recipientId);
    if (recipient) {
      return {
        ...recipient,
        membershipSource: "manual",
      };
    }
    return {
      id: recipientId,
      company: "",
      email: "",
      clientType: "tip_2",
      status: "ready",
      activationAllowed: false,
      membershipSource: "manual",
    };
  });
}

function readDemoCampaignMembershipRows(campaignId: string): CampaignRecipientMembershipRow[] {
  const memberships = readDemoCampaignMemberships();
  if (Object.prototype.hasOwnProperty.call(memberships, campaignId)) {
    return demoMembershipRows(memberships[campaignId] ?? []);
  }

  const campaign = readDemoCampaigns().find((item) => item.id === campaignId);
  if (!campaign || campaign.segment === null) {
    return [];
  }

  const defaultRecipientIds = defaultDemoMembershipRecipientIds(campaign.segment);
  writeDemoCampaignMemberships({
    ...memberships,
    [campaignId]: defaultRecipientIds,
  });
  return demoMembershipRows(defaultRecipientIds);
}

function replaceDemoCampaignMembershipRows(
  campaignId: string,
  recipientIds: string[],
): CampaignRecipientMembershipRow[] {
  const uniqueRecipientIds = Array.from(new Set(recipientIds));
  writeDemoCampaignMemberships({
    ...readDemoCampaignMemberships(),
    [campaignId]: uniqueRecipientIds,
  });
  return demoMembershipRows(uniqueRecipientIds);
}

function createDemoCampaign(campaign: CampaignCreate): EmailCampaign {
  const campaigns = readDemoCampaigns();
  const created: EmailCampaign = {
    id: nextDemoId("campaign", campaigns.map((item) => item.id)),
    status: "ready",
    ...campaign,
    media_kind: campaign.video_url ? "video" : campaign.thumbnail_url ? "image" : "none",
  };
  writeDemoCampaigns([...campaigns, created]);
  if (created.segment !== null) {
    replaceDemoCampaignMembershipRows(created.id, defaultDemoMembershipRecipientIds(created.segment));
  }
  return { ...created };
}

function updateDemoCampaign(campaignId: string, campaign: CampaignUpdate): EmailCampaign {
  const campaigns = readDemoCampaigns();
  const existing = campaigns.find((item) => item.id === campaignId) ?? {
    id: campaignId,
    name: "",
    segment: "potential_customer",
    status: "ready",
    subject: "",
    html_body: "",
    text_body: "",
  };
  const updated: EmailCampaign = {
    ...existing,
    ...campaign,
    id: campaignId,
    status: campaign.status ?? existing.status,
    video_url: campaign.video_url === null ? undefined : campaign.video_url ?? existing.video_url,
    thumbnail_url: campaign.thumbnail_url === null ? undefined : campaign.thumbnail_url ?? existing.thumbnail_url,
    landing_page_url: campaign.landing_page_url === null ? undefined : campaign.landing_page_url ?? existing.landing_page_url,
  };
  updated.media_kind = updated.video_url ? "video" : updated.thumbnail_url ? "image" : "none";
  writeDemoCampaigns(campaigns.some((item) => item.id === campaignId)
    ? campaigns.map((item) => (item.id === campaignId ? updated : item))
    : [...campaigns, updated]);
  return { ...updated };
}

function deleteDemoCampaign(campaignId: string): void {
  writeDemoCampaigns(readDemoCampaigns().filter((campaign) => campaign.id !== campaignId));
  const memberships = readDemoCampaignMemberships();
  delete memberships[campaignId];
  writeDemoCampaignMemberships(memberships);
}

export type CampaignSendRecipientResult = {
  recipient_id: string;
  email: string;
  status: "accepted" | "failed" | "skipped" | "dry_run" | string;
  message_id?: string | null;
  error?: string | null;
};

export type CampaignSendResponse = {
  campaign_id: string;
  total: number;
  queued?: number;
  sent: number;
  failed: number;
  skipped: number;
  dry_run: boolean;
  results: CampaignSendRecipientResult[];
};

export async function createCampaignOnServer(campaign: CampaignCreate): Promise<EmailCampaign> {
  try {
    const response = await apiFetch(`${getApiBaseUrl()}/communications/campaigns`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(campaign),
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) {
        return createDemoCampaign(campaign);
      }
      const errorBody = await response.json().catch(() => null);
      throw campaignPersistenceError(
        response,
        errorBody,
        `Nu am putut crea campania (${response.status}).`,
      );
    }
    return await response.json();
  } catch (err) {
    if (isDemoFallbackEnabled()) {
      return createDemoCampaign(campaign);
    }
    throw err;
  }
}

export async function updateCampaignOnServer(campaignId: string, campaign: CampaignUpdate): Promise<EmailCampaign> {
  try {
    const response = await apiFetch(`${getApiBaseUrl()}/communications/campaigns/${campaignId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(campaign),
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) {
        return updateDemoCampaign(campaignId, campaign);
      }
      const errorBody = await response.json().catch(() => null);
      throw campaignPersistenceError(
        response,
        errorBody,
        `Nu am putut actualiza campania (${response.status}).`,
      );
    }
    return await response.json();
  } catch (err) {
    if (isDemoFallbackEnabled()) {
      return updateDemoCampaign(campaignId, campaign);
    }
    throw err;
  }
}

export async function listCampaignsOnServer(): Promise<EmailCampaign[]> {
  if (typeof window !== "undefined" && isDemoFallbackEnabled()) {
    return readDemoCampaigns();
  }

  try {
    const response = await apiFetch(`${getApiBaseUrl()}/communications/campaigns`, {
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) return readDemoCampaigns();
      throw new Error(`Failed to fetch campaigns: ${response.status}`);
    }
    return await response.json();
  } catch (err) {
    if (isDemoFallbackEnabled()) return readDemoCampaigns();
    throw err;
  }
}

export async function deleteCampaignOnServer(campaignId: string): Promise<void> {
  if (typeof window !== "undefined" && isDemoFallbackEnabled()) {
    deleteDemoCampaign(campaignId);
    return;
  }

  try {
    const response = await apiFetch(`${getApiBaseUrl()}/communications/campaigns/${campaignId}`, {
      method: "DELETE",
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) {
        deleteDemoCampaign(campaignId);
        return;
      }
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.error?.message ?? `Nu am putut șterge campania (${response.status}).`);
    }
  } catch (err) {
    if (isDemoFallbackEnabled()) {
      deleteDemoCampaign(campaignId);
      return;
    }
    throw err;
  }
}

export async function sendCampaignOnServer(
  campaignId: string,
  options: {
    dryRun?: boolean;
    recipientIds?: string[];
    mode?: "new" | "selected" | "all";
    idempotencyKey?: string;
  } = {},
): Promise<CampaignSendResponse> {
  if (typeof window !== "undefined" && isDemoFallbackEnabled()) {
    return {
      campaign_id: campaignId,
      total: 0,
      sent: 0,
      failed: 0,
      skipped: 0,
      dry_run: Boolean(options.dryRun),
      results: [],
    };
  }

  try {
    const response = await apiFetch(`${getApiBaseUrl()}/communications/campaigns/${campaignId}/send`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Idempotency-Key": options.idempotencyKey ?? createEmailIdempotencyKey(),
      },
      cache: "no-store",
      credentials: "include",
      body: JSON.stringify({
        dry_run: Boolean(options.dryRun),
        recipient_ids: options.recipientIds,
        mode: options.mode ?? (options.recipientIds?.length ? "selected" : "new"),
      }),
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) {
        return {
          campaign_id: campaignId,
          total: 0,
          sent: 0,
          failed: 0,
          skipped: 0,
          dry_run: Boolean(options.dryRun),
          results: [],
        };
      }
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.error?.message ?? `Nu am putut trimite campania (${response.status}).`);
    }
    return await response.json();
  } catch (err) {
    if (isDemoFallbackEnabled()) {
      return {
        campaign_id: campaignId,
        total: 0,
        sent: 0,
        failed: 0,
        skipped: 0,
        dry_run: Boolean(options.dryRun),
        results: [],
      };
    }
    throw err;
  }
}

function createEmailIdempotencyKey(): string {
  const suffix = globalThis.crypto?.randomUUID?.()
    ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `campaign-send-${suffix}`;
}
