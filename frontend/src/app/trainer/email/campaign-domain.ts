import type {
  CampaignRecipientMembershipRow,
  CampaignRecipientRow,
  CampaignSendResponse,
  EmailCampaign,
} from "@/api/email";

export type CampaignSegmentKey = "past_customer" | "potential_customer";
export type CampaignTargetSegment = CampaignSegmentKey | null;
export type CampaignContactTypeFilter = "all" | CampaignSegmentKey;
export type CampaignDeliveryState = NonNullable<CampaignRecipientMembershipRow["campaignDelivery"]>;
export type CampaignSendMode = "new" | "all" | "selected";
export type CampaignContactDraft = {
  email: string;
  contact_name: string;
  organization_name: string;
  segment: CampaignSegmentKey;
  status: "active" | "suppressed" | "unsubscribed";
};
export type CampaignMembershipCompanyGroup = {
  key: string;
  label: string;
  recipientIds: string[];
  selectedCount: number;
};

export function createCampaignSendIdempotencyKey(): string {
  const suffix = globalThis.crypto?.randomUUID?.()
    ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `campaign-ui-${suffix}`;
}

export function campaignRecipientName(recipient: CampaignRecipientRow): string {
  return [recipient.firstName, recipient.lastName].filter(Boolean).join(" ");
}

export function campaignRecipientIdentityLabel(recipient: CampaignRecipientRow): string {
  const emailLocalPart = recipient.email.split("@", 1)[0];
  return campaignRecipientName(recipient) || recipient.company.trim() || emailLocalPart || recipient.email;
}

export function campaignRecipientSegment(recipient: CampaignRecipientRow): CampaignSegmentKey {
  return recipient.clientType === "tip_1" ? "past_customer" : "potential_customer";
}

export function campaignSegmentLabel(segment: CampaignTargetSegment): string {
  if (segment === null) return "Fără grup";
  return segment === "past_customer" ? "Client existent" : "Prospect";
}

export function campaignDeliveryLabel(delivery: CampaignDeliveryState): string {
  return { failed: "Eroare", not_sent: "Netrimis", queued: "În coadă", sent: "Trimis" }[delivery];
}

function campaignSendErrorLabel(error: string): string {
  const labels: Record<string, string> = {
    "Daily email send cap reached.": "A fost atinsă limita zilnică de emailuri.",
    "Recipient is suppressed or unsubscribed.": "Adresa este respinsă sau contactul s-a dezabonat.",
    "Recipient segment does not match campaign segment.": "Tipul contactului nu corespunde campaniei.",
  };
  return labels[error] ?? error;
}

export function campaignSendResultSummary(result: CampaignSendResponse): string {
  const parts = [
    result.queued ? `${result.queued} în coadă` : null,
    result.sent ? `${result.sent} trimise` : null,
    result.failed ? `${result.failed} eșuate` : null,
    result.skipped ? `${result.skipped} omise` : null,
  ].filter(Boolean);
  return parts.join(", ") || "Niciun email procesat";
}

export function campaignSendFailureDetail(result: CampaignSendResponse): string | null {
  const failedResult = result.results.find((item) => item.error);
  if (!failedResult?.error) return null;
  return `${failedResult.email}: ${campaignSendErrorLabel(failedResult.error)}`;
}

export function campaignRecipientCompanyLabel(recipient: CampaignRecipientRow): string {
  return recipient.company.trim() || "Companie necompletată";
}

export function campaignRecipientCompanyKey(recipient: CampaignRecipientRow): string {
  return campaignRecipientCompanyLabel(recipient).toLocaleLowerCase("ro-RO");
}

export function campaignMembershipCompanyGroups(
  recipients: CampaignRecipientRow[],
  memberIds: string[],
): CampaignMembershipCompanyGroup[] {
  const selectedIds = new Set(memberIds);
  const groups = new Map<string, CampaignMembershipCompanyGroup>();
  for (const recipient of recipients) {
    const key = campaignRecipientCompanyKey(recipient);
    const currentGroup = groups.get(key) ?? {
      key,
      label: campaignRecipientCompanyLabel(recipient),
      recipientIds: [],
      selectedCount: 0,
    };
    currentGroup.recipientIds.push(recipient.id);
    if (selectedIds.has(recipient.id)) currentGroup.selectedCount += 1;
    groups.set(key, currentGroup);
  }
  return Array.from(groups.values()).sort((first, second) => first.label.localeCompare(second.label, "ro-RO"));
}

export function campaignRecipientMatchesSearch(recipient: CampaignRecipientRow, query: string): boolean {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return true;
  return [recipient.company, campaignRecipientName(recipient), recipient.email]
    .some((value) => value.toLowerCase().includes(normalizedQuery));
}

export function splitContactName(value: string): { firstName?: string; lastName?: string } {
  const [firstName, ...lastNameParts] = value.trim().split(/\s+/).filter(Boolean);
  const lastName = lastNameParts.join(" ");
  return { firstName: firstName || undefined, lastName: lastName || undefined };
}

export function campaignRecipientDraft(recipient: CampaignRecipientRow): CampaignContactDraft {
  return {
    email: recipient.email,
    contact_name: campaignRecipientName(recipient),
    organization_name: recipient.company === "Companie necompletată" ? "" : recipient.company,
    segment: campaignRecipientSegment(recipient),
    status: recipient.status === "unsubscribed"
      ? "unsubscribed"
      : recipient.status === "suppressed"
        ? "suppressed"
        : "active",
  };
}

export function campaignRecipientSortKey(recipient: CampaignRecipientRow): string {
  return [recipient.company, campaignRecipientName(recipient), recipient.email].join(" ").toLocaleLowerCase("ro-RO");
}

export function campaignRecipientStatusLabel(status: CampaignRecipientRow["status"]): string {
  const labels: Record<CampaignRecipientRow["status"], string> = {
    needs_contact_name: "Activ",
    ready: "Activ",
    sent: "Activ",
    suppressed: "Adresă respinsă",
    unsubscribed: "Dezabonat",
    archived: "Arhivat",
  };
  return labels[status] ?? status;
}

export function campaignStatusLabel(status: EmailCampaign["status"]): string {
  const labels: Partial<Record<EmailCampaign["status"], string>> = {
    draft: "Draft",
    ready: "Pregătită",
    paused: "Pauză",
    completed: "Finalizată",
  };
  return labels[status] ?? status;
}

export function isCampaignRecipientEffectivelyActive(recipient: CampaignRecipientRow): boolean {
  return recipient.status !== "suppressed"
    && recipient.status !== "unsubscribed"
    && recipient.status !== "archived";
}

export function campaignRecipientSourceLabel(source?: string | null): string {
  if (!source) return "Manual";
  if (source === "manual") return "Manual";
  if (source === "excel_import") return "Excel";
  if (source === "local_preview") return "Import contacte";
  if (source === "segment_backfill") return "Segment";
  return source.replace(/_/g, " ");
}
