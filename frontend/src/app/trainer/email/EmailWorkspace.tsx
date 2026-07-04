"use client";

import Image from "next/image";
import Link from "next/link";
import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  listEmailTemplatesOnServer,
  createEmailTemplateOnServer,
  updateEmailTemplateOnServer,
  deleteEmailTemplateOnServer,
  deleteCampaignOnServer,
  deleteCampaignRecipientOnServer,
  bulkCreateCampaignRecipientsOnServer,
  buildVideoCampaignCreatePayload,
  createCampaignOnServer,
  listCampaignsOnServer,
  sendCampaignOnServer,
  updateCampaignOnServer,
  updateCampaignRecipientOnServer,
  uploadCampaignAssetOnServer,
  type EmailOpsSummary,
  type AssessmentDeliveryRow,
  type CampaignRecipientRow,
  type CampaignRecipientCreate,
  type CampaignSendResponse,
  type EmailCampaign,
  type EmailTemplate
} from "@/api/email";

type TabKey = "delivery" | "campaigns" | "templates";


const MOCK_REPLACEMENTS: Record<string, string> = {
  "{first_name}": "Ioana",
  "{last_name}": "Popescu",
  "{participant_name}": "Ioana Popescu",
  "{trainer_name}": "Echipa Codruț",
  "{company_name}": "Compania Pilot",
  "{organization_name}": "Compania Pilot",
  "{contact_name}": "Ioana Popescu",
  "{email}": "ioana.popescu@example.com",
  "{action_url}": "https://codrut.andreivacaru.ro/invite/demo-token",
  "{project}": "Intake Iunie",
  "{link_securizat}": "https://codrut.andreivacaru.ro/auth/seclink-8f2a175",
  "{estimare_timp}": "15",
  "{sarcini_ramase}": "2 chestionare rămase (Lencioni, Distress)",
  "{link_video}": "https://watch.codrut.ro/v/performanta-echipe-2026",
  "{video_url}": "https://vimeo.com/123456789",
  "{thumbnail_url}": "https://codrut.andreivacaru.ro/api/campaign-assets/demo.jpg",
  "{landing_page_url}": "https://vimeo.com/123456789",
  "{unsubscribe_url}": "https://codrut.andreivacaru.ro/api/communications/campaigns/unsubscribe/demo-token",
};

function detectedPlaceholders(subject: string, body: string): string[] {
  const placeholderRegex = /\{[a-z0-9_]+\}/gi;
  return Array.from(new Set(`${subject} ${body}`.match(placeholderRegex) || []));
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function sanitizePreviewHref(value: string): string {
  const trimmed = value.trim();
  try {
    const parsed = new URL(trimmed, "https://codrut.andreivacaru.ro");
    if (["http:", "https:", "mailto:"].includes(parsed.protocol)) {
      return trimmed;
    }
  } catch {
    // Fall through to a harmless placeholder when the markdown URL is invalid.
  }
  return "#";
}

export function replacePreviewPlaceholders(value: string): string {
  let replaced = value;
  Object.entries(MOCK_REPLACEMENTS).forEach(([key, replacement]) => {
    replaced = replaced
      .replace(new RegExp(escapeRegExp(`$${key}`), "g"), replacement)
      .replace(new RegExp(escapeRegExp(key), "g"), replacement);
  });
  return replaced;
}

function looksLikeHtml(value: string): boolean {
  return /^\s*<\/?[a-z][\s\S]*>/i.test(value);
}

function sanitizePreviewHtml(value: string): string {
  if (typeof DOMParser === "undefined") {
    return escapeHtml(value);
  }

  const allowedTags = new Set([
    "A",
    "B",
    "BR",
    "DIV",
    "EM",
    "H1",
    "H2",
    "H3",
    "IMG",
    "LI",
    "OL",
    "P",
    "SPAN",
    "STRONG",
    "UL",
  ]);
  const allowedAttributes = new Set(["alt", "class", "height", "href", "src", "style", "target", "width"]);
  const allowedUrlAttributes = new Set(["href", "src"]);
  const parser = new DOMParser();
  const document = parser.parseFromString(value, "text/html");
  const nodes = Array.from(document.body.querySelectorAll("*"));

  nodes.forEach((node) => {
    if (!allowedTags.has(node.tagName)) {
      node.replaceWith(...Array.from(node.childNodes));
      return;
    }

    Array.from(node.attributes).forEach((attribute) => {
      const attributeName = attribute.name.toLowerCase();
      if (!allowedAttributes.has(attributeName) || attributeName.startsWith("on")) {
        node.removeAttribute(attribute.name);
        return;
      }

      if (allowedUrlAttributes.has(attributeName)) {
        const safeUrl = sanitizePreviewHref(attribute.value);
        node.setAttribute(attribute.name, safeUrl);
      } else if (
        attributeName === "style"
        && /(javascript\s*:|expression\s*\(|url\s*\()/i.test(attribute.value)
      ) {
        node.removeAttribute(attribute.name);
      }
    });

    if (node.tagName === "A") {
      node.setAttribute("rel", "noreferrer");
      node.setAttribute("target", "_blank");
    }
  });

  return document.body.innerHTML;
}

export function renderEmailTemplatePreviewBody(body: string): string {
  if (looksLikeHtml(body)) {
    return sanitizePreviewHtml(body);
  }
  return escapeHtml(body)
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[(.*?)\]\((.*?)\)/g, (_match, label: string, href: string) => {
      const safeHref = escapeHtml(sanitizePreviewHref(href));
      return `<a href="${safeHref}" target="_blank" rel="noreferrer" class="text-burgundy underline font-bold">${label}</a>`;
    })
    .replace(/\r?\n/g, "<br />");
}

function upsertEmailTemplate(templates: EmailTemplate[], template: EmailTemplate): EmailTemplate[] {
  const nextTemplates = [...templates];
  const existingIndex = nextTemplates.findIndex((item) => item.id === template.id);
  if (existingIndex >= 0) {
    nextTemplates[existingIndex] = template;
  } else {
    nextTemplates.unshift(template);
  }
  return nextTemplates;
}

type CampaignContactDraft = {
  email: string;
  contact_name: string;
  organization_name: string;
  segment: "past_customer" | "potential_customer";
  status: "active" | "suppressed";
};

type CampaignRecipientImportResult = {
  recipients: CampaignRecipientCreate[];
  skippedBySendFlag: number;
  skippedMissingEmail: number;
  skippedInvalidEmail: number;
};

type CampaignImportDraft = {
  id: string;
  rowNumber: number;
  email: string;
  contact_name: string;
  organization_name: string;
  segment: "past_customer" | "potential_customer";
  send: boolean;
  source: string;
};

function normalizeImportKey(value: string): string {
  return value.trim().toLowerCase().replace(/\s+/g, " ");
}

function normalizeImportValue(value: unknown): string {
  return value == null ? "" : String(value).trim();
}

function readImportValue(row: Record<string, unknown>, keys: string[]): string {
  const wantedKeys = new Set(keys.map(normalizeImportKey));
  for (const [key, value] of Object.entries(row)) {
    if (wantedKeys.has(normalizeImportKey(key))) {
      const normalizedValue = normalizeImportValue(value);
      if (normalizedValue) {
        return normalizedValue;
      }
    }
  }
  return "";
}

function isMarkedForCampaignSend(row: Record<string, unknown>): boolean {
  const sendValue = readImportValue(row, ["De trimis"]);
  if (!sendValue) {
    return true;
  }
  return ["da", "yes", "y", "1", "true"].includes(normalizeImportKey(sendValue));
}

function isValidImportEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

export function selectCampaignRecipientImportSheetName(sheetNames: string[]): string | undefined {
  return sheetNames.find((sheetName) => normalizeImportKey(sheetName) === "revised") ?? sheetNames[0];
}

function importSegmentFromValue(value: string): "past_customer" | "potential_customer" {
  const normalized = normalizeImportKey(value);
  if (!normalized) {
    return "potential_customer";
  }
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
  const explicitName = readImportValue(row, ["name", "nume", "Name", "Nume"]);
  if (explicitName) {
    return explicitName;
  }
  return [
    readImportValue(row, ["Primul prenume"]),
    readImportValue(row, ["Al doilea prenume"]),
    readImportValue(row, ["Nume de familie"]),
  ].filter(Boolean).join(" ");
}

export function buildCampaignRecipientImportDrafts(rows: Record<string, unknown>[]): CampaignImportDraft[] {
  return rows.map((row, index) => {
    const segmentValue = readImportValue(row, ["segment", "Segment", "Tip Client"]);
    return {
      id: `${index}-${readImportValue(row, ["email", "Email", "EMAIL"]) || "missing"}`,
      rowNumber: index + 2,
      email: readImportValue(row, ["email", "Email", "EMAIL"]),
      contact_name: importContactName(row),
      organization_name: readImportValue(row, ["company", "companie", "Company", "Companie", "Organizație"]),
      segment: importSegmentFromValue(segmentValue),
      send: isMarkedForCampaignSend(row),
      source: "excel_import",
    };
  });
}

function campaignImportDraftToRecipient(row: CampaignImportDraft): CampaignRecipientCreate {
  return {
    email: row.email.trim(),
    contact_name: row.contact_name.trim() || undefined,
    organization_name: row.organization_name.trim() || undefined,
    segment: row.segment,
    status: row.send ? "active" : "suppressed",
    source: row.source,
  };
}

export function buildCampaignRecipientImport(rows: Record<string, unknown>[]): CampaignRecipientImportResult {
  return rows.reduce<CampaignRecipientImportResult>(
    (result, row) => {
      const email = readImportValue(row, ["email", "Email", "EMAIL"]);
      if (!email) {
        result.skippedMissingEmail += 1;
        return result;
      }
      if (!isValidImportEmail(email)) {
        result.skippedInvalidEmail += 1;
        return result;
      }

      const segmentValue = readImportValue(row, ["segment", "Segment", "Tip Client"]);
      result.recipients.push({
        email,
        contact_name: importContactName(row) || undefined,
        organization_name: readImportValue(row, ["company", "companie", "Company", "Companie", "Organizație"]) || undefined,
        segment: importSegmentFromValue(segmentValue),
        status: isMarkedForCampaignSend(row) ? "active" : "suppressed",
        source: "excel_import",
      });
      return result;
    },
    { recipients: [], skippedBySendFlag: 0, skippedMissingEmail: 0, skippedInvalidEmail: 0 },
  );
}

function campaignRecipientName(recipient: CampaignRecipientRow): string {
  return [recipient.firstName, recipient.lastName].filter(Boolean).join(" ");
}

function campaignRecipientSegment(recipient: CampaignRecipientRow): "past_customer" | "potential_customer" {
  return recipient.clientType === "tip_1" ? "past_customer" : "potential_customer";
}

function splitContactName(value: string): { firstName?: string; lastName?: string } {
  const [firstName, ...lastNameParts] = value.trim().split(/\s+/).filter(Boolean);
  const lastName = lastNameParts.join(" ");
  return {
    firstName: firstName || undefined,
    lastName: lastName || undefined,
  };
}

function campaignRecipientDraft(recipient: CampaignRecipientRow): CampaignContactDraft {
  return {
    email: recipient.email,
    contact_name: campaignRecipientName(recipient),
    organization_name: recipient.company === "Companie necompletată" ? "" : recipient.company,
    segment: campaignRecipientSegment(recipient),
    status: recipient.status === "suppressed" ? "suppressed" : "active",
  };
}

type EmailWorkspaceProps = {
  initialSummary: EmailOpsSummary;
};

export function EmailWorkspace({ initialSummary }: EmailWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<TabKey>("templates");
  const [summary, setSummary] = useState<EmailOpsSummary>(initialSummary);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const refreshSummary = async () => {
    setIsRefreshing(true);
    try {
      const { getEmailOpsSummary } = await import("@/api/email");
      const fresh = await getEmailOpsSummary();
      setSummary(fresh);
    } finally {
      setIsRefreshing(false);
    }
  };

  // Template Manager States
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<string>("");
  const [isEditing, setIsEditing] = useState(false);
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(false);

  // Editor fields
  const [editName, setEditName] = useState("");
  const [editSubject, setEditSubject] = useState("");
  const [editBody, setEditBody] = useState("");
  const [editLane, setEditLane] = useState<"transactional" | "campaign">("transactional");

  // Campaign Manager States
  const [isUploadingCSV, setIsUploadingCSV] = useState(false);
  const [importSheetName, setImportSheetName] = useState<string | null>(null);
  const [importDrafts, setImportDrafts] = useState<CampaignImportDraft[]>([]);
  const [isImportingContacts, setIsImportingContacts] = useState(false);
  const [campaigns, setCampaigns] = useState<EmailCampaign[]>([]);
  const [isLoadingCampaigns, setIsLoadingCampaigns] = useState(false);
  const [isCreatingCampaign, setIsCreatingCampaign] = useState(false);
  const [showCampaignModal, setShowCampaignModal] = useState(false);
  const [editingCampaign, setEditingCampaign] = useState<EmailCampaign | null>(null);
  const [campaignView, setCampaignView] = useState<"contacts" | "campaigns">("contacts");
  const [campaignName, setCampaignName] = useState("Campanie video leadership");
  const [campaignSegment, setCampaignSegment] = useState<"past_customer" | "potential_customer">("potential_customer");
  const [campaignTemplateId, setCampaignTemplateId] = useState("");
  const [campaignSubject, setCampaignSubject] = useState("O idee practică pentru echipa ta, {first_name}");
  const [campaignBody, setCampaignBody] = useState("");
  const [campaignTextBody, setCampaignTextBody] = useState("");
  const [campaignVideoUrl, setCampaignVideoUrl] = useState("");
  const [campaignThumbnailUrl, setCampaignThumbnailUrl] = useState("");
  const [campaignLandingUrl, setCampaignLandingUrl] = useState("");
  const [campaignMessage, setCampaignMessage] = useState<string | null>(null);
  const [campaignAssetMessage, setCampaignAssetMessage] = useState<string | null>(null);
  const [isUploadingCampaignAsset, setIsUploadingCampaignAsset] = useState(false);
  const [sendingCampaignId, setSendingCampaignId] = useState<string | null>(null);
  const [deletingCampaignId, setDeletingCampaignId] = useState<string | null>(null);
  const [campaignSendResults, setCampaignSendResults] = useState<Record<string, CampaignSendResponse>>({});
  const [campaignContactMessage, setCampaignContactMessage] = useState<string | null>(null);
  const [selectedCampaignRecipientIds, setSelectedCampaignRecipientIds] = useState<string[]>([]);
  const [editingContactId, setEditingContactId] = useState<string | null>(null);
  const [contactDrafts, setContactDrafts] = useState<Record<string, CampaignContactDraft>>({});
  const [savingContactId, setSavingContactId] = useState<string | null>(null);
  const [deletingContactId, setDeletingContactId] = useState<string | null>(null);

  const activeCampaignRecipientIdSet = useMemo(
    () => new Set(summary.campaign.recipients.filter((recipient) => recipient.status !== "suppressed").map((recipient) => recipient.id)),
    [summary.campaign.recipients],
  );
  const activeSelectedCampaignRecipientIds = useMemo(
    () => selectedCampaignRecipientIds.filter((recipientId) => activeCampaignRecipientIdSet.has(recipientId)),
    [activeCampaignRecipientIdSet, selectedCampaignRecipientIds],
  );

  const campaignTemplates = useMemo(
    () => templates.filter((template) => {
      if (template.lane !== "campaign") return false;
      const audience = template.audience ?? "";
      if (campaignSegment === "past_customer") return audience.includes("past_customer");
      return audience.includes("potential_customer");
    }),
    [campaignSegment, templates],
  );

  const selectedCampaignTemplate = useMemo(
    () => campaignTemplates.find((template) => template.id === campaignTemplateId) ?? null,
    [campaignTemplateId, campaignTemplates],
  );

  function resetCampaignModal() {
    setEditingCampaign(null);
    setCampaignName("Campanie video leadership");
    setCampaignSegment("potential_customer");
    setCampaignTemplateId("");
    setCampaignSubject("O idee practică pentru echipa ta, {first_name}");
    setCampaignBody("");
    setCampaignTextBody("");
    setCampaignVideoUrl("");
    setCampaignThumbnailUrl("");
    setCampaignLandingUrl("");
    setCampaignAssetMessage(null);
  }

  function openCreateCampaignModal() {
    resetCampaignModal();
    setCampaignMessage(null);
    setShowCampaignModal(true);
  }

  function openEditCampaignModal(campaign: EmailCampaign) {
    setEditingCampaign(campaign);
    setCampaignName(campaign.name);
    setCampaignSegment(campaign.segment);
    setCampaignTemplateId("");
    setCampaignSubject(campaign.subject.replace(/\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "{$1}"));
    setCampaignBody(campaign.html_body.replace(/\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "{$1}"));
    setCampaignTextBody(campaign.text_body.replace(/\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "{$1}"));
    setCampaignVideoUrl(campaign.video_url ?? "");
    setCampaignThumbnailUrl(campaign.thumbnail_url ?? "");
    setCampaignLandingUrl(campaign.landing_page_url ?? "");
    setCampaignAssetMessage(null);
    setCampaignMessage(null);
    setShowCampaignModal(true);
  }

  // Manual Add State
  const [showManualAddModal, setShowManualAddModal] = useState(false);
  const [manualEmail, setManualEmail] = useState("");
  const [manualName, setManualName] = useState("");
  const [manualCompany, setManualCompany] = useState("");
  const [manualSegment, setManualSegment] = useState<"past_customer" | "potential_customer">("potential_customer");
  const [isAddingManual, setIsAddingManual] = useState(false);

  const handleAddManualContact = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!manualEmail.trim()) return;
    setIsAddingManual(true);
    setCampaignContactMessage(null);
    try {
      await bulkCreateCampaignRecipientsOnServer([{
        email: manualEmail.trim(),
        contact_name: manualName.trim() || undefined,
        organization_name: manualCompany.trim() || undefined,
        segment: manualSegment,
      }]);
      setCampaignContactMessage("Contactul a fost adăugat.");
      setShowManualAddModal(false);
      setManualEmail("");
      setManualName("");
      setManualCompany("");
      await refreshSummary();
    } catch (error) {
      setCampaignContactMessage(error instanceof Error ? error.message : "Contactul nu a putut fi adăugat.");
    } finally {
      setIsAddingManual(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploadingCSV(true);
    try {
      const XLSX = await import("xlsx");
      const data = await file.arrayBuffer();
      const workbook = XLSX.read(data, { type: "array" });
      const sheetName = selectCampaignRecipientImportSheetName(workbook.SheetNames);
      const selectedSheet = sheetName ? workbook.Sheets[sheetName] : undefined;
      const rows = selectedSheet
        ? XLSX.utils.sheet_to_json(selectedSheet) as Record<string, unknown>[]
        : [];
      const drafts = buildCampaignRecipientImportDrafts(rows);

      if (drafts.length > 0) {
        const invalidCount = drafts.filter((draft) => !isValidImportEmail(draft.email.trim())).length;
        setImportSheetName(sheetName ?? null);
        setImportDrafts(drafts);
        setCampaignContactMessage(
          `Previzualizare ${drafts.length} contacte din sheet-ul ${sheetName}.${invalidCount > 0 ? ` ${invalidCount} emailuri trebuie corectate.` : ""}`,
        );
      } else {
        setCampaignContactMessage("Fișierul nu conține coloana email. Folosește un cap de tabel valid.");
      }
    } catch (error) {
      setCampaignContactMessage(error instanceof Error ? error.message : "Fișierul nu a putut fi procesat.");
    } finally {
      setIsUploadingCSV(false);
      e.target.value = "";
    }
  };

  const updateImportDraft = <K extends keyof CampaignImportDraft>(
    rowId: string,
    field: K,
    value: CampaignImportDraft[K],
  ) => {
    setImportDrafts((previousDrafts) =>
      previousDrafts.map((draft) =>
        draft.id === rowId ? { ...draft, [field]: value } : draft,
      ),
    );
  };

  const invalidImportDraftCount = importDrafts.filter((draft) => !isValidImportEmail(draft.email.trim())).length;
  const activeImportDraftCount = importDrafts.filter((draft) => draft.send).length;

  const confirmCampaignRecipientImport = async () => {
    if (invalidImportDraftCount > 0) {
      setCampaignContactMessage("Corectează emailurile invalide înainte de import.");
      return;
    }
    setIsImportingContacts(true);
    try {
      await bulkCreateCampaignRecipientsOnServer(importDrafts.map(campaignImportDraftToRecipient));
      setCampaignContactMessage(
        `S-au importat ${importDrafts.length} contacte: ${activeImportDraftCount} active, ${importDrafts.length - activeImportDraftCount} inactive.`,
      );
      setImportDrafts([]);
      setImportSheetName(null);
      await refreshSummary();
    } catch (error) {
      setCampaignContactMessage(error instanceof Error ? error.message : "Contactele nu au putut fi importate.");
    } finally {
      setIsImportingContacts(false);
    }
  };

  const loadCampaigns = useCallback(async () => {
    setIsLoadingCampaigns(true);
    try {
      setCampaigns(await listCampaignsOnServer());
    } finally {
      setIsLoadingCampaigns(false);
    }
  }, []);

  useEffect(() => {
    loadCampaigns();
  }, [loadCampaigns]);

  const handleCampaignAssetUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setIsUploadingCampaignAsset(true);
    setCampaignAssetMessage(null);
    try {
      const asset = await uploadCampaignAssetOnServer(file);
      setCampaignThumbnailUrl(asset.url);
      setCampaignAssetMessage(`Thumbnail încărcat: ${(asset.size_bytes / 1024).toFixed(1)} KB.`);
    } catch (error) {
      setCampaignAssetMessage(
        error instanceof Error ? error.message : "Thumbnailul nu a putut fi încărcat.",
      );
    } finally {
      setIsUploadingCampaignAsset(false);
      event.target.value = "";
    }
  };

  const handleSaveCampaign = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const templateBody = campaignBody || selectedCampaignTemplate?.body || "";
    const templateText = campaignTextBody || templateBody.replace(/<[^>]*>/g, "");
    const payload = buildVideoCampaignCreatePayload({
      name: campaignName,
      segment: campaignSegment,
      subject: campaignSubject,
      htmlBody: templateBody,
      textBody: templateText,
      videoUrl: campaignVideoUrl,
      thumbnailUrl: campaignThumbnailUrl,
      landingUrl: campaignLandingUrl,
    });

    if (!payload) {
      setCampaignMessage("Completează numele, linkul Vimeo/video și un thumbnail valid.");
      return;
    }

    setIsCreatingCampaign(true);
    setCampaignMessage(null);
    try {
      if (editingCampaign) {
        await updateCampaignOnServer(editingCampaign.id, {
          ...payload,
          landing_page_url: campaignLandingUrl.trim() ? payload.landing_page_url : null,
          status: editingCampaign.status,
        });
        setCampaignMessage("Campania a fost actualizată.");
      } else {
        await createCampaignOnServer(payload);
        setCampaignMessage("Campania a fost salvată.");
      }
      setShowCampaignModal(false);
      setEditingCampaign(null);
      await loadCampaigns();
    } catch (error) {
      setCampaignMessage(error instanceof Error ? error.message : "Campania nu a putut fi salvată.");
    } finally {
      setIsCreatingCampaign(false);
    }
  };

  const startEditingContact = (recipient: CampaignRecipientRow) => {
    setEditingContactId(recipient.id);
    setCampaignContactMessage(null);
    setContactDrafts((drafts) => ({
      ...drafts,
      [recipient.id]: drafts[recipient.id] ?? campaignRecipientDraft(recipient),
    }));
  };

  const updateContactDraft = <Field extends keyof CampaignContactDraft>(
    recipientId: string,
    field: Field,
    value: CampaignContactDraft[Field],
  ) => {
    setContactDrafts((drafts) => ({
      ...drafts,
      [recipientId]: {
        ...(drafts[recipientId] ?? {
          email: "",
          contact_name: "",
          organization_name: "",
          segment: "potential_customer",
          status: "active",
        }),
        [field]: value,
      },
    }));
  };

  const cancelEditingContact = (recipientId: string) => {
    setEditingContactId(null);
    setContactDrafts((drafts) => {
      const nextDrafts = { ...drafts };
      delete nextDrafts[recipientId];
      return nextDrafts;
    });
  };

  const saveContact = async (recipient: CampaignRecipientRow) => {
    const draft = contactDrafts[recipient.id] ?? campaignRecipientDraft(recipient);
    if (!draft.email.trim()) {
      setCampaignContactMessage("Emailul contactului este obligatoriu.");
      return;
    }

    setSavingContactId(recipient.id);
    setCampaignContactMessage(null);
    try {
      await updateCampaignRecipientOnServer(recipient.id, {
        email: draft.email.trim(),
        contact_name: draft.contact_name.trim(),
        organization_name: draft.organization_name.trim(),
        segment: draft.segment,
        status: draft.status,
      });
      const nameParts = splitContactName(draft.contact_name);
      setSummary((currentSummary) => ({
        ...currentSummary,
        campaign: {
          ...currentSummary.campaign,
          recipients: currentSummary.campaign.recipients.map((currentRecipient) =>
            currentRecipient.id === recipient.id
              ? {
                  ...currentRecipient,
                  email: draft.email.trim(),
                  company: draft.organization_name.trim() || "Companie necompletată",
                  firstName: nameParts.firstName,
                  lastName: nameParts.lastName,
                  clientType: draft.segment === "past_customer" ? "tip_1" : "tip_2",
                  status: draft.status === "suppressed" ? "suppressed" : "ready",
                }
              : currentRecipient,
          ),
        },
      }));
      setCampaignContactMessage("Contactul a fost actualizat.");
      cancelEditingContact(recipient.id);
    } catch (error) {
      setCampaignContactMessage(error instanceof Error ? error.message : "Contactul nu a putut fi actualizat.");
    } finally {
      setSavingContactId(null);
    }
  };

  const deleteContact = async (recipient: CampaignRecipientRow) => {
    const confirmed = window.confirm(`Ștergi contactul ${recipient.email}? Istoricul agregat de email rămâne în rapoarte.`);
    if (!confirmed) return;

    setDeletingContactId(recipient.id);
    setCampaignContactMessage(null);
    try {
      await deleteCampaignRecipientOnServer(recipient.id);
      setCampaignContactMessage("Contactul a fost șters.");
      if (editingContactId === recipient.id) {
        cancelEditingContact(recipient.id);
      }
      setSummary((currentSummary) => ({
        ...currentSummary,
        campaign: {
          ...currentSummary.campaign,
          recipients: currentSummary.campaign.recipients.filter(
            (currentRecipient) => currentRecipient.id !== recipient.id,
          ),
        },
      }));
    } catch (error) {
      setCampaignContactMessage(error instanceof Error ? error.message : "Contactul nu a putut fi șters.");
    } finally {
      setDeletingContactId(null);
    }
  };

  const toggleSelectedCampaignRecipient = (recipientId: string) => {
    if (!activeCampaignRecipientIdSet.has(recipientId)) return;
    setSelectedCampaignRecipientIds((currentIds) =>
      currentIds.includes(recipientId)
        ? currentIds.filter((id) => id !== recipientId)
        : [...currentIds, recipientId],
    );
  };

  const handleSendCampaign = async (
    campaign: EmailCampaign,
    mode: "new" | "all" | "selected" = "new",
  ) => {
    const selectedRecipientIds = mode === "selected" ? activeSelectedCampaignRecipientIds : undefined;
    if (mode === "selected" && activeSelectedCampaignRecipientIds.length === 0) {
      setCampaignMessage("Selectează cel puțin un contact activ înainte de trimitere.");
      return;
    }
    const confirmed = window.confirm(
      mode === "selected"
        ? `Trimiți campania „${campaign.name}” către ${activeSelectedCampaignRecipientIds.length} contacte selectate?`
        : mode === "all"
        ? `Trimiți campania „${campaign.name}” către toate contactele active din segment, inclusiv cele care au mai primit-o?`
        : `Trimiți campania „${campaign.name}” doar către contactele active care nu au primit-o încă?`,
    );
    if (!confirmed) return;

    setSendingCampaignId(campaign.id);
    setCampaignMessage(null);
    try {
      const result = await sendCampaignOnServer(campaign.id, { mode, recipientIds: selectedRecipientIds });
      setCampaignSendResults((previousResults) => ({
        ...previousResults,
        [campaign.id]: result,
      }));
      setCampaignMessage(
        `Campania a fost procesată: ${result.sent} trimise, ${result.failed} eșuate, ${result.skipped} omise.`,
      );
      await Promise.all([loadCampaigns(), refreshSummary()]);
    } catch (error) {
      setCampaignMessage(error instanceof Error ? error.message : "Campania nu a putut fi trimisă.");
    } finally {
      setSendingCampaignId(null);
    }
  };

  const handleDeleteCampaign = async (campaign: EmailCampaign) => {
    const confirmed = window.confirm(
      `Ștergi campania „${campaign.name}”? Contactele și istoricul de livrare rămân păstrate.`,
    );
    if (!confirmed) return;

    setDeletingCampaignId(campaign.id);
    setCampaignMessage(null);
    try {
      await deleteCampaignOnServer(campaign.id);
      setCampaignSendResults((previousResults) => {
        const nextResults = { ...previousResults };
        delete nextResults[campaign.id];
        return nextResults;
      });
      setCampaignMessage("Campania a fost ștearsă.");
      await loadCampaigns();
    } catch (error) {
      setCampaignMessage(error instanceof Error ? error.message : "Campania nu a putut fi ștearsă.");
    } finally {
      setDeletingCampaignId(null);
    }
  };

  // Search state
  const [searchQuery, setSearchQuery] = useState("");

  const filteredTemplates = React.useMemo(() => {
    const visibleTemplates = templates.filter((template) => !template.baseKey.startsWith("template_"));
    if (!searchQuery.trim()) return visibleTemplates;
    const q = searchQuery.toLowerCase();
    return visibleTemplates.filter((t) =>
      t.name.toLowerCase().includes(q) ||
      t.subject.toLowerCase().includes(q)
    );
  }, [templates, searchQuery]);
  const templatesById = useMemo(() => {
    const byId = new Map<string, EmailTemplate>();
    for (const template of templates) {
      byId.set(template.id, template);
    }
    return byId;
  }, [templates]);

  // Load templates from Server
  const loadTemplates = useCallback(async () => {
    setIsLoadingTemplates(true);
    try {
      const list = await listEmailTemplatesOnServer();
      setTemplates(list);
    } finally {
      setIsLoadingTemplates(false);
    }
  }, []);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  // Sync editor fields when selected template changes
  const selectedTemplate = templatesById.get(selectedTemplateId);
  useEffect(() => {
    if (selectedTemplate) {
      setEditName(selectedTemplate.name);
      setEditSubject(selectedTemplate.subject);
      setEditBody(selectedTemplate.body);
      setEditLane(selectedTemplate.lane);
    }
  }, [selectedTemplate]);

  const handleSaveTemplate = async () => {
    if (!selectedTemplateId || !selectedTemplate) return;
    setIsLoadingTemplates(true);
    try {
      const updatedTemp: EmailTemplate = {
        ...selectedTemplate,
        subject: editSubject,
        body: editBody,
        lane: editLane,
        placeholders: detectedPlaceholders(editSubject, editBody),
      };
      const saved = await updateEmailTemplateOnServer(updatedTemp);
      setIsEditing(false);
      setSelectedTemplateId(saved.id);
      setTemplates((previousTemplates) => upsertEmailTemplate(previousTemplates, saved));
    } catch (e) {
      alert((e as Error).message ?? "Eroare la salvarea șablonului.");
    } finally {
      setIsLoadingTemplates(false);
    }
  };

  const handleCreateTemplate = async () => {
    const key = `template_${Date.now()}`;
    const newTemp: EmailTemplate = {
      id: key,
      baseKey: key,
      version: 1,
      name: "Șablon Email Nou",
      subject: "Subiectul emailului {first_name}",
      lane: "transactional",
      placeholders: ["{first_name}"],
      body: `Salut {first_name},

Introduceți conținutul noului șablon email aici. Puteți folosi coduri între acolade pentru personalizare.`,
    };
    setIsLoadingTemplates(true);
    try {
      const saved = await createEmailTemplateOnServer(newTemp);
      setSelectedTemplateId(saved.id);
      setIsEditing(true);
      setTemplates((previousTemplates) => upsertEmailTemplate(previousTemplates, saved));
    } catch (e) {
      alert((e as Error).message ?? "Eroare la crearea șablonului.");
    } finally {
      setIsLoadingTemplates(false);
    }
  };

  const handleCreateTemplateVersion = async () => {
    if (!selectedTemplate) return;
    setIsLoadingTemplates(true);
    try {
      const nextTemplate: EmailTemplate = {
        ...selectedTemplate,
        version: selectedTemplate.version + 1,
      };
      const saved = await createEmailTemplateOnServer(nextTemplate);
      setSelectedTemplateId(saved.id);
      setIsEditing(true);
      setTemplates((previousTemplates) => upsertEmailTemplate(previousTemplates, saved));
    } catch (e) {
      alert((e as Error).message ?? "Eroare la crearea versiunii noi.");
    } finally {
      setIsLoadingTemplates(false);
    }
  };

  const handleDeleteTemplate = async () => {
    if (!selectedTemplate) return;
    if (templates.length <= 1) {
      alert("Trebuie să păstrați cel puțin un șablon în catalog.");
      return;
    }
    if (!confirm("Sigur doriți să pensionați acest șablon?")) return;

    setIsLoadingTemplates(true);
    try {
      await deleteEmailTemplateOnServer(selectedTemplate.baseKey); // Fix: Remove version to delete the whole template
      const remaining = templates.filter((t) => t.baseKey !== selectedTemplate.baseKey);
      setTemplates(remaining);
      if (remaining.length > 0) {
        setSelectedTemplateId(remaining[0].id);
      } else {
        setSelectedTemplateId("");
      }
      setIsEditing(false);
    } catch (e) {
      alert((e as Error).message ?? "Eroare la pensionarea șablonului.");
    } finally {
      setIsLoadingTemplates(false);
    }
  };

  // Convert markdown to clean, basic HTML preview
  const getRenderedPreview = (subjectText: string, bodyText: string, lane: string) => {
    let replacedSubject = subjectText;
    let replacedBody = bodyText;

    replacedSubject = replacePreviewPlaceholders(replacedSubject);
    replacedBody = replacePreviewPlaceholders(replacedBody);

    let html = renderEmailTemplatePreviewBody(replacedBody);

    if (lane === "campaign") {
      html += `
        <div style="margin-top:24px;padding-top:24px;border-top:1px solid #eadfdb;font-size:12px;line-height:1.5;color:#8c7e7b;text-align:center;font-family:sans-serif;">
          <p style="margin:0 0 8px;">Ai primit acest email deoarece ești abonat la actualizările noastre sau ești un client.</p>
          <p style="margin:0 0 8px;">
            <a href="https://codrut.andreivacaru.ro/unsubscribe" style="color:#6d5f5b;text-decoration:underline;">Dezabonare</a>
          </p>
          <p style="margin:0;">Str. Exemplu Nr. 10, București, România</p>
        </div>
      `;
    }

    return {
      subject: replacedSubject,
      bodyHtml: html,
    };
  };

  const preview = useMemo(
    () =>
      selectedTemplate
        ? getRenderedPreview(
            isEditing ? editSubject : selectedTemplate.subject,
            isEditing ? editBody : selectedTemplate.body,
            isEditing ? editLane : selectedTemplate.lane,
          )
        : { subject: "", bodyHtml: "" },
    [editBody, editLane, editSubject, isEditing, selectedTemplate],
  );
  const campaignPreview = useMemo(
    () => getRenderedPreview(
      campaignSubject,
      campaignBody || selectedCampaignTemplate?.body || "",
      "campaign",
    ),
    [campaignBody, campaignSubject, selectedCampaignTemplate],
  );

  const deliveryLabel = (delivery: AssessmentDeliveryRow["delivery"]) => {
    switch (delivery) {
      case "draft":
        return "Ciornă";
      case "sent":
        return "Trimis";
      case "delivered":
        return "Livrat";
      case "opened":
        return "Deschis";
      case "failed":
        return "Eșuat";
      default:
        return delivery;
    }
  };

  const reminderLabel = (reminder: AssessmentDeliveryRow["reminder"]) => {
    switch (reminder) {
      case "today":
        return "Azi";
      case "tomorrow":
        return "Mâine";
      case "paused":
        return "Oprit";
      default:
        return "Fără";
    }
  };

  return (
    <div className="space-y-8">
      <div className="surface-panel flex flex-wrap gap-2 p-2">
        <button
          onClick={() => setActiveTab("templates")}
          className={`rounded-full px-5 py-2.5 text-sm font-bold transition-all ${
            activeTab === "templates"
              ? "bg-burgundy text-white shadow-sm"
              : "text-foreground/55 hover:bg-surface-muted hover:text-foreground"
          }`}
        >
          Șabloane email
        </button>
        <button
          onClick={() => setActiveTab("delivery")}
          className={`rounded-full px-5 py-2.5 text-sm font-bold transition-all ${
            activeTab === "delivery"
              ? "bg-burgundy text-white shadow-sm"
              : "text-foreground/55 hover:bg-surface-muted hover:text-foreground"
          }`}
        >
          Arhivă globală
        </button>
        <button
          onClick={() => setActiveTab("campaigns")}
          className={`rounded-full px-5 py-2.5 text-sm font-bold transition-all ${
            activeTab === "campaigns"
              ? "bg-burgundy text-white shadow-sm"
              : "text-foreground/55 hover:bg-surface-muted hover:text-foreground"
          }`}
        >
          Campanii
        </button>
      </div>

      {activeTab === "delivery" && (
        <div className="space-y-6">
          <section className="surface-panel overflow-hidden">
            <div className="flex flex-col gap-6 p-6 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80">Context global</p>
                <h2 className="mt-2 font-display text-2xl font-bold text-foreground">Invitațiile live se operează din companie</h2>
                <p className="mt-3 max-w-2xl text-sm leading-relaxed text-foreground/60">
                  Această pagină păstrează o privire agregată și șabloanele. Pentru a trimite emailuri, genera linkuri securizate sau verifica statusul unei persoane, deschide proiectul și tabul Invitații.
                </p>
              </div>
              <Link
                href="/trainer/companies"
                className="btn-premium shrink-0"
              >
                Deschide companii
              </Link>
            </div>
          </section>

          {/* Metrics summary grid */}
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {summary.metrics.map((metric) => (
              <article key={metric.label} className="surface-panel p-6">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-burgundy/70">{metric.label}</p>
                  <p className="mt-3 font-display text-4xl font-bold text-foreground tracking-tight">{metric.value}</p>
                  <p className="mt-2 text-sm leading-relaxed text-foreground/50">{metric.detail}</p>
                </div>
              </article>
            ))}
          </div>

          {/* Delivery Queue table */}
            <section className="surface-panel overflow-hidden">
            <div className="border-b border-[var(--border)] px-8 py-6 bg-surface-muted">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80">Invitații</p>
              <h2 className="mt-2 text-xl font-bold text-foreground">Status acces participanți</h2>
              <p className="mt-2 max-w-2xl text-sm leading-relaxed text-foreground/60">
                Liderii primesc cont complet, membrii primesc link securizat de completare rapidă.
              </p>
            </div>
            <div className="hidden overflow-x-auto xl:block">
              <table className="min-w-[980px] w-full text-left text-sm">
                <thead className="bg-surface-muted text-[11px] font-bold uppercase tracking-[0.15em] text-foreground/50 border-b border-[var(--border)]">
                  <tr>
                    <th className="px-8 py-4">Recipient</th>
                    <th className="px-8 py-4">Acces</th>
                    <th className="px-8 py-4">Sarcini</th>
                    <th className="px-8 py-4">Status livrare</th>
                    <th className="px-8 py-4">Reminder</th>
                    <th className="px-8 py-4">Următorul pas</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {summary.assessmentRows.map((row) => (
                    <tr key={row.id} className="align-top hover:bg-surface-muted transition-colors">
                      <td className="px-8 py-5">
                        <p className="font-bold text-foreground">{row.participant}</p>
                        <p className="mt-1 text-[11px] text-foreground/50 font-mono">{row.email}</p>
                        <p className="mt-1.5 text-xs font-bold text-burgundy">{row.project}</p>
                      </td>
                      <td className="px-8 py-5">
                        <span className="inline-flex items-center rounded-full bg-surface-muted px-3 py-1 text-xs font-bold text-foreground/70 border border-[var(--border)] shadow-sm whitespace-nowrap">
                          {row.audience === "leadership_account" ? "Cont lider" : "Link securizat"}
                        </span>
                      </td>
                      <td className="px-8 py-5 text-foreground/70 font-bold">{row.tasks}</td>
                      <td className="px-8 py-5">
                        <span className={`inline-flex items-center rounded-full px-3 py-1 text-[11px] font-bold border uppercase tracking-wider whitespace-nowrap shadow-sm ${
                          row.delivery === "delivered" || row.delivery === "opened"
                            ? "bg-green-50 border-green-200 text-green-700"
                            : row.delivery === "failed"
                              ? "bg-red-50 border-red-200 text-red-700"
                              : "bg-surface border-[var(--border)] text-foreground/60"
                        }`}>
                          {deliveryLabel(row.delivery)}
                        </span>
                      </td>
                      <td className="px-8 py-5">
                        <span className="inline-flex items-center rounded-full bg-surface px-3 py-1 text-[11px] font-bold text-foreground/60 border border-[var(--border)] shadow-sm uppercase tracking-wider">
                          {reminderLabel(row.reminder)}
                        </span>
                      </td>
                      <td className="px-8 py-5 text-foreground/60 font-semibold max-w-[200px] leading-relaxed">{row.nextAction}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="grid gap-4 p-6 xl:hidden">
              {summary.assessmentRows.map((row) => (
                <article key={row.id} className="rounded-xl border border-[var(--border)] bg-surface p-5 shadow-sm">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                    <div className="min-w-0">
                      <p className="font-bold text-foreground text-lg">{row.participant}</p>
                      <p className="mt-1 break-all text-xs text-foreground/50 font-mono">{row.email}</p>
                      <p className="mt-2 text-xs font-bold text-burgundy uppercase tracking-wider">{row.project}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className="rounded-xl border border-[var(--border)] bg-surface-muted px-3 py-1 text-xs font-bold text-foreground/70 shadow-sm">
                        {row.audience === "leadership_account" ? "Cont lider" : "Link securizat"}
                      </span>
                      <span className={`rounded-full px-3 py-1 text-xs font-bold border uppercase tracking-wider shadow-sm ${
                        row.delivery === "delivered" || row.delivery === "opened"
                          ? "bg-green-50 border-green-200 text-green-700"
                          : row.delivery === "failed"
                            ? "bg-red-50 border-red-200 text-red-700"
                            : "bg-surface border-[var(--border)] text-foreground/60"
                      }`}>
                        {deliveryLabel(row.delivery)}
                      </span>
                    </div>
                  </div>

                  <dl className="mt-5 grid gap-3 sm:grid-cols-3">
                    <div className="rounded-xl bg-surface-muted border border-[var(--border)] px-4 py-3">
                      <dt className="text-[10px] font-bold uppercase tracking-wider text-foreground/50 mb-1">Sarcini</dt>
                      <dd className="text-sm font-bold text-foreground">{row.tasks}</dd>
                    </div>
                    <div className="rounded-xl bg-surface-muted border border-[var(--border)] px-4 py-3">
                      <dt className="text-[10px] font-bold uppercase tracking-wider text-foreground/50 mb-1">Reminder</dt>
                      <dd className="text-sm font-bold text-foreground">{reminderLabel(row.reminder)}</dd>
                    </div>
                    <div className="rounded-xl bg-surface-muted border border-[var(--border)] px-4 py-3 sm:col-span-3">
                      <dt className="text-[10px] font-bold uppercase tracking-wider text-foreground/50 mb-1">Următorul pas</dt>
                      <dd className="text-sm font-semibold leading-relaxed text-foreground/70">{row.nextAction}</dd>
                    </div>
                  </dl>
                </article>
              ))}
            </div>
          </section>

          {/* Quick Actions Panel */}
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_24rem]">
            <section className="surface-panel flex flex-col justify-center p-6 md:p-8">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80 mb-4">Operare globală</p>
              <div className="grid gap-4 md:grid-cols-2">
                <button
                  type="button"
                  disabled={isRefreshing}
                  onClick={refreshSummary}
                  className="btn-secondary min-h-[3rem] w-full"
                >
                  {isRefreshing ? "Se actualizează..." : "Actualizează starea"}
                </button>
              </div>
            </section>

            <section className="surface-panel-muted p-6 md:p-8">
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80 mb-4">Reguli de livrare</p>
              <div className="space-y-3">
                {summary.rules.map((rule) => (
                  <p key={rule} className="rounded-xl bg-surface px-4 py-3 text-xs font-medium leading-relaxed text-foreground/70 border border-[var(--border)] shadow-sm">
                    {rule}
                  </p>
                ))}
              </div>
            </section>
          </div>
        </div>
      )}

      {activeTab === "campaigns" && (
        <div className="space-y-6">
          {/* Campaigns header */}
          <section className="surface-panel flex flex-col justify-between gap-6 p-6 md:flex-row md:items-center md:p-8">
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80">Campanii Promoționale</p>
              <h2 className="mt-2 font-display text-2xl font-bold text-foreground">Emailuri video personalizate</h2>
              <p className="mt-3 max-w-2xl text-sm leading-relaxed text-foreground/60">
                Aici poți încărca liste Excel/CSV cu contacte, pregăti campanii video și trimite către contactele active din segmentul ales.
              </p>
            </div>
            
            <div className="flex shrink-0 flex-wrap gap-3">
              <button
                type="button"
                className="btn-premium"
                onClick={openCreateCampaignModal}
              >
                Creează campanie
              </button>
              <label className="btn-premium cursor-pointer inline-flex items-center gap-2">
                {isUploadingCSV ? (
                  <span>Se încarcă...</span>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" /></svg>
                    Importă contacte
                  </>
                )}
                <input 
                  type="file" 
                  accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet, application/vnd.ms-excel" 
                  className="hidden" 
                  onChange={handleFileUpload}
                  disabled={isUploadingCSV}
                />
              </label>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => setShowManualAddModal(true)}
              >
                + Adaugă contact
              </button>
            </div>
          </section>

          <section className="surface-panel overflow-hidden">
            <div className="border-b border-[var(--border)] px-8 py-6 bg-surface-muted flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80">Operațiuni campanii</p>
                <h2 className="mt-2 text-xl font-bold text-foreground">Contacte și istoric</h2>
              </div>
              <div className="flex rounded-full border border-[var(--border)] bg-surface p-1 shadow-sm">
                <button
                  type="button"
                  onClick={() => setCampaignView("contacts")}
                  className={`rounded-full px-4 py-2 text-xs font-bold transition ${campaignView === "contacts" ? "bg-burgundy text-white" : "text-foreground/62 hover:text-burgundy"}`}
                >
                  Contacte
                </button>
                <button
                  type="button"
                  onClick={() => setCampaignView("campaigns")}
                  className={`rounded-full px-4 py-2 text-xs font-bold transition ${campaignView === "campaigns" ? "bg-burgundy text-white" : "text-foreground/62 hover:text-burgundy"}`}
                >
                  Campanii
                </button>
              </div>
            </div>
            {campaignMessage ? (
              <p aria-live="polite" className="mx-6 mt-4 rounded-xl bg-surface-muted px-3 py-2 text-xs font-semibold text-foreground/62">
                {campaignMessage}
              </p>
            ) : null}
            {campaignView === "campaigns" ? (
              <div className="p-6">
                <div className="grid gap-3 lg:grid-cols-2">
                  {isLoadingCampaigns ? (
                    <p className="text-xs font-medium text-foreground/50">Se încarcă...</p>
                  ) : campaigns.length === 0 ? (
                    <p className="rounded-xl border border-[var(--border)] bg-surface-muted px-4 py-6 text-sm font-semibold text-foreground/55">Nicio campanie salvată încă.</p>
                  ) : (
                    campaigns.map((campaign) => (
                        <article key={campaign.id} className="rounded-xl border border-[var(--border)] bg-surface-muted px-4 py-4">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="truncate text-sm font-bold text-foreground">{campaign.name}</p>
                              <p className="mt-1 text-[10px] font-semibold uppercase tracking-wider text-foreground/45">{campaign.status}</p>
                              <p className="mt-2 text-xs font-semibold text-foreground/55">
                                {campaign.segment === "past_customer" ? "Client existent" : "Prospect"} · {campaign.subject}
                              </p>
                            </div>
                            <div className="flex shrink-0 flex-wrap justify-end gap-2">
                              <button
                                type="button"
                                disabled={sendingCampaignId === campaign.id || deletingCampaignId === campaign.id}
                                onClick={() => openEditCampaignModal(campaign)}
                                className="btn-secondary px-3 py-1.5 text-[10px]"
                              >
                                Editează
                              </button>
                              <button
                                type="button"
                                disabled={sendingCampaignId === campaign.id || deletingCampaignId === campaign.id || activeSelectedCampaignRecipientIds.length === 0}
                                onClick={() => handleSendCampaign(campaign, "selected")}
                                className="btn-secondary px-3 py-1.5 text-[10px]"
                              >
                                Trimite selectați ({activeSelectedCampaignRecipientIds.length})
                              </button>
                              <button
                                type="button"
                                disabled={sendingCampaignId === campaign.id || deletingCampaignId === campaign.id}
                                onClick={() => handleSendCampaign(campaign, "new")}
                                className="btn-secondary px-3 py-1.5 text-[10px]"
                              >
                                {sendingCampaignId === campaign.id ? "Se trimite..." : "Trimite netrimișilor"}
                              </button>
                              <button
                                type="button"
                                disabled={sendingCampaignId === campaign.id || deletingCampaignId === campaign.id}
                                onClick={() => handleSendCampaign(campaign, "all")}
                                className="btn-secondary px-3 py-1.5 text-[10px]"
                              >
                                Trimite tuturor
                              </button>
                              <button
                                type="button"
                                disabled={sendingCampaignId === campaign.id || deletingCampaignId === campaign.id}
                                onClick={() => handleDeleteCampaign(campaign)}
                                className="rounded-full border border-red-500/35 bg-red-500/10 px-3 py-1.5 text-[10px] font-bold text-red-700 transition hover:-translate-y-0.5 hover:border-red-500/55 hover:bg-red-500/15 disabled:cursor-not-allowed disabled:opacity-60 dark:text-red-200"
                              >
                                {deletingCampaignId === campaign.id ? "Se șterge..." : "Șterge"}
                              </button>
                            </div>
                          </div>
                          {campaignSendResults[campaign.id] ? (
                            <p className="mt-2 rounded-xl bg-surface px-3 py-2 text-[11px] font-semibold text-foreground/60">
                              {campaignSendResults[campaign.id].sent} trimise · {campaignSendResults[campaign.id].failed} eșuate · {campaignSendResults[campaign.id].skipped} omise
                            </p>
                          ) : null}
                        </article>
                    ))
                  )}
                </div>
              </div>
            ) : (
              <div className="overflow-x-auto p-2">
                {campaignContactMessage ? (
                  <p aria-live="polite" className="mx-4 mt-4 rounded-xl border border-[var(--border)] bg-surface-muted px-4 py-3 text-xs font-semibold text-foreground/65">
                    {campaignContactMessage}
                  </p>
                ) : null}
                <table className="min-w-full text-left text-sm">
                  <thead className="text-[10px] font-bold uppercase tracking-[0.15em] text-foreground/50 border-b border-[var(--border)]">
                    <tr>
                      <th className="px-6 py-4">Select</th>
                      <th className="px-6 py-4">Companie & Contact</th>
                      <th className="px-6 py-4">Tip client</th>
                      <th className="px-6 py-4">Status</th>
                      <th className="px-6 py-4">Evenimente</th>
                      <th className="px-6 py-4">Reply / Calendly</th>
                      <th className="px-6 py-4">Rezultat</th>
                      <th className="px-6 py-4 text-right">Acțiuni</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)]">
                    {summary.campaign.recipients.length > 0 ? (
                      summary.campaign.recipients.map((recipient) => {
                        const isEditingContact = editingContactId === recipient.id;
                        const draft = contactDrafts[recipient.id] ?? campaignRecipientDraft(recipient);
                        return (
                          <tr key={recipient.id} className={`transition-colors hover:bg-surface-muted ${recipient.status === "suppressed" ? "bg-surface-muted/50 text-foreground/55" : ""}`}>
                            <td className="px-6 py-4">
                              <input
                                type="checkbox"
                                checked={activeCampaignRecipientIdSet.has(recipient.id) && selectedCampaignRecipientIds.includes(recipient.id)}
                                disabled={!activeCampaignRecipientIdSet.has(recipient.id)}
                                onChange={() => toggleSelectedCampaignRecipient(recipient.id)}
                                className="h-4 w-4 accent-burgundy disabled:opacity-40"
                                aria-label={`Selectează ${recipient.email}`}
                              />
                            </td>
                            <td className="min-w-[17rem] px-6 py-4">
                              {isEditingContact ? (
                                <div className="space-y-2">
                                  <input
                                    value={draft.organization_name}
                                    onChange={(event) => updateContactDraft(recipient.id, "organization_name", event.target.value)}
                                    className="control-input w-full px-3 py-2 text-xs"
                                    placeholder="Companie"
                                  />
                                  <input
                                    value={draft.contact_name}
                                    onChange={(event) => updateContactDraft(recipient.id, "contact_name", event.target.value)}
                                    className="control-input w-full px-3 py-2 text-xs"
                                    placeholder="Nume contact"
                                  />
                                  <input
                                    type="email"
                                    value={draft.email}
                                    onChange={(event) => updateContactDraft(recipient.id, "email", event.target.value)}
                                    className="control-input w-full px-3 py-2 font-mono text-xs"
                                    placeholder="email@companie.ro"
                                  />
                                </div>
                              ) : (
                                <>
                                  <p className="font-bold text-foreground">{recipient.company}</p>
                                  <p className="mt-1 text-xs font-medium text-foreground/60">
                                    {campaignRecipientName(recipient) || "Contact lipsă"}
                                  </p>
                                  <p className="mt-1 text-[11px] text-foreground/40 font-mono">{recipient.email}</p>
                                </>
                              )}
                            </td>
                            <td className="min-w-[11rem] px-6 py-4">
                              {isEditingContact ? (
                                <div className="space-y-2">
                                  <select
                                    value={draft.segment}
                                    onChange={(event) => updateContactDraft(recipient.id, "segment", event.target.value as CampaignContactDraft["segment"])}
                                    className="control-input w-full px-3 py-2 text-xs"
                                  >
                                    <option value="potential_customer">Prospect</option>
                                    <option value="past_customer">Client existent</option>
                                  </select>
                                  <select
                                    value={draft.status}
                                    onChange={(event) => updateContactDraft(recipient.id, "status", event.target.value as CampaignContactDraft["status"])}
                                    className="control-input w-full px-3 py-2 text-xs"
                                  >
                                    <option value="active">Da - activ în campanii</option>
                                    <option value="suppressed">Nu - inactiv</option>
                                  </select>
                                </div>
                              ) : (
                                <span className="capitalize text-[11px] font-bold uppercase tracking-wider text-foreground/60">
                                  {recipient.clientType === "tip_1" ? "Client existent" : "Prospect"}
                                </span>
                              )}
                            </td>
                            <td className="px-6 py-4">
                              <span className="rounded-full bg-surface px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-foreground/70 border border-[var(--border)] shadow-sm">
                                {recipient.status}
                              </span>
                            </td>
                            <td className="px-6 py-4 text-foreground/70 font-mono text-xs">
                              {recipient.openCount ?? 0} desch. / {recipient.clickCount ?? 0} click / {recipient.viewCount ?? 0} video
                              {recipient.emailVariant ? (
                                <span className="mt-1 block font-sans text-[10px] font-bold uppercase tracking-wider text-burgundy/70">
                                  variantă {recipient.emailVariant}
                                </span>
                              ) : null}
                            </td>
                            <td className="px-6 py-4 text-foreground/70 font-mono text-xs">
                              {recipient.replyCount ?? 0} / {recipient.calendlyClickCount ?? 0}
                            </td>
                            <td className="px-6 py-4">
                              <span className="rounded-full bg-burgundy/10 border border-burgundy/20 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-burgundy shadow-sm">
                                {recipient.outcome ?? "pending"}
                              </span>
                            </td>
                            <td className="px-6 py-4">
                              <div className="flex justify-end gap-2">
                                {isEditingContact ? (
                                  <>
                                    <button
                                      type="button"
                                      disabled={savingContactId === recipient.id}
                                      onClick={() => saveContact(recipient)}
                                      className="btn-secondary px-3 py-1.5 text-[10px]"
                                    >
                                      {savingContactId === recipient.id ? "Se salvează..." : "Salvează"}
                                    </button>
                                    <button
                                      type="button"
                                      disabled={savingContactId === recipient.id}
                                      onClick={() => cancelEditingContact(recipient.id)}
                                      className="rounded-full border border-[var(--border)] bg-surface px-3 py-1.5 text-[10px] font-bold text-foreground/60"
                                    >
                                      Anulează
                                    </button>
                                  </>
                                ) : (
                                  <>
                                    <button
                                      type="button"
                                      onClick={() => startEditingContact(recipient)}
                                      className="btn-secondary px-3 py-1.5 text-[10px]"
                                    >
                                      Editează
                                    </button>
                                    <button
                                      type="button"
                                      disabled={deletingContactId === recipient.id}
                                      onClick={() => deleteContact(recipient)}
                                      className="rounded-full border border-red-500/35 bg-red-500/10 px-3 py-1.5 text-[10px] font-bold text-red-700 dark:text-red-200"
                                    >
                                      {deletingContactId === recipient.id ? "Se șterge..." : "Șterge"}
                                    </button>
                                  </>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td colSpan={8} className="px-6 py-12 text-center text-foreground/50 text-sm font-medium">
                          <p>Niciun contact înregistrat încă.</p>
                          <div className="mt-4 flex items-center justify-center gap-3">
                            <span className="text-foreground/40">Importă un fișier CSV sau</span>
                            <button onClick={() => setShowManualAddModal(true)} className="tap-soft rounded-full border border-[var(--border)] bg-surface px-3 py-1.5 text-xs font-bold text-burgundy hover:border-burgundy/45 hover:text-burgundy-dark">adaugă manual</button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>
      )}

      {activeTab === "templates" && (
        <div className="space-y-6">
          {!selectedTemplateId ? (
            <div className="space-y-6">
              {/* Action Bar */}
              <div className="filter-toolbar">
                <div className="relative w-full md:flex-1">
                  <svg className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-foreground/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 1 1-14 0 7 7 0 0 1 14 0z" />
                  </svg>
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Caută șabloane..."
                    className="control-input control-search w-full py-3 pl-12 pr-4"
                  />
                </div>
                <button
                  onClick={handleCreateTemplate}
                  disabled={isLoadingTemplates}
                  className="btn-primary shrink-0"
                >
                  + Creează șablon
                </button>
              </div>

              {/* Grid */}
              {isLoadingTemplates && templates.length === 0 ? (
                <div className="surface-panel flex h-64 items-center justify-center">
                  <p className="text-sm font-bold text-foreground/50">Se încarcă șabloanele...</p>
                </div>
              ) : filteredTemplates.length > 0 ? (
                <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-3">
                  {filteredTemplates.map((temp) => (
                    <article
                      key={temp.id}
                      role="button"
                      tabIndex={0}
                      onClick={() => {
                        setSelectedTemplateId(temp.id);
                        setIsEditing(false);
                      }}
                      onKeyDown={(event) => {
                        if (event.key !== "Enter" && event.key !== " ") return;
                        event.preventDefault();
                        setSelectedTemplateId(temp.id);
                        setIsEditing(false);
                      }}
                      className="group relative flex h-full min-h-[220px] flex-col overflow-hidden rounded-xl border border-[var(--border)] bg-surface p-6 text-left shadow-sm outline-none transition-colors hover:border-burgundy/25 focus:ring-2 focus:ring-burgundy/30"
                    >
                      <div className="flex h-full w-full flex-col">
                        <div className="flex items-start justify-between mb-4">
                          <span className={`rounded-full border px-3 py-1 text-[10px] font-bold uppercase tracking-[0.2em] ${
                            temp.lane === "transactional"
                              ? "bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:border-emerald-800/50"
                              : "bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-900/30 dark:text-purple-300 dark:border-purple-800/50"
                          }`}>
                            {temp.lane === "transactional" ? "Sistem" : "Campanie"}
                          </span>
                          <span className="rounded-xl border border-[var(--border)] bg-surface-muted px-3 py-1 text-[10px] font-bold text-foreground/60">
                            v{temp.version ?? 1}
                          </span>
                        </div>
                        <h4 className="font-display font-bold text-xl text-foreground mb-2 group-hover:text-burgundy transition-colors line-clamp-1">
                          {temp.name}
                        </h4>
                        <p className="text-sm font-medium leading-relaxed text-foreground/60 mb-4 line-clamp-2 min-h-[2.5rem]">
                          {temp.subject || "Fără subiect"}
                        </p>
                        
                        <div className="mt-auto pt-4 border-t border-[var(--border)] flex items-center justify-between">
                          <div className="flex flex-wrap gap-1.5">
                            {temp.placeholders.slice(0, 3).map((p, i) => (
                              <div key={i} className="inline-block rounded-full bg-surface-muted px-2 py-1 text-[10px] font-mono font-bold text-foreground/60 border border-[var(--border)] shadow-sm">
                                {p.replace('{', '').replace('}', '')}
                              </div>
                            ))}
                            {temp.placeholders.length > 3 && (
                              <div className="inline-flex items-center justify-center rounded-full bg-surface-muted px-2 py-1 text-[10px] font-bold text-foreground/60 border border-[var(--border)] shadow-sm">
                                +{temp.placeholders.length - 3}
                              </div>
                            )}
                          </div>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              ) : (
                <div className="flex h-64 flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border)] bg-surface-muted p-6 text-center">
                  <div className="w-16 h-16 rounded-xl bg-surface flex items-center justify-center mb-4 text-foreground/30 shadow-sm">
                    <svg className="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
                  </div>
                  <p className="text-lg font-display font-bold text-foreground mb-1">Niciun șablon găsit</p>
                  <p className="text-sm font-medium text-foreground/50">Modifică termenii de căutare sau creează un șablon nou.</p>
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-6">
              {/* Back to catalog button */}
              <div>
                <button
                  onClick={() => setSelectedTemplateId("")}
                  className="tap-soft inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-surface px-4 py-2 text-sm font-bold text-foreground/60 shadow-sm transition-colors hover:text-foreground"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" /></svg>
                  Înapoi la catalog
                </button>
              </div>

              {/* Editor View */}
              {selectedTemplate && (
                <main className="grid gap-6 xl:grid-cols-2">
              {/* Editor Column */}
              <section className="surface-panel flex flex-col p-6">
                <div className="flex flex-wrap items-center justify-between gap-4 border-b border-[var(--border)] pb-4 mb-5">
                  <div>
                    <h3 className="text-xl font-bold text-foreground">
                      {isEditing ? "Modificare șablon" : "Detalii șablon"}
                    </h3>
                    <p className="mt-1 text-[10px] font-bold uppercase tracking-[0.15em] text-foreground/50">
                      Versiunea {selectedTemplate.version ?? 1}
                    </p>
                  </div>
                  
                  <div className="flex flex-wrap justify-end gap-2">
                    {isEditing ? (
                      <>
                        <button
                          onClick={handleSaveTemplate}
                          disabled={isLoadingTemplates}
                          className="btn-premium py-1.5 px-4 text-xs"
                        >
                          Salvează
                        </button>
                        <button
                          onClick={() => setIsEditing(false)}
                          disabled={isLoadingTemplates}
                          className="btn-secondary py-1.5 px-4 text-xs"
                        >
                          Anulează
                        </button>
                      </>
                    ) : (
                      <>
                        <button
                          onClick={() => setIsEditing(true)}
                          disabled={isLoadingTemplates}
                          className="tap-soft rounded-full bg-burgundy/10 border border-burgundy/20 px-4 py-2 text-xs font-bold text-burgundy hover:bg-burgundy/20 transition-colors"
                        >
                          Editează
                        </button>
                        <button
                          onClick={handleCreateTemplateVersion}
                          disabled={isLoadingTemplates}
                          className="tap-soft rounded-full border border-[var(--border)] bg-surface px-4 py-2 text-xs font-bold text-foreground/70 hover:border-burgundy/40 hover:text-burgundy transition-all shadow-sm"
                        >
                          Versiune nouă
                        </button>
                        <button
                          onClick={handleDeleteTemplate}
                          disabled={isLoadingTemplates}
                          className="tap-soft rounded-full border border-red-200 bg-red-50 px-4 py-2 text-xs font-bold text-red-600 hover:bg-red-100 transition-colors shadow-sm"
                        >
                          Șterge
                        </button>
                      </>
                    )}
                  </div>
                </div>

                <div className="space-y-5 flex-1 flex flex-col">
                  <label className="block">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-2 block">Nume intern</span>
                    <input
                      type="text"
                      disabled={!isEditing}
                      value={isEditing ? editName : selectedTemplate.name}
                      onChange={(e) => setEditName(e.target.value)}
                      className="control-input w-full py-3 disabled:opacity-60"
                    />
                  </label>

                  <div className="grid gap-5 grid-cols-2">
                    <label className="block">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-2 block">Canal trimitere</span>
                      <select
                        disabled={!isEditing}
                        value={isEditing ? editLane : selectedTemplate.lane}
                        onChange={(e) => setEditLane(e.target.value as "transactional" | "campaign")}
                        className="control-input w-full appearance-none py-3 disabled:opacity-60"
                      >
                        <option value="transactional">Tranzacțional (Sistem)</option>
                        <option value="campaign">Campanie (Prospectare)</option>
                      </select>
                    </label>

                    <div className="block">
                      <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-2 block">Tag-uri active</span>
                      <div className="flex flex-wrap gap-2 min-h-[3rem] items-center p-2 rounded-xl border border-[var(--border)] bg-surface-muted">
                        {selectedTemplate.placeholders.length > 0 ? (
                          selectedTemplate.placeholders.map((p) => (
                            <span
                              key={p}
                              className="inline-flex items-center rounded-full bg-foreground/5 border border-foreground/10 px-2 py-1 text-[10px] font-bold text-foreground/70 font-mono"
                            >
                              {p}
                            </span>
                          ))
                        ) : (
                          <span className="text-xs text-foreground/40 px-2 font-medium">Niciun tag</span>
                        )}
                      </div>
                    </div>
                  </div>

                  <label className="block">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-2 block">Subiect email</span>
                    <input
                      type="text"
                      disabled={!isEditing}
                      value={isEditing ? editSubject : selectedTemplate.subject}
                      onChange={(e) => setEditSubject(e.target.value)}
                      className="control-input w-full py-3 disabled:opacity-60"
                    />
                  </label>

                  <label className="block flex-1 flex flex-col">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-2 block">Corp email (Markdown)</span>
                    <textarea
                      disabled={!isEditing}
                      value={isEditing ? editBody : selectedTemplate.body}
                      onChange={(e) => setEditBody(e.target.value)}
                      className="control-input min-h-[200px] w-full flex-1 resize-none py-4 font-mono leading-relaxed disabled:opacity-60"
                    />
                  </label>
                </div>
              </section>

              {/* Preview Column */}
              <section className="surface-panel flex flex-col p-6">
                <div className="flex items-center gap-3 border-b border-[var(--border)] pb-4 mb-5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-burgundy/10 text-burgundy">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                  </div>
                  <h3 className="text-sm font-bold uppercase tracking-wider text-foreground/80">
                    Previzualizare Live
                  </h3>
                </div>

                <div className="rounded-xl border border-[var(--border)] bg-surface overflow-hidden shadow-sm flex-1 flex flex-col">
                  {/* Simulated Mailbox Header */}
                  <div className="bg-surface-muted p-5 border-b border-[var(--border)] space-y-2 text-xs text-foreground/60">
                    <div className="flex justify-between items-center">
                      <p><strong className="text-foreground/80">De la:</strong> Echipa Codruț</p>
                      <span className="text-[10px] font-mono opacity-50">10:42 AM</span>
                    </div>
                    <p><strong className="text-foreground/80">Către:</strong> {MOCK_REPLACEMENTS["{first_name}"]}</p>
                    <p className="text-sm text-foreground font-bold pt-1">{preview.subject}</p>
                  </div>

                  {/* Rendered HTML Body */}
                  <div
                    className="flex-1 bg-surface p-6 font-sans text-[15px] leading-relaxed text-foreground"
                    dangerouslySetInnerHTML={{ __html: preview.bodyHtml }}
                  />
                </div>

                <div className="mt-5 rounded-xl bg-surface-muted p-4 border border-[var(--border)]">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 text-burgundy/60">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    </div>
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-1">Informație utilă</p>
                      <p className="text-[11px] text-foreground/60 leading-relaxed font-medium">
                        Tag-urile ca <code className="bg-foreground/5 px-1 rounded mx-0.5">{`{first_name}`}</code> sunt înlocuite automat la expediere. Puteți formata corpul emailului folosind <strong className="text-foreground">**text**</strong> pentru bold și <span className="text-burgundy underline">[linkuri](url)</span>.
                      </p>
                    </div>
                  </div>
                </div>
              </section>
                </main>
              )}
            </div>
          )}
        </div>
      )}

      {/* New Campaign Modal */}
      {showCampaignModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
          <div className="max-h-[92vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-[var(--border)] bg-surface p-6 shadow-2xl">
            <div className="mb-5 flex items-start justify-between gap-4 border-b border-[var(--border)] pb-4">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80">
                  {editingCampaign ? "Editează campanie" : "Campanie nouă"}
                </p>
                <h2 className="mt-2 text-xl font-bold text-foreground">Email video cu thumbnail</h2>
                <p className="mt-2 text-xs font-medium leading-relaxed text-foreground/55">
                  Linkul video poate fi Vimeo. Landing page-ul Codruț este opțional și se folosește doar când vrei tracking sau CTA-uri dedicate.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setShowCampaignModal(false)}
                className="rounded-full border border-[var(--border)] bg-surface-muted px-3 py-1.5 text-xs font-bold text-foreground/60"
              >
                Închide
              </button>
            </div>

            <form onSubmit={handleSaveCampaign} className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <label className="block">
                  <span className="mb-1 block text-xs font-bold uppercase tracking-wider text-foreground/60">Nume campanie</span>
                  <input
                    value={campaignName}
                    onChange={(event) => setCampaignName(event.target.value)}
                    className="control-input w-full py-3"
                  />
                </label>
                <label className="block">
                  <span className="mb-1 block text-xs font-bold uppercase tracking-wider text-foreground/60">Segment</span>
                  <select
                    value={campaignSegment}
                    onChange={(event) => {
                      setCampaignSegment(event.target.value as "past_customer" | "potential_customer");
                      setCampaignTemplateId("");
                    }}
                    className="control-input w-full py-3"
                  >
                    <option value="potential_customer">Prospect / client potențial</option>
                    <option value="past_customer">Client vechi / existent</option>
                  </select>
                </label>
              </div>

              <label className="block">
                <span className="mb-1 block text-xs font-bold uppercase tracking-wider text-foreground/60">Șablon email</span>
                <select
                  value={campaignTemplateId}
                  onChange={(event) => {
                    const nextTemplate = campaignTemplates.find((template) => template.id === event.target.value);
                    setCampaignTemplateId(event.target.value);
                    if (nextTemplate) {
                      setCampaignSubject(nextTemplate.subject);
                      setCampaignBody(nextTemplate.body);
                      setCampaignTextBody(nextTemplate.body.replace(/<[^>]*>/g, ""));
                    }
                  }}
                  className="control-input w-full py-3"
                >
                  <option value="">Alege șablonul pentru segment</option>
                  {campaignTemplates.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="block">
                <span className="mb-1 block text-xs font-bold uppercase tracking-wider text-foreground/60">Subiect</span>
                <input
                  value={campaignSubject}
                  onChange={(event) => setCampaignSubject(event.target.value)}
                  className="control-input w-full py-3"
                />
              </label>

              <label className="block">
                <span className="mb-1 block text-xs font-bold uppercase tracking-wider text-foreground/60">Corp email</span>
                <textarea
                  value={campaignBody}
                  onChange={(event) => {
                    setCampaignBody(event.target.value);
                    setCampaignTextBody(event.target.value.replace(/<[^>]*>/g, ""));
                  }}
                  rows={7}
                  placeholder="Alege un șablon sau scrie corpul emailului."
                  className="control-input w-full resize-y py-3 font-mono text-xs leading-relaxed"
                />
              </label>

              <label className="block">
                <span className="mb-1 block text-xs font-bold uppercase tracking-wider text-foreground/60">Link video</span>
                <input
                  type="url"
                  value={campaignVideoUrl}
                  onChange={(event) => setCampaignVideoUrl(event.target.value)}
                  placeholder="https://vimeo.com/..."
                  className="control-input w-full py-3"
                />
              </label>

              <div className="rounded-xl border border-[var(--border)] bg-surface-muted p-4">
                <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                  <div>
                    <span className="block text-xs font-bold uppercase tracking-wider text-foreground/60">Thumbnail</span>
                    <p className="mt-1 text-[11px] font-medium text-foreground/50">Încarcă imagine/GIF sau lipește un URL existent.</p>
                  </div>
                  <label className="btn-secondary inline-flex cursor-pointer items-center justify-center px-4 py-2 text-xs">
                    {isUploadingCampaignAsset ? "Se încarcă..." : "Încarcă fișier"}
                    <input
                      type="file"
                      accept="image/jpeg,image/png,image/webp,image/gif"
                      className="hidden"
                      disabled={isUploadingCampaignAsset}
                      onChange={handleCampaignAssetUpload}
                    />
                  </label>
                </div>
                <input
                  type="url"
                  value={campaignThumbnailUrl}
                  onChange={(event) => setCampaignThumbnailUrl(event.target.value)}
                  placeholder="https://codrut.andreivacaru.ro/api/campaign-assets/thumbnail.jpg"
                  className="control-input w-full py-3"
                />
                {campaignThumbnailUrl ? (
                  <div className="relative mt-3 max-w-md overflow-hidden rounded-xl border border-[var(--border)] bg-surface">
                    <Image
                      src={campaignThumbnailUrl}
                      alt="Previzualizare thumbnail campanie"
                      width={640}
                      height={320}
                      unoptimized
                      className="h-28 w-full object-cover"
                    />
                    <div
                      aria-hidden="true"
                      className="absolute inset-0 flex items-center justify-center bg-black/10"
                    >
                      <span className="flex h-14 w-14 items-center justify-center rounded-full border border-white/65 bg-white/86 shadow-xl backdrop-blur-sm">
                        <span className="ml-1 block h-0 w-0 border-y-[9px] border-l-[14px] border-y-transparent border-l-burgundy" />
                      </span>
                    </div>
                  </div>
                ) : null}
                {campaignAssetMessage ? (
                  <p className="mt-2 text-xs font-semibold text-foreground/62">{campaignAssetMessage}</p>
                ) : null}
              </div>

              <label className="block">
                <span className="mb-1 block text-xs font-bold uppercase tracking-wider text-foreground/60">Landing page Codruț (opțional)</span>
                <input
                  type="url"
                  value={campaignLandingUrl}
                  onChange={(event) => setCampaignLandingUrl(event.target.value)}
                  placeholder="Lasă gol ca butonul să ducă direct la Vimeo"
                  className="control-input w-full py-3"
                />
              </label>

              <div className="rounded-xl border border-[var(--border)] bg-surface-muted p-4">
                <p className="text-[10px] font-bold uppercase tracking-wider text-foreground/60">Preview email campanie</p>
                <div className="mt-3 overflow-hidden rounded-xl border border-[var(--border)] bg-surface">
                  <div className="border-b border-[var(--border)] bg-surface-muted px-4 py-3">
                    <p className="text-[11px] font-semibold text-foreground/50">Către: {MOCK_REPLACEMENTS["{first_name}"]}</p>
                    <p className="mt-1 text-sm font-bold text-foreground">{campaignPreview.subject}</p>
                  </div>
                  <div
                    className="max-h-72 overflow-y-auto p-4 text-sm leading-relaxed text-foreground"
                    dangerouslySetInnerHTML={{ __html: campaignPreview.bodyHtml }}
                  />
                </div>
              </div>

              {campaignMessage ? (
                <p aria-live="polite" className="rounded-xl bg-surface-muted px-3 py-2 text-xs font-semibold text-foreground/62">
                  {campaignMessage}
                </p>
              ) : null}

              <div className="flex justify-end gap-3 border-t border-[var(--border)] pt-4">
                <button
                  type="button"
                  onClick={() => setShowCampaignModal(false)}
                  className="rounded-full px-4 py-2 font-bold text-foreground/60 hover:bg-surface-muted"
                >
                  Anulează
                </button>
                <button type="submit" disabled={isCreatingCampaign} className="btn-primary !rounded-full !px-6 !py-2 !text-sm">
                  {isCreatingCampaign ? "Se salvează..." : editingCampaign ? "Salvează modificările" : "Salvează campania"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {importDrafts.length > 0 && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4 backdrop-blur-sm">
          <div className="flex max-h-[88vh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-2xl">
            <div className="border-b border-[var(--border)] bg-surface-muted px-6 py-4">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80">Import contacte</p>
                  <h2 className="mt-1 text-xl font-bold text-foreground">Previzualizare {importSheetName ?? "sheet"}</h2>
                  <p className="mt-1 text-xs font-semibold text-foreground/55">
                    {importDrafts.length} contacte · {activeImportDraftCount} active · {importDrafts.length - activeImportDraftCount} inactive · {invalidImportDraftCount} emailuri de corectat
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    disabled={isImportingContacts}
                    onClick={() => {
                      setImportDrafts([]);
                      setImportSheetName(null);
                    }}
                    className="rounded-full border border-[var(--border)] bg-surface px-4 py-2 text-xs font-bold text-foreground/60"
                  >
                    Anulează
                  </button>
                  <button
                    type="button"
                    disabled={isImportingContacts || invalidImportDraftCount > 0}
                    onClick={confirmCampaignRecipientImport}
                    className="btn-primary !rounded-full !px-5 !py-2 !text-xs disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isImportingContacts ? "Se importă..." : "Confirmă importul"}
                  </button>
                </div>
              </div>
            </div>
            <div className="overflow-auto p-4">
              <table className="min-w-[1040px] w-full text-left text-xs">
                <thead className="sticky top-0 z-10 bg-surface text-[10px] font-bold uppercase tracking-[0.14em] text-foreground/50">
                  <tr>
                    <th className="px-3 py-2">Trimite</th>
                    <th className="px-3 py-2">Nume</th>
                    <th className="px-3 py-2">Organizație</th>
                    <th className="px-3 py-2">Email</th>
                    <th className="px-3 py-2">Tip client</th>
                    <th className="px-3 py-2">Rând</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {importDrafts.map((draft) => {
                    const invalidEmail = !isValidImportEmail(draft.email.trim());
                    return (
                      <tr key={draft.id} className={draft.send ? "bg-surface" : "bg-surface-muted/70 text-foreground/50"}>
                        <td className="px-3 py-2">
                          <button
                            type="button"
                            onClick={() => updateImportDraft(draft.id, "send", !draft.send)}
                            className={`rounded-full px-3 py-1 text-[10px] font-bold ${draft.send ? "bg-green-100 text-green-800" : "bg-surface border border-[var(--border)] text-foreground/50"}`}
                          >
                            {draft.send ? "Da" : "Nu"}
                          </button>
                        </td>
                        <td className="px-3 py-2">
                          <input
                            value={draft.contact_name}
                            onChange={(event) => updateImportDraft(draft.id, "contact_name", event.target.value)}
                            className="control-input w-full min-w-[13rem] px-2 py-1 text-xs"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            value={draft.organization_name}
                            onChange={(event) => updateImportDraft(draft.id, "organization_name", event.target.value)}
                            className="control-input w-full min-w-[13rem] px-2 py-1 text-xs"
                          />
                        </td>
                        <td className="px-3 py-2">
                          <input
                            type="email"
                            value={draft.email}
                            onChange={(event) => updateImportDraft(draft.id, "email", event.target.value)}
                            className={`control-input w-full min-w-[16rem] px-2 py-1 font-mono text-xs ${invalidEmail ? "border-red-400 bg-red-50 text-red-800" : ""}`}
                          />
                        </td>
                        <td className="px-3 py-2">
                          <select
                            value={draft.segment}
                            onChange={(event) => updateImportDraft(draft.id, "segment", event.target.value as CampaignImportDraft["segment"])}
                            className="control-input w-full min-w-[10rem] px-2 py-1 text-xs"
                          >
                            <option value="potential_customer">Prospect</option>
                            <option value="past_customer">Client existent</option>
                          </select>
                        </td>
                        <td className="px-3 py-2 font-mono text-[11px] text-foreground/45">
                          {draft.rowNumber}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Manual Add Contact Modal */}
      {showManualAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/45 backdrop-blur-sm">
          <div className="bg-surface rounded-xl p-6 shadow-xl w-full max-w-md border border-[var(--border)]">
            <h2 className="text-xl font-bold text-foreground mb-4">Adaugă Contact Manual</h2>
            <form onSubmit={handleAddManualContact} className="space-y-4">
              <label className="block">
                <span className="text-xs font-bold uppercase tracking-wider text-foreground/60 mb-1 block">Email</span>
                <input type="email" required value={manualEmail} onChange={e => setManualEmail(e.target.value)} className="control-input w-full py-3" placeholder="exemplu@companie.ro" />
              </label>
              <label className="block">
                <span className="text-xs font-bold uppercase tracking-wider text-foreground/60 mb-1 block">Nume (Opțional)</span>
                <input type="text" value={manualName} onChange={e => setManualName(e.target.value)} className="control-input w-full py-3" placeholder="Nume și prenume" />
              </label>
              <label className="block">
                <span className="text-xs font-bold uppercase tracking-wider text-foreground/60 mb-1 block">Companie (Opțional)</span>
                <input type="text" value={manualCompany} onChange={e => setManualCompany(e.target.value)} className="control-input w-full py-3" placeholder="Numele companiei" />
              </label>
              <label className="block">
                <span className="text-xs font-bold uppercase tracking-wider text-foreground/60 mb-1 block">Segment</span>
                <select value={manualSegment} onChange={e => setManualSegment(e.target.value as "past_customer" | "potential_customer")} className="control-input w-full py-3">
                  <option value="potential_customer">Prospect / Client Potențial</option>
                  <option value="past_customer">Client Existent / Vechi</option>
                </select>
              </label>
              <div className="pt-4 flex justify-end gap-3 border-t border-[var(--border)]">
                <button type="button" onClick={() => setShowManualAddModal(false)} className="rounded-full px-4 py-2 font-bold text-foreground/60 hover:bg-surface-muted">Anulează</button>
                <button type="submit" disabled={isAddingManual} className="btn-primary !px-6 !py-2 !rounded-full !text-sm">
                  {isAddingManual ? "Se adaugă..." : "Adaugă contact"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
