import type { EmailCampaign } from "@/api/email";

export type CampaignFieldName = "name" | "subject" | "body" | "videoUrl" | "thumbnailUrl" | "landingUrl";

export type CampaignFieldErrors = Partial<Record<CampaignFieldName, string>>;

export type CampaignDraftForValidation = {
  name: string;
  subject: string;
  htmlBody?: string;
  textBody?: string;
  videoUrl: string;
  thumbnailUrl: string;
  landingUrl: string;
};

export type CampaignSaveFailure = {
  message: string;
  fieldErrors: CampaignFieldErrors;
  retryable: boolean;
};

type CampaignValidationDetail = {
  loc?: unknown;
  message?: unknown;
};

const CAMPAIGN_API_FIELD_MAP: Record<string, CampaignFieldName> = {
  name: "name",
  subject: "subject",
  html_body: "body",
  text_body: "body",
  video_url: "videoUrl",
  thumbnail_url: "thumbnailUrl",
  landing_page_url: "landingUrl",
};

const CAMPAIGN_FIELD_FAILURE_COPY: Record<CampaignFieldName, string> = {
  name: "Verifică numele campaniei.",
  subject: "Verifică subiectul emailului.",
  body: "Verifică mesajul campaniei.",
  videoUrl: "Verifică linkul video.",
  thumbnailUrl: "Verifică imaginea campaniei.",
  landingUrl: "Verifică linkul paginii campaniei.",
};

function campaignErrorStatus(error: unknown): number | undefined {
  if (!error || typeof error !== "object" || !("status" in error)) return undefined;
  return typeof error.status === "number" ? error.status : undefined;
}

function campaignErrorMessage(error: unknown): string {
  return error instanceof Error && error.message.trim() ? error.message.trim() : "";
}

function campaignValidationDetails(error: unknown): CampaignValidationDetail[] {
  if (!error || typeof error !== "object" || !("details" in error) || !Array.isArray(error.details)) return [];
  return error.details.filter((detail): detail is CampaignValidationDetail => Boolean(detail && typeof detail === "object"));
}

function fieldFromValidationLocation(location: unknown): CampaignFieldName | null {
  if (!Array.isArray(location)) return null;
  for (let index = location.length - 1; index >= 0; index -= 1) {
    const field = CAMPAIGN_API_FIELD_MAP[String(location[index])];
    if (field) return field;
  }
  return null;
}

function inferCampaignFieldsFromMessage(message: string, draft: CampaignDraftForValidation): CampaignFieldName[] {
  const normalized = message.toLocaleLowerCase("ro-RO");
  const fields = new Set<CampaignFieldName>();

  if (/\bname\b|\bnume(?:le)?\b/.test(normalized)) fields.add("name");
  if (/\bsubject\b|\bsubiect/.test(normalized)) fields.add("subject");
  if (/html_body|text_body|\bbody\b|\bcorp(?:ul)?\b|\bconținut|\bcontinut|\bmesaj/.test(normalized)) fields.add("body");
  if (/video_url|\bvideo\b/.test(normalized)) fields.add("videoUrl");
  if (/thumbnail_url|thumbnail|\bimagin/.test(normalized)) fields.add("thumbnailUrl");
  if (/landing_page_url|landing page|pagina campaniei|paginii campaniei/.test(normalized)) fields.add("landingUrl");

  if (/unsupported variables|variabile neacceptate/.test(normalized)) {
    const normalizedSubject = draft.subject.toLocaleLowerCase("ro-RO");
    const normalizedBody = `${draft.htmlBody ?? ""}\n${draft.textBody ?? ""}`.toLocaleLowerCase("ro-RO");
    const variables = message.split(":").slice(1).join(":").split(",").map((value) => value.trim().toLocaleLowerCase("ro-RO")).filter(Boolean);
    if (variables.some((variable) => normalizedSubject.includes(variable))) fields.add("subject");
    if (variables.length === 0 || variables.some((variable) => normalizedBody.includes(variable))) fields.add("body");
  }

  return Array.from(fields);
}

function fieldFailureMessage(field: CampaignFieldName, serverMessage: string): string {
  const normalized = serverMessage.toLocaleLowerCase("ro-RO");
  if (/unsupported variables|variabile neacceptate/.test(normalized)) {
    return field === "subject"
      ? "Subiectul conține o variabilă neacceptată. Elimin-o și salvează din nou."
      : "Mesajul conține o variabilă neacceptată. Elimin-o și salvează din nou.";
  }
  if (/too long|max_length|at most/.test(normalized)) {
    return `${CAMPAIGN_FIELD_FAILURE_COPY[field].replace(/\.$/, "")}: valoarea este prea lungă.`;
  }
  return CAMPAIGN_FIELD_FAILURE_COPY[field];
}

function isRomanianCampaignMessage(message: string): boolean {
  return /campani|salvat|actualizat|imagine|link|subiect|nume|mesaj|server|permisi|conexi|încarc|incarc/i.test(message);
}

export function normalizeCampaignUrl(value: string): string | undefined {
  if (!value.trim()) return undefined;

  try {
    const url = new URL(value.trim());
    if (url.protocol !== "http:" && url.protocol !== "https:") return undefined;
    return url.toString();
  } catch {
    return undefined;
  }
}

export function validateCampaignDraft(draft: CampaignDraftForValidation): CampaignFieldErrors {
  const errors: CampaignFieldErrors = {};

  if (!draft.name.trim()) errors.name = "Adaugă un nume pentru campanie.";
  else if (draft.name.trim().length > 255) errors.name = "Numele campaniei poate avea cel mult 255 de caractere.";
  if (!draft.subject.trim()) errors.subject = "Adaugă subiectul emailului.";
  else if (draft.subject.trim().length > 255) errors.subject = "Subiectul emailului poate avea cel mult 255 de caractere.";

  for (const [field, value, message] of [
    ["videoUrl", draft.videoUrl, "Linkul video trebuie să înceapă cu http:// sau https://."],
    ["thumbnailUrl", draft.thumbnailUrl, "Linkul imaginii trebuie să înceapă cu http:// sau https://."],
    ["landingUrl", draft.landingUrl, "Linkul paginii trebuie să înceapă cu http:// sau https://."],
  ] as const) {
    if (value.trim().length > 2048) errors[field] = "Linkul poate avea cel mult 2048 de caractere.";
    else if (value.trim() && !normalizeCampaignUrl(value)) errors[field] = message;
  }

  return errors;
}

export function campaignSendReadinessError(campaign: EmailCampaign): string | null {
  if (!campaign.subject.trim()) return "Adaugă subiectul emailului înainte de trimitere.";
  if (!campaign.html_body.trim() || !campaign.text_body.trim()) {
    return "Adaugă mesajul campaniei înainte de trimitere.";
  }
  if (campaign.video_url?.trim() && !campaign.thumbnail_url?.trim()) {
    return "Adaugă o imagine de previzualizare înainte de a trimite campania video.";
  }
  return null;
}

export function campaignSendBlockedReason(options: {
  campaign: EmailCampaign;
  mode: "selected" | "all";
  sendableRecipientCount: number;
  activeRecipientCount: number;
  isSending: boolean;
  isDeleting: boolean;
}): string | null {
  const readinessError = campaignSendReadinessError(options.campaign);
  if (readinessError) return readinessError;
  if (options.isSending) return "Campania se trimite acum.";
  if (options.isDeleting) return "Campania se șterge acum.";
  if (options.mode === "selected" && options.sendableRecipientCount === 0) {
    return "Selectează cel puțin un destinatar care nu a primit campania.";
  }
  if (options.mode === "all" && options.activeRecipientCount === 0) {
    return "Adaugă cel puțin un destinatar activ în lista campaniei.";
  }
  return null;
}

export function campaignSaveFailureFromError(
  error: unknown,
  draft: CampaignDraftForValidation,
): CampaignSaveFailure {
  const status = campaignErrorStatus(error);
  const rawMessage = campaignErrorMessage(error);
  const fieldErrors: CampaignFieldErrors = {};

  for (const detail of campaignValidationDetails(error)) {
    const field = fieldFromValidationLocation(detail.loc);
    if (!field) continue;
    const detailMessage = typeof detail.message === "string" ? detail.message : rawMessage;
    fieldErrors[field] = fieldFailureMessage(field, detailMessage);
  }

  for (const field of inferCampaignFieldsFromMessage(rawMessage, draft)) {
    fieldErrors[field] ??= fieldFailureMessage(field, rawMessage);
  }

  if (Object.keys(fieldErrors).length > 0 && (status === 400 || status === 422)) {
    return {
      message: "Campania nu a fost salvată. Corectează câmpurile marcate.",
      fieldErrors,
      retryable: false,
    };
  }
  if (status === 401) {
    return { message: "Sesiunea a expirat. Reîncarcă pagina și autentifică-te din nou.", fieldErrors, retryable: false };
  }
  if (status === 403) {
    return { message: "Nu ai permisiunea să salvezi această campanie.", fieldErrors, retryable: false };
  }
  if (status === 404) {
    return { message: "Campania nu mai există. Reîncarcă lista înainte de a continua.", fieldErrors, retryable: false };
  }
  if (status === 409) {
    return { message: "Campania a fost modificată între timp. Reîncarcă lista înainte de a salva din nou.", fieldErrors, retryable: false };
  }
  if (status === 408 || status === 429 || (status !== undefined && status >= 500)) {
    return { message: "Serverul nu a putut salva campania. Datele au rămas în formular.", fieldErrors, retryable: true };
  }
  if (status === 400 || status === 422) {
    return {
      message: rawMessage && isRomanianCampaignMessage(rawMessage)
        ? rawMessage
        : "Datele campaniei au fost respinse. Verifică formularul și încearcă din nou.",
      fieldErrors,
      retryable: false,
    };
  }

  const looksLikeNetworkFailure = error instanceof TypeError || /failed to fetch|network|load failed|conexi/i.test(rawMessage);
  return {
    message: looksLikeNetworkFailure
      ? "Nu ne-am putut conecta la server. Datele au rămas în formular."
      : rawMessage && isRomanianCampaignMessage(rawMessage)
        ? `${rawMessage} Datele au rămas în formular.`
        : "Campania nu a putut fi salvată. Datele au rămas în formular.",
    fieldErrors,
    retryable: true,
  };
}
