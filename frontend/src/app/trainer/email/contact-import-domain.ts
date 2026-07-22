import type { CampaignRecipientCreate } from "@/api/email";

export type CampaignImportDraft = {
  id: string;
  rowNumber: number;
  email: string;
  contact_name: string;
  organization_name: string;
  segment: "past_customer" | "potential_customer";
  send: boolean;
  source: string;
};

type CampaignRecipientImportResult = {
  recipients: CampaignRecipientCreate[];
  skippedBySendFlag: number;
  skippedMissingEmail: number;
  skippedInvalidEmail: number;
};

function normalizeImportKey(value: string): string {
  return value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim().toLowerCase().replace(/\s+/g, " ");
}

function normalizeImportValue(value: unknown): string {
  return value == null ? "" : String(value).trim();
}

function readImportValue(row: Record<string, unknown>, keys: string[]): string {
  const wantedKeys = new Set(keys.map(normalizeImportKey));
  for (const [key, value] of Object.entries(row)) {
    if (wantedKeys.has(normalizeImportKey(key))) {
      const normalizedValue = normalizeImportValue(value);
      if (normalizedValue) return normalizedValue;
    }
  }
  return "";
}

function isMarkedForCampaignSend(row: Record<string, unknown>): boolean {
  const sendValue = readImportValue(row, ["De trimis", "Trimite", "Send", "Active"]);
  if (!sendValue) return true;
  return ["da", "yes", "y", "1", "true", "activ"].includes(normalizeImportKey(sendValue));
}

export function isValidImportEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

export function importDraftHasEmailError(draft: Pick<CampaignImportDraft, "email" | "send">): boolean {
  return draft.send && !isValidImportEmail(draft.email.trim());
}

export function selectCampaignRecipientImportSheetName(sheetNames: string[]): string | undefined {
  return sheetNames.find((sheetName) => normalizeImportKey(sheetName) === "revised") ?? sheetNames[0];
}

function importSegmentFromValue(value: string): "past_customer" | "potential_customer" {
  const normalized = normalizeImportKey(value);
  if (!normalized) return "potential_customer";
  if (
    normalized.includes("nu e client")
    || normalized.includes("nu este client")
    || normalized.includes("non-client")
    || normalized.includes("potential")
    || normalized.includes("potențial")
  ) {
    return "potential_customer";
  }
  if (normalized.includes("past") || normalized.includes("client")) {
    return "past_customer";
  }
  return "potential_customer";
}

function importContactName(row: Record<string, unknown>): string {
  const explicitName = readImportValue(row, ["contact_name", "Contact name", "Nume contact", "Nume complet", "Full name", "Name", "name"]);
  if (explicitName) return explicitName;
  const composedName = [
    readImportValue(row, ["Primul prenume", "Prenume", "Prenume 1", "First name", "first_name"]),
    readImportValue(row, ["Al doilea prenume", "Prenume 2", "Middle name", "middle_name"]),
    readImportValue(row, ["Nume de familie", "Nume familie", "Nume", "Familie", "Surname", "Last name", "last_name"]),
  ].filter(Boolean).join(" ");
  return composedName || readImportValue(row, ["Nume"]);
}

function importOrganizationName(row: Record<string, unknown>): string {
  return readImportValue(row, [
    "organization_name", "Organizație", "Organizatie", "Organizaţie", "Organizația", "Organizatia", "Companie", "company", "Company",
  ]);
}

export function buildCampaignRecipientImportDrafts(rows: Record<string, unknown>[]): CampaignImportDraft[] {
  return rows.map((row, index) => {
    const segmentValue = readImportValue(row, ["segment", "Segment", "Tip Client"]);
    const email = readImportValue(row, ["email", "Email", "EMAIL"]);
    return {
      id: `${index}-${email || "missing"}`,
      rowNumber: index + 2,
      email,
      contact_name: importContactName(row),
      organization_name: importOrganizationName(row),
      segment: importSegmentFromValue(segmentValue),
      send: isMarkedForCampaignSend(row) && isValidImportEmail(email),
      source: "excel_import",
    };
  });
}

export function campaignImportDraftToRecipient(row: CampaignImportDraft): CampaignRecipientCreate {
  const email = row.email.trim();
  return {
    email: isValidImportEmail(email) ? email : undefined,
    contact_name: row.contact_name.trim() || undefined,
    organization_name: row.organization_name.trim() || undefined,
    segment: row.segment,
    status: row.send ? "active" : "suppressed",
    source: row.source,
  };
}

export function uniqueCampaignImportDrafts(drafts: CampaignImportDraft[]): {
  duplicateEmailCount: number;
  uniqueDrafts: CampaignImportDraft[];
} {
  const uniqueDraftsByEmail = new Map<string, CampaignImportDraft>();
  const uniqueDrafts: CampaignImportDraft[] = [];
  let duplicateEmailCount = 0;
  for (const draft of drafts) {
    const normalizedEmail = draft.email.trim().toLowerCase();
    if (normalizedEmail && isValidImportEmail(normalizedEmail)) {
      if (uniqueDraftsByEmail.has(normalizedEmail)) duplicateEmailCount += 1;
      uniqueDraftsByEmail.set(normalizedEmail, draft);
      continue;
    }
    uniqueDrafts.push(draft);
  }
  return { duplicateEmailCount, uniqueDrafts: [...uniqueDraftsByEmail.values(), ...uniqueDrafts] };
}

export function buildCampaignRecipientImport(rows: Record<string, unknown>[]): CampaignRecipientImportResult {
  return rows.reduce<CampaignRecipientImportResult>((result, row) => {
    const email = readImportValue(row, ["email", "Email", "EMAIL"]);
    const validEmail = isValidImportEmail(email);
    const segmentValue = readImportValue(row, ["segment", "Segment", "Tip Client"]);
    result.recipients.push({
      email: validEmail ? email : undefined,
      contact_name: importContactName(row) || undefined,
      organization_name: importOrganizationName(row) || undefined,
      segment: importSegmentFromValue(segmentValue),
      status: isMarkedForCampaignSend(row) && validEmail ? "active" : "suppressed",
      source: "excel_import",
    });
    return result;
  }, { recipients: [], skippedBySendFlag: 0, skippedMissingEmail: 0, skippedInvalidEmail: 0 });
}
