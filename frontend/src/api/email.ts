import { getApiBaseUrl, isDemoFallbackEnabled, isSeededDemoFallbackEnabled } from "./runtime";
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
    body: `<p>Bună, {participant_name}.</p><p>{trainer_name} te-a invitat în Codruț pentru {company_name}. După activare vei vedea spațiul tău de participant și sarcinile pregătite pentru proiect.</p><p><a href="{action_url}">Activează contul</a></p>`
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

function getSeededTemplates(): EmailTemplate[] {
  return SEEDED_TEMPLATES.map((template) => ({
    ...template,
    placeholders: [...template.placeholders],
  }));
}

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
  if (typeof window !== "undefined" && !process.env.VITEST && isDemoFallbackEnabled()) {
    return getSeededTemplates();
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/communications/templates?include_retired=${includeRetired}`, {
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
  if (typeof window !== "undefined" && !process.env.VITEST && isDemoFallbackEnabled()) {
    return {
      ...template,
      placeholders: [...template.placeholders],
    };
  }

  const payload = frontendToBackendTemplate(template);
  const response = await fetch(`${getApiBaseUrl()}/communications/templates`, {
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
  const response = await fetch(`${getApiBaseUrl()}/communications/templates/${template.baseKey}?version=${template.version}`, {
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
  const response = await fetch(`${getApiBaseUrl()}/communications/templates/${key}/versions/${version}/activate`, {
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
  openCount?: number;
  clickCount?: number;
  viewCount?: number;
  replyCount?: number;
  calendlyClickCount?: number;
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
    if (!isDemoFallbackEnabled()) {
      throw e;
    }
    return {
      metrics: [],
      assessmentRows: [],
      rules: [],
      campaign: {
        videoHost: {
          provider: "Vimeo sau pagină Codruț",
          status: "ready",
          note: "Emailul trimite thumbnail și CTA către linkul video. Pagina Codruț este opțională pentru tracking sau CTA-uri dedicate.",
        },
        template: {
          subject: "O idee practică pentru echipa ta, ${first_name}",
          personalization: "Prenumele se completează automat când există nume în bază.",
          ctaPrimary: "Programează o discuție",
          ctaSecondary: "Vreau să fiu contactat",
        },
        recipients: [
          {
            id: "campaign-atlas-ceo",
            company: "Atlas Mobility",
            firstName: "Radu",
            lastName: "Munteanu",
            email: "radu.munteanu@atlas-mobility.ro",
            clientType: "tip_1",
            status: "sent",
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
            email: "diana.ene@clinica-meridian.ro",
            clientType: "tip_1",
            status: "ready",
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
            email: "cristina.olaru@nova-retail.ro",
            clientType: "tip_2",
            status: "needs_contact_name",
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
            email: "office@fabricanord.ro",
            clientType: "tip_2",
            status: "suppressed",
            openCount: 0,
            clickCount: 0,
            viewCount: 0,
            replyCount: 0,
            calendlyClickCount: 0,
            emailVariant: "variant_c",
          },
        ],
        weeklyReport: {
          cadence: "Săptămânal",
          metrics: ["deschideri", "clickuri", "vizualizări video", "reply-uri", "clickuri Calendly", "variantă email"],
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

export type CampaignRecipientUpdate = Partial<CampaignRecipientCreate> & {
  status?: "active" | "suppressed" | "unsubscribed";
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

export async function updateCampaignRecipientOnServer(
  recipientId: string,
  recipient: CampaignRecipientUpdate,
) {
  try {
    const response = await fetch(`${getApiBaseUrl()}/communications/campaigns/recipients/${recipientId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(recipient),
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) return { id: recipientId, ...recipient };
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.error?.message ?? `Nu am putut actualiza contactul (${response.status}).`);
    }
    return await response.json();
  } catch (err) {
    if (isDemoFallbackEnabled()) return { id: recipientId, ...recipient };
    throw err;
  }
}

export async function deleteCampaignRecipientOnServer(recipientId: string): Promise<void> {
  try {
    const response = await fetch(`${getApiBaseUrl()}/communications/campaigns/recipients/${recipientId}`, {
      method: "DELETE",
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) return;
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.error?.message ?? `Nu am putut șterge contactul (${response.status}).`);
    }
  } catch (err) {
    if (isDemoFallbackEnabled()) return;
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

export type CampaignAssetUpload = {
  url: string;
  file_name: string;
  content_type: string;
  size_bytes: number;
};

export async function uploadCampaignAssetOnServer(file: File): Promise<CampaignAssetUpload> {
  const response = await fetch(`${getApiBaseUrl()}/communications/campaign-assets`, {
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

export type CampaignVideoDraft = {
  name: string;
  segment: "past_customer" | "potential_customer";
  subject: string;
  videoUrl: string;
  thumbnailUrl: string;
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

function escapeHtmlAttribute(value: string): string {
  return value.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");
}

export function buildVideoCampaignCreatePayload(draft: CampaignVideoDraft): CampaignCreate | null {
  const trimmedName = draft.name.trim();
  const videoUrl = normalizeHttpUrl(draft.videoUrl);
  const thumbnailUrl = normalizeHttpUrl(draft.thumbnailUrl);
  const landingUrl = normalizeHttpUrl(draft.landingUrl) ?? videoUrl;

  if (!trimmedName || !videoUrl || !thumbnailUrl || !landingUrl) return null;

  const safeLandingUrl = escapeHtmlAttribute(landingUrl);
  const safeThumbnailUrl = escapeHtmlAttribute(thumbnailUrl);

  return {
    name: trimmedName,
    segment: draft.segment,
    subject: draft.subject.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "$${$1}"),
    html_body: [
      "<p>Bună, ${first_name}.</p>",
      "<p>Am pregătit un material video scurt pentru contextul echipei tale.</p>",
      [
        `<p><a href="${safeLandingUrl}" style="display:block;text-decoration:none;color:inherit;">`,
        `<span style="display:block;position:relative;max-width:620px;border-radius:16px;overflow:hidden;background:#2b211f;">`,
        `<img src="${safeThumbnailUrl}" alt="Previzualizare video" style="display:block;width:100%;max-width:620px;height:auto;border:0;border-radius:16px;" />`,
        `<span style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:64px;height:64px;border-radius:999px;background:rgba(255,255,255,.9);box-shadow:0 14px 35px rgba(0,0,0,.22);text-align:center;line-height:64px;color:#890505;font-size:28px;font-weight:700;">&#9654;</span>`,
        "</span>",
        "</a></p>",
      ].join(""),
      `<p><a href="${safeLandingUrl}">Vezi video-ul</a></p>`,
    ].join(""),
    text_body: `Bună, \${first_name}. Vezi video-ul aici: ${landingUrl}`,
    video_url: videoUrl,
    thumbnail_url: thumbnailUrl,
    landing_page_url: landingUrl === videoUrl ? undefined : landingUrl,
  };
}

export type EmailCampaign = CampaignCreate & {
  id: string;
  status: "draft" | "ready" | "paused" | "completed";
};

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
  sent: number;
  failed: number;
  skipped: number;
  dry_run: boolean;
  results: CampaignSendRecipientResult[];
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

export async function listCampaignsOnServer(): Promise<EmailCampaign[]> {
  if (typeof window !== "undefined" && isDemoFallbackEnabled()) {
    return [];
  }

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

export async function deleteCampaignOnServer(campaignId: string): Promise<void> {
  if (typeof window !== "undefined" && isDemoFallbackEnabled()) {
    return;
  }

  try {
    const response = await fetch(`${getApiBaseUrl()}/communications/campaigns/${campaignId}`, {
      method: "DELETE",
      cache: "no-store",
      credentials: "include",
    });
    if (!response.ok) {
      if (isDemoFallbackEnabled()) return;
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.error?.message ?? `Nu am putut șterge campania (${response.status}).`);
    }
  } catch (err) {
    if (isDemoFallbackEnabled()) return;
    throw err;
  }
}

export async function sendCampaignOnServer(
  campaignId: string,
  options: { dryRun?: boolean; recipientIds?: string[] } = {},
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
    const response = await fetch(`${getApiBaseUrl()}/communications/campaigns/${campaignId}/send`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      cache: "no-store",
      credentials: "include",
      body: JSON.stringify({
        dry_run: Boolean(options.dryRun),
        recipient_ids: options.recipientIds,
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
