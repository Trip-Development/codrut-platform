"use client";

import Image from "next/image";
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
  htmlToPlainText,
  listCampaignRecipientMembershipOnServer,
  listCampaignsOnServer,
  replaceCampaignRecipientMembershipOnServer,
  sendCampaignOnServer,
  updateCampaignOnServer,
  updateCampaignRecipientOnServer,
  uploadCampaignAssetOnServer,
  type EmailOpsSummary,
  type CampaignRecipientRow,
  type CampaignRecipientCreate,
  type CampaignSendResponse,
  type EmailCampaign,
  type EmailTemplate
} from "@/api/email";
import { ModalLayer } from "@/components/ui/modal-layer";
import { useUrlState } from "@/hooks/use-url-state";
import { readSpreadsheetFile, spreadsheetRowsToObjects } from "@/utils/spreadsheet-import";

type TabKey = "campaigns" | "templates";
type CampaignViewKey = "contacts" | "campaigns";
type CampaignSegmentKey = "past_customer" | "potential_customer";
type CampaignTargetSegment = CampaignSegmentKey | null;
type CampaignContactTypeFilter = "all" | CampaignSegmentKey;

function normalizeEmailTab(value: string | null): TabKey {
  return value === "campaigns" || value === "templates" ? value : "templates";
}

function normalizeCampaignView(value: string | null): CampaignViewKey {
  return value === "campaigns" ? "campaigns" : "contacts";
}

function renderEditablePlaceholders(value: string): string {
  return value.replace(/\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "{$1}");
}

function replaceLiteral(value: string, literal: string | null | undefined, replacement: string): string {
  if (!literal) return value;
  const escapedLiteral = escapeHtmlAttribute(literal);
  return value.split(literal).join(replacement).split(escapedLiteral).join(replacement);
}

function renderEditableCampaignBody(campaign: EmailCampaign): string {
  let body = renderEditablePlaceholders(campaign.html_body);
  body = replaceLiteral(body, campaign.landing_page_url ?? campaign.video_url, "{landing_page_url}");
  body = replaceLiteral(body, campaign.thumbnail_url, "{thumbnail_url}");
  body = replaceLiteral(body, campaign.video_url, "{video_url}");
  return body;
}

const MOCK_REPLACEMENTS: Record<string, string> = {
  "{first_name}": "Ioana",
  "{last_name}": "Popescu",
  "{participant_name}": "Ioana Popescu",
  "{trainer_name}": "Andrei Văcaru",
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
  "{calendly_url}": "https://calendly.com/andreivacaru/intalnire-de-apropiere",
  "{unsubscribe_url}": "https://codrut.andreivacaru.ro/api/communications/campaigns/unsubscribe/demo-token",
};

const EMAIL_PREVIEW_SHELL_OPEN =
  '<div style="font-family:Inter,Arial,sans-serif;max-width:620px;margin:0 auto;padding:28px;color:#2b211f;"><div style="border:1px solid #eadfdb;border-radius:18px;padding:28px;background:#fffdfb;"><p style="margin:0 0 8px;font-size:13px;font-weight:700;color:#890505;letter-spacing:.08em;text-transform:uppercase;">Andrei Văcaru</p>';
const EMAIL_PREVIEW_SHELL_CLOSE = "</div></div>";
const PROMOTIONAL_EMAIL_PREVIEW_SHELL_CLOSE =
  '</div><div style="margin-top:24px;padding-top:24px;border-top:1px solid #eadfdb;font-size:12px;line-height:1.5;color:#8c7e7b;text-align:center;"><p style="margin:0 0 8px;">Ai primit acest email deoarece ești abonat la actualizările noastre sau ești un client.</p><p style="margin:0 0 8px;"><a href="{unsubscribe_url}" style="color:#6d5f5b;text-decoration:underline;">Dezabonare</a></p><p style="margin:0;">Str. Exemplu Nr. 10, București, România</p></div></div>';
const EMAIL_HEADING_STYLE = "margin:0 0 16px;font-size:24px;line-height:1.25;";
const EMAIL_PARAGRAPH_STYLE = "margin:0 0 18px;font-size:15px;line-height:1.65;";
const EMAIL_BUTTON_STYLE = "display:inline-block;background:#890505;color:#ffffff;text-decoration:none;border-radius:12px;padding:13px 18px;font-weight:700;";
const DEFAULT_ACTION_TOKEN = "{action_button:Deschide chestionarele|{action_url}}";
const DEFAULT_VIDEO_TOKEN = "{video_block}";

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

function escapeHtmlAttribute(value: string): string {
  return escapeHtml(value).replace(/`/g, "&#96;");
}

function plainCampaignContentToHtml(value: string): string {
  return value
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block) => (
      `<p style="margin:0 0 18px;font-size:15px;line-height:1.65;">${escapeHtml(block).replace(/\n/g, "<br />")}</p>`
    ))
    .join("");
}

function sanitizePreviewHref(value: string): string {
  const trimmed = value.trim();
  if (/^\{[a-zA-Z_][a-zA-Z0-9_]*\}$/.test(trimmed)) {
    return trimmed;
  }
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

function emailInlineMarkdownToHtml(value: string): string {
  return escapeHtml(value)
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\[(.*?)\]\((.*?)\)/g, (_match, label: string, href: string) => {
      const safeHref = escapeHtmlAttribute(sanitizePreviewHref(href));
      return `<a href="${safeHref}" style="color:#890505;text-decoration:underline;font-weight:700;">${label}</a>`;
    });
}

function emailParagraphHtml(value: string): string {
  return `<p style="${EMAIL_PARAGRAPH_STYLE}">${emailInlineMarkdownToHtml(value).replace(/\r?\n/g, "<br />")}</p>`;
}

function emailButtonHtml(label: string, href: string): string {
  const safeHref = escapeHtmlAttribute(sanitizePreviewHref(href));
  const safeLabel = escapeHtml(label.trim() || "Deschide linkul");
  return `<p style="margin:24px 0;"><a href="${safeHref}" style="${EMAIL_BUTTON_STYLE}">${safeLabel}</a></p><p style="margin:0;font-size:13px;line-height:1.6;color:#6d5f5b;">Link platformă: <a href="${safeHref}" style="color:#890505;text-decoration:underline;">${safeHref}</a></p>`;
}

function emailVideoBlockHtml(): string {
  return '<p style="margin:24px 0;"><a href="{landing_page_url}" style="display:block;text-decoration:none;color:inherit;"><span style="display:block;position:relative;max-width:420px;border-radius:14px;overflow:hidden;background:#2b211f;"><img src="{thumbnail_url}" alt="Previzualizare video" style="display:block;width:100%;max-width:420px;height:auto;border:0;border-radius:14px;" /><span style="position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:64px;height:64px;border-radius:999px;background:rgba(255,255,255,.92);box-shadow:0 14px 35px rgba(0,0,0,.22);text-align:center;line-height:64px;color:#890505;font-size:28px;font-weight:700;">&#9654;</span></span></a></p>';
}

function emailBulletTableHtml(lines: string[]): string {
  const rows = lines.map((line) => {
    const match = line.match(/^\s*([•✓✗*-])\s+(.*)$/);
    const marker = match?.[1] === "*" || match?.[1] === "-" ? "•" : match?.[1] ?? "•";
    const body = match?.[2] ?? line;
    return `<tr><td style="width:24px;padding:0 8px 8px 0;vertical-align:top;color:#890505;font-weight:700;">${escapeHtml(marker)}</td><td style="padding:0 0 8px;vertical-align:top;">${emailInlineMarkdownToHtml(body)}</td></tr>`;
  }).join("");
  return `<table role="presentation" cellpadding="0" cellspacing="0" style="width:100%;margin:0 0 18px;font-size:15px;line-height:1.65;border-collapse:collapse;">${rows}</table>`;
}

function friendlyEmailBlocksToHtml(body: string): string {
  return body
    .split(/\n{2,}/)
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block) => {
      if (block === DEFAULT_VIDEO_TOKEN) return emailVideoBlockHtml();
      const actionMatch = block.match(/^\{action_button:([^|]+)\|(.+)\}$/);
      if (actionMatch) return emailButtonHtml(actionMatch[1], actionMatch[2]);
      const calendlyMatch = block.match(/^\{calendly_button:([^}]+)\}$/);
      if (calendlyMatch) return emailButtonHtml(calendlyMatch[1], "{calendly_url}");
      const lines = block.split(/\r?\n/);
      if (lines.every((line) => /^\s*[•✓✗*-]\s+/.test(line))) {
        return emailBulletTableHtml(lines);
      }
      return emailParagraphHtml(block);
    })
    .join("");
}

export function buildStyledEmailTemplateBody({
  heading,
  body,
  lane,
}: {
  heading: string;
  body: string;
  lane: "transactional" | "campaign";
}): string {
  const headingHtml = heading.trim()
    ? `<h1 style="${EMAIL_HEADING_STYLE}">${emailInlineMarkdownToHtml(heading.trim())}</h1>`
    : "";
  const shellClose = lane === "campaign" ? PROMOTIONAL_EMAIL_PREVIEW_SHELL_CLOSE : EMAIL_PREVIEW_SHELL_CLOSE;
  return `${EMAIL_PREVIEW_SHELL_OPEN}${headingHtml}${friendlyEmailBlocksToHtml(body)}${shellClose}`;
}

export function parseEmailTemplateEditorDraft(body: string, fallbackHeading: string): { heading: string; body: string } {
  if (!looksLikeHtml(body) || typeof DOMParser === "undefined") {
    return { heading: fallbackHeading, body };
  }

  const parser = new DOMParser();
  const document = parser.parseFromString(body, "text/html");
  const headingNode = document.body.querySelector("h1,h2,h3");
  const heading = headingNode?.textContent?.trim() || fallbackHeading;
  const blocks: string[] = [];
  const skipTexts = [
    "Andrei Văcaru",
    "Ai primit acest email deoarece",
    "Str. Exemplu Nr. 10",
  ];

  Array.from(document.body.querySelectorAll("h1,h2,h3,p,table")).forEach((node) => {
    if (node === headingNode) return;
    const text = node.textContent?.replace(/\s+/g, " ").trim() ?? "";
    if (!text || skipTexts.some((skipText) => text.includes(skipText)) || text.startsWith("Link platformă:") || text === "Dezabonare") {
      return;
    }
    if (node.tagName === "TABLE") {
      const rows = Array.from(node.querySelectorAll("tr"))
        .map((row) => {
          const cells = Array.from(row.querySelectorAll("td,th"));
          const marker = cells[0]?.textContent?.trim() || "•";
          const value = cells.slice(1).map((cell) => cell.textContent?.trim() ?? "").join(" ").trim();
          return value ? `${marker} ${value}` : "";
        })
        .filter(Boolean);
      if (rows.length > 0) blocks.push(rows.join("\n"));
      return;
    }
    if (node.querySelector("img")) {
      blocks.push(DEFAULT_VIDEO_TOKEN);
      return;
    }
    const link = node.querySelector("a[href]");
    if (link) {
      const href = link.getAttribute("href") ?? "";
      const label = link.textContent?.trim() || "Deschide linkul";
      if (href.includes("calendly_url")) {
        blocks.push(`{calendly_button:${label}}`);
      } else if (href.includes("action_url") || href.includes("landing_page_url") || link.getAttribute("style")?.includes("background")) {
        blocks.push(`{action_button:${label}|${href}}`);
      } else {
        blocks.push(text);
      }
      return;
    }
    blocks.push(text);
  });

  return { heading, body: blocks.join("\n\n") };
}

export function replacePreviewPlaceholders(
  value: string,
  replacements: Record<string, string> = MOCK_REPLACEMENTS,
): string {
  let replaced = value;
  Object.entries(replacements).forEach(([key, replacement]) => {
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
    "TABLE",
    "TBODY",
    "TD",
    "TH",
    "THEAD",
    "TR",
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

export function renderCampaignEmailPreviewShell(
  bodyHtml: string,
  replacements: Record<string, string> = MOCK_REPLACEMENTS,
): string {
  if (bodyHtml.includes("font-family:Inter,Arial,sans-serif") && bodyHtml.includes("Andrei Văcaru")) {
    return bodyHtml;
  }

  const shellClose = replacePreviewPlaceholders(PROMOTIONAL_EMAIL_PREVIEW_SHELL_CLOSE, replacements);
  return `${EMAIL_PREVIEW_SHELL_OPEN}${bodyHtml || ""}${shellClose}`;
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
  status: "active" | "suppressed" | "unsubscribed";
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
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
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
  const sendValue = readImportValue(row, ["De trimis", "Trimite", "Send", "Active"]);
  if (!sendValue) {
    return true;
  }
  return ["da", "yes", "y", "1", "true", "activ"].includes(normalizeImportKey(sendValue));
}

function isValidImportEmail(value: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function importDraftHasEmailError(draft: Pick<CampaignImportDraft, "email" | "send">): boolean {
  return draft.send && !isValidImportEmail(draft.email.trim());
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
  const explicitName = readImportValue(row, ["contact_name", "Contact name", "Nume contact", "Nume complet", "Full name", "Name", "name"]);
  if (explicitName) {
    return explicitName;
  }

  const composedName = [
    readImportValue(row, ["Primul prenume", "Prenume", "Prenume 1", "First name", "first_name"]),
    readImportValue(row, ["Al doilea prenume", "Prenume 2", "Middle name", "middle_name"]),
    readImportValue(row, ["Nume de familie", "Nume familie", "Nume", "Familie", "Surname", "Last name", "last_name"]),
  ].filter(Boolean).join(" ");
  if (composedName) {
    return composedName;
  }

  return readImportValue(row, ["Nume"]);
}

function importOrganizationName(row: Record<string, unknown>): string {
  return readImportValue(row, [
    "organization_name",
    "Organizație",
    "Organizatie",
    "Organizaţie",
    "Organizația",
    "Organizatia",
    "Companie",
    "company",
    "Company",
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

function campaignImportDraftToRecipient(row: CampaignImportDraft): CampaignRecipientCreate {
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
      if (uniqueDraftsByEmail.has(normalizedEmail)) {
        duplicateEmailCount += 1;
      }
      uniqueDraftsByEmail.set(normalizedEmail, draft);
      continue;
    }
    uniqueDrafts.push(draft);
  }

  return {
    duplicateEmailCount,
    uniqueDrafts: [...uniqueDraftsByEmail.values(), ...uniqueDrafts],
  };
}

export function buildCampaignRecipientImport(rows: Record<string, unknown>[]): CampaignRecipientImportResult {
  return rows.reduce<CampaignRecipientImportResult>(
    (result, row) => {
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

function campaignSegmentLabel(segment: CampaignTargetSegment): string {
  if (segment === null) return "Fără grup";
  return segment === "past_customer" ? "Client existent" : "Prospect";
}

function campaignRecipientMatchesSearch(recipient: CampaignRecipientRow, query: string): boolean {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return true;
  return [
    recipient.company,
    campaignRecipientName(recipient),
    recipient.email,
  ].some((value) => value.toLowerCase().includes(normalizedQuery));
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
    status: recipient.status === "unsubscribed"
      ? "unsubscribed"
      : recipient.status === "suppressed"
      ? "suppressed"
      : "active",
  };
}

function campaignRecipientSortKey(recipient: CampaignRecipientRow): string {
  return [
    recipient.company,
    campaignRecipientName(recipient),
    recipient.email,
  ].join(" ").toLocaleLowerCase("ro-RO");
}

function campaignRecipientStatusLabel(status: CampaignRecipientRow["status"]): string {
  const labels: Record<CampaignRecipientRow["status"], string> = {
    needs_contact_name: "Nume lipsă",
    ready: "Pregătit",
    sent: "Trimis",
    suppressed: "Inactiv",
    unsubscribed: "Dezabonat",
  };
  return labels[status] ?? status;
}

function isCampaignRecipientEffectivelyActive(recipient: CampaignRecipientRow): boolean {
  return recipient.status !== "suppressed" && recipient.status !== "unsubscribed";
}

function campaignRecipientSourceLabel(source?: string | null): string {
  if (!source) return "Manual";
  if (source === "excel_import") return "Excel";
  return source.replace(/_/g, " ");
}

function EditIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="m16.862 4.487 1.687-1.688a1.875 1.875 0 1 1 2.652 2.652L8.582 18.07a4.5 4.5 0 0 1-1.897 1.13L3 20l.8-3.685a4.5 4.5 0 0 1 1.13-1.897L16.862 4.487Z" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="m14.74 9-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166M19.228 5.79 18.16 19.673A2.25 2.25 0 0 1 15.916 21H8.084a2.25 2.25 0 0 1-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 0 0-3.478-.397m-12 .563c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 0 1 3.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 0 0-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 0 0-7.5 0" />
    </svg>
  );
}

function SaveIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="m4.5 12.75 6 6 9-13.5" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg aria-hidden="true" className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18 18 6M6 6l12 12" />
    </svg>
  );
}

function IconButton({
  label,
  children,
  tone = "neutral",
  disabled,
  onClick,
}: {
  label: string;
  children: React.ReactNode;
  tone?: "neutral" | "danger" | "success";
  disabled?: boolean;
  onClick: () => void;
}) {
  const toneClass = tone === "danger"
    ? "border-red-500/35 bg-red-500/10 text-red-700 hover:border-red-500/55 hover:bg-red-500/15 dark:text-red-200"
    : tone === "success"
    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-700 hover:border-emerald-500/50 hover:bg-emerald-500/15 dark:text-emerald-200"
    : "border-[var(--border)] bg-surface text-foreground/62 hover:border-burgundy/40 hover:text-burgundy";
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className={`tap-soft inline-flex h-9 w-9 items-center justify-center rounded-full border shadow-sm transition disabled:cursor-not-allowed disabled:opacity-55 ${toneClass}`}
    >
      {children}
    </button>
  );
}

type EmailWorkspaceProps = {
  initialSummary: EmailOpsSummary;
};

export function EmailWorkspace({ initialSummary }: EmailWorkspaceProps) {
  const { get, searchKey, setParam, setParams } = useUrlState();
  const [activeTab, setActiveTabState] = useState<TabKey>(normalizeEmailTab(get("tab")));
  const [summary, setSummary] = useState<EmailOpsSummary>(initialSummary);

  function setActiveTab(tab: TabKey) {
    setActiveTabState(tab);
    setParams(
      {
        tab: tab === "templates" ? null : tab,
        modal: null,
        campaignId: null,
      },
      "push",
    );
  }

  useEffect(() => {
    const tab = get("tab");
    const normalizedTab = normalizeEmailTab(tab);
    setActiveTabState(normalizedTab);
    if (tab && tab !== normalizedTab) {
      setParams({ tab: normalizedTab === "templates" ? null : normalizedTab, modal: null, campaignId: null }, "replace");
    }
  }, [get, searchKey, setParams]);

  const refreshSummary = async () => {
    const { getEmailOpsSummary } = await import("@/api/email");
    const fresh = await getEmailOpsSummary();
    setSummary(fresh);
  };

  // Template Manager States
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateIdState] = useState<string>(get("templateId") ?? "");
  const [isEditing, setIsEditing] = useState(false);
  const [isLoadingTemplates, setIsLoadingTemplates] = useState(false);

  function setSelectedTemplateId(templateId: string) {
    setSelectedTemplateIdState(templateId);
    setParam("templateId", templateId || null, "push");
  }

  // Editor fields
  const [editName, setEditName] = useState("");
  const [editSubject, setEditSubject] = useState("");
  const [editHeading, setEditHeading] = useState("");
  const [editBody, setEditBody] = useState("");
  const [editLane, setEditLane] = useState<"transactional" | "campaign">("transactional");
  const [previewCalendlyUrl, setPreviewCalendlyUrl] = useState(MOCK_REPLACEMENTS["{calendly_url}"]);

  // Campaign Manager States
  const [isUploadingCSV, setIsUploadingCSV] = useState(false);
  const [importSheetName, setImportSheetName] = useState<string | null>(null);
  const [importDrafts, setImportDrafts] = useState<CampaignImportDraft[]>([]);
  const [isImportingContacts, setIsImportingContacts] = useState(false);
  const [campaigns, setCampaigns] = useState<EmailCampaign[]>([]);
  const [isLoadingCampaigns, setIsLoadingCampaigns] = useState(false);
  const [isCreatingCampaign, setIsCreatingCampaign] = useState(false);
  const [showCampaignModal, setShowCampaignModal] = useState(get("modal") === "new-campaign" || get("modal") === "edit-campaign");
  const [editingCampaign, setEditingCampaign] = useState<EmailCampaign | null>(null);
  const [campaignModalHydrationKey, setCampaignModalHydrationKey] = useState<string | null>(null);
  const [campaignView, setCampaignViewState] = useState<CampaignViewKey>(normalizeCampaignView(get("view")));
  const [campaignName, setCampaignName] = useState("Campanie video leadership");
  const [campaignSegment, setCampaignSegment] = useState<CampaignTargetSegment>("potential_customer");
  const [campaignTemplateId, setCampaignTemplateId] = useState("");
  const [campaignSubject, setCampaignSubject] = useState("O idee practică pentru echipa ta, {first_name}");
  const [campaignBody, setCampaignBody] = useState("");
  const [campaignPlainBody, setCampaignPlainBody] = useState("");
  const [campaignVideoUrl, setCampaignVideoUrl] = useState("");
  const [campaignThumbnailUrl, setCampaignThumbnailUrl] = useState("");
  const [campaignLandingUrl, setCampaignLandingUrl] = useState("");
  const [campaignMessage, setCampaignMessage] = useState<string | null>(null);
  const [campaignAssetMessage, setCampaignAssetMessage] = useState<string | null>(null);
  const [isUploadingCampaignAsset, setIsUploadingCampaignAsset] = useState(false);
  const [sendingCampaignId, setSendingCampaignId] = useState<string | null>(null);
  const [deletingCampaignId, setDeletingCampaignId] = useState<string | null>(null);
  const [campaignSendResults, setCampaignSendResults] = useState<Record<string, CampaignSendResponse>>({});
  const [campaignMemberships, setCampaignMemberships] = useState<Record<string, string[]>>({});
  const [campaignMembershipSearches, setCampaignMembershipSearches] = useState<Record<string, string>>({});
  const [campaignMembershipTypeFilters, setCampaignMembershipTypeFilters] = useState<Record<string, CampaignContactTypeFilter>>({});
  const [savingCampaignMembershipId, setSavingCampaignMembershipId] = useState<string | null>(null);
  const [campaignContactMessage, setCampaignContactMessage] = useState<string | null>(null);
  const [selectedCampaignRecipientIds, setSelectedCampaignRecipientIds] = useState<string[]>([]);
  const [showInactiveCampaignContacts, setShowInactiveCampaignContacts] = useState(false);
  const [campaignContactSearch, setCampaignContactSearch] = useState("");
  const [campaignContactTypeFilter, setCampaignContactTypeFilter] = useState<CampaignContactTypeFilter>("all");
  const [bulkContactAction, setBulkContactAction] = useState<null | "activate" | "suppress" | "delete">(null);
  const [editingContactId, setEditingContactId] = useState<string | null>(null);
  const [contactDrafts, setContactDrafts] = useState<Record<string, CampaignContactDraft>>({});
  const [savingContactId, setSavingContactId] = useState<string | null>(null);
  const [deletingContactId, setDeletingContactId] = useState<string | null>(null);

  function setCampaignView(view: CampaignViewKey) {
    setCampaignViewState(view);
    setParam("view", view === "contacts" ? null : view, "push");
  }

  function closeCampaignModal(mode: "push" | "replace" = "push") {
    setShowCampaignModal(false);
    setEditingCampaign(null);
    setCampaignModalHydrationKey(null);
    setParams({ modal: null, campaignId: null }, mode);
  }

  function closeManualAddModal(mode: "push" | "replace" = "push") {
    setShowManualAddModal(false);
    setParam("modal", null, mode);
  }

  const sortedCampaignRecipients = useMemo(
    () =>
      [...summary.campaign.recipients].sort((first, second) =>
        campaignRecipientSortKey(first).localeCompare(campaignRecipientSortKey(second), "ro-RO"),
      ),
    [summary.campaign.recipients],
  );
  const activeCampaignContacts = useMemo(
    () => sortedCampaignRecipients.filter((recipient) => recipient.status !== "suppressed"),
    [sortedCampaignRecipients],
  );
  const inactiveCampaignContacts = useMemo(
    () => sortedCampaignRecipients.filter((recipient) => recipient.status === "suppressed"),
    [sortedCampaignRecipients],
  );
  const visibleCampaignContacts = useMemo(
    () => {
      const baseContacts = showInactiveCampaignContacts
        ? sortedCampaignRecipients
        : activeCampaignContacts;
      return baseContacts.filter((recipient) => {
        if (campaignContactTypeFilter !== "all" && campaignRecipientSegment(recipient) !== campaignContactTypeFilter) {
          return false;
        }
        return campaignRecipientMatchesSearch(recipient, campaignContactSearch);
      });
    },
    [
      activeCampaignContacts,
      campaignContactSearch,
      campaignContactTypeFilter,
      showInactiveCampaignContacts,
      sortedCampaignRecipients,
    ],
  );
  const selectableCampaignRecipientIdSet = useMemo(
    () =>
      new Set(
        visibleCampaignContacts
          .filter((recipient) => recipient.status !== "unsubscribed" && recipient.email.trim())
          .map((recipient) => recipient.id),
      ),
    [visibleCampaignContacts],
  );
  const visibleSelectableCampaignRecipientIds = useMemo(
    () => visibleCampaignContacts
      .filter((recipient) => selectableCampaignRecipientIdSet.has(recipient.id))
      .map((recipient) => recipient.id),
    [selectableCampaignRecipientIdSet, visibleCampaignContacts],
  );
  const visibleSelectedCampaignRecipientIds = useMemo(
    () => selectedCampaignRecipientIds.filter((recipientId) => selectableCampaignRecipientIdSet.has(recipientId)),
    [selectableCampaignRecipientIdSet, selectedCampaignRecipientIds],
  );
  const isSelectedCampaignContactBeingEdited = editingContactId !== null
    && visibleSelectedCampaignRecipientIds.includes(editingContactId);
  const campaignContactsById = useMemo(
    () => new Map(summary.campaign.recipients.map((recipient) => [recipient.id, recipient])),
    [summary.campaign.recipients],
  );
  const visibleContactsAllSelected = visibleSelectableCampaignRecipientIds.length > 0
    && visibleSelectableCampaignRecipientIds.every((recipientId) => selectedCampaignRecipientIds.includes(recipientId));
  const previewReplacements = useMemo<Record<string, string>>(
    () => ({
      ...MOCK_REPLACEMENTS,
      "{calendly_url}": previewCalendlyUrl,
    }),
    [previewCalendlyUrl],
  );
  const campaignPreviewReplacements = useMemo(() => {
    const videoUrl = campaignVideoUrl.trim();
    const landingUrl = campaignLandingUrl.trim() || videoUrl;
    const thumbnailUrl = campaignThumbnailUrl.trim();
    return {
      ...previewReplacements,
      "{video_url}": videoUrl || previewReplacements["{video_url}"],
      "{landing_page_url}": landingUrl || previewReplacements["{landing_page_url}"],
      "{thumbnail_url}": thumbnailUrl || previewReplacements["{thumbnail_url}"],
    };
  }, [campaignLandingUrl, campaignThumbnailUrl, campaignVideoUrl, previewReplacements]);
  const campaignMediaHasChanges = useMemo(() => {
    if (!editingCampaign) return false;
    return (
      (editingCampaign.video_url ?? "") !== campaignVideoUrl.trim()
      || (editingCampaign.thumbnail_url ?? "") !== campaignThumbnailUrl.trim()
      || (editingCampaign.landing_page_url ?? "") !== campaignLandingUrl.trim()
    );
  }, [campaignLandingUrl, campaignThumbnailUrl, campaignVideoUrl, editingCampaign]);

  const campaignTemplates = useMemo(
    () => templates.filter((template) => {
      if (template.lane !== "campaign") return false;
      if (campaignSegment === null) return true;
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

  const applyCampaignToModal = useCallback((campaign: EmailCampaign) => {
    setEditingCampaign(campaign);
    setCampaignName(campaign.name);
    setCampaignSegment(campaign.segment);
    setCampaignTemplateId("");
    const editableBody = renderEditableCampaignBody(campaign);
    setCampaignSubject(renderEditablePlaceholders(campaign.subject));
    setCampaignBody(editableBody);
    setCampaignPlainBody(htmlToPlainText(editableBody));
    setCampaignVideoUrl(campaign.video_url ?? "");
    setCampaignThumbnailUrl(campaign.thumbnail_url ?? "");
    setCampaignLandingUrl(campaign.landing_page_url ?? "");
    setCampaignAssetMessage(null);
    setCampaignMessage(null);
  }, []);

  const resetCampaignModal = useCallback(() => {
    setEditingCampaign(null);
    setCampaignName("Campanie video leadership");
    setCampaignSegment("potential_customer");
    setCampaignTemplateId("");
    setCampaignSubject("O idee practică pentru echipa ta, {first_name}");
    setCampaignBody("");
    setCampaignPlainBody("");
    setCampaignVideoUrl("");
    setCampaignThumbnailUrl("");
    setCampaignLandingUrl("");
    setCampaignAssetMessage(null);
  }, []);

  function openCreateCampaignModal() {
    resetCampaignModal();
    setCampaignModalHydrationKey("new");
    setCampaignMessage(null);
    setShowCampaignModal(true);
    setParams({ tab: "campaigns", modal: "new-campaign", campaignId: null }, "push");
  }

  function openEditCampaignModal(campaign: EmailCampaign) {
    applyCampaignToModal(campaign);
    setCampaignModalHydrationKey(`edit:${campaign.id}`);
    setShowCampaignModal(true);
    setParams({ tab: "campaigns", view: "campaigns", modal: "edit-campaign", campaignId: campaign.id }, "push");
  }

  const urlTemplateId = get("templateId") ?? "";
  const urlCampaignView = normalizeCampaignView(get("view"));
  const urlModal = get("modal");
  const urlCampaignId = get("campaignId");
  const isManualAddModalOpen = urlModal === "add-contact";

  useEffect(() => {
    setSelectedTemplateIdState(urlTemplateId);
    setCampaignViewState(urlCampaignView);
    setShowManualAddModal(isManualAddModalOpen);

    if (urlModal === "new-campaign") {
      if (campaignModalHydrationKey !== "new") {
        resetCampaignModal();
        setCampaignMessage(null);
        setCampaignModalHydrationKey("new");
      }
      setShowCampaignModal(true);
      return;
    }

    if (urlModal === "edit-campaign") {
      const campaign = urlCampaignId ? campaigns.find((item) => item.id === urlCampaignId) : null;
      if (campaign) {
        const nextHydrationKey = `edit:${campaign.id}`;
        if (campaignModalHydrationKey !== nextHydrationKey) {
          applyCampaignToModal(campaign);
          setCampaignModalHydrationKey(nextHydrationKey);
        }
        setShowCampaignModal(true);
      } else {
        setShowCampaignModal(false);
      }
      return;
    }

    setShowCampaignModal(false);
    setEditingCampaign(null);
    setCampaignModalHydrationKey(null);
  }, [
    applyCampaignToModal,
    campaignModalHydrationKey,
    campaigns,
    isManualAddModalOpen,
    resetCampaignModal,
    searchKey,
    urlCampaignId,
    urlCampaignView,
    urlModal,
    urlTemplateId,
  ]);

  // Manual Add State
  const [showManualAddModal, setShowManualAddModal] = useState(get("modal") === "add-contact");
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
      closeManualAddModal("replace");
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
      const spreadsheet = await readSpreadsheetFile(file, selectCampaignRecipientImportSheetName);
      const sheetName = spreadsheet.sheetName;
      const rows = spreadsheetRowsToObjects(spreadsheet.rows);
      const drafts = buildCampaignRecipientImportDrafts(rows);

      if (drafts.length > 0) {
        const invalidCount = drafts.filter(importDraftHasEmailError).length;
        setImportSheetName(sheetName ?? null);
        setImportDrafts(drafts);
        setCampaignContactMessage(
          `Previzualizare ${drafts.length} contacte din sheet-ul ${sheetName ?? "selectat"}.${invalidCount > 0 ? ` ${invalidCount} emailuri trebuie corectate.` : ""}`,
        );
      } else {
        setCampaignContactMessage("Fișierul nu conține contacte de importat.");
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
        draft.id === rowId
          ? {
              ...draft,
              [field]: value,
              send: field === "email" && !isValidImportEmail(String(value).trim()) ? false : draft.send,
            }
          : draft,
      ),
    );
  };

  const invalidImportDraftCount = importDrafts.filter(importDraftHasEmailError).length;
  const activeImportDraftCount = importDrafts.filter((draft) => draft.send).length;
  const duplicateImportDraftEmailCount = useMemo(
    () => uniqueCampaignImportDrafts(importDrafts).duplicateEmailCount,
    [importDrafts],
  );

  const confirmCampaignRecipientImport = async () => {
    if (invalidImportDraftCount > 0) {
      setCampaignContactMessage("Corectează emailurile invalide înainte de import.");
      return;
    }
    setIsImportingContacts(true);
    try {
      const { duplicateEmailCount, uniqueDrafts } = uniqueCampaignImportDrafts(importDrafts);
      const activeUniqueDraftCount = uniqueDrafts.filter((draft) => draft.send).length;
      const result = await bulkCreateCampaignRecipientsOnServer(uniqueDrafts.map(campaignImportDraftToRecipient));
      const savedCount = typeof result?.count === "number" ? result.count : uniqueDrafts.length;
      const createdCount = typeof result?.created === "number" ? result.created : null;
      const updatedCount = typeof result?.updated === "number" ? result.updated : null;
      const metricCopy = createdCount !== null && updatedCount !== null
        ? `${createdCount} noi, ${updatedCount} actualizate`
        : `${savedCount} salvate`;
      setCampaignContactMessage(
        `S-au importat ${savedCount} contacte (${metricCopy}): ${activeUniqueDraftCount} active, ${uniqueDrafts.length - activeUniqueDraftCount} inactive.${duplicateEmailCount > 0 ? ` ${duplicateEmailCount} duplicate cu același email au fost consolidate folosind ultima apariție.` : ""}`,
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
      const nextCampaigns = await listCampaignsOnServer();
      setCampaigns(nextCampaigns);
      const membershipEntries = await Promise.all(
        nextCampaigns.map(async (campaign) => {
          const recipients = await listCampaignRecipientMembershipOnServer(campaign.id);
          return [campaign.id, recipients.map((recipient) => recipient.id)] as const;
        }),
      );
      setCampaignMemberships(Object.fromEntries(membershipEntries));
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
    const templateText = htmlToPlainText(templateBody);
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
      setCampaignMessage("Completează numele campaniei. Dacă folosești video, adaugă linkul și thumbnailul.");
      return;
    }

    setIsCreatingCampaign(true);
    setCampaignMessage(null);
    try {
      if (editingCampaign) {
        await updateCampaignOnServer(editingCampaign.id, {
          ...payload,
          video_url: campaignVideoUrl.trim() ? payload.video_url : null,
          thumbnail_url: campaignThumbnailUrl.trim() ? payload.thumbnail_url : null,
          landing_page_url: campaignLandingUrl.trim() ? payload.landing_page_url : null,
          status: editingCampaign.status,
        });
        setCampaignMessage(
          campaignMediaHasChanges
            ? "Campania a fost actualizată. Video-ul, landing page-ul și thumbnailul afișate în preview vor fi folosite la trimiterile viitoare."
            : "Campania a fost actualizată.",
        );
      } else {
        await createCampaignOnServer(payload);
        setCampaignMessage("Campania a fost salvată.");
      }
      setCampaignViewState("campaigns");
      setShowCampaignModal(false);
      setEditingCampaign(null);
      setCampaignModalHydrationKey(null);
      setParams({ tab: "campaigns", view: "campaigns", modal: null, campaignId: null }, "replace");
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
    if (draft.status === "active" && !draft.email.trim()) {
      setCampaignContactMessage("Adaugă email înainte să activezi contactul.");
      return;
    }

    setSavingContactId(recipient.id);
    setCampaignContactMessage(null);
    try {
      if (recipient.status === "unsubscribed" && draft.status !== "unsubscribed") {
        setCampaignContactMessage("Contactul s-a dezabonat. Statusul nu poate fi schimbat din listă.");
        return;
      }

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
                  status: draft.status === "unsubscribed"
                    ? "unsubscribed"
                    : draft.status === "suppressed"
                    ? "suppressed"
                    : draft.contact_name.trim()
                    ? "ready"
                    : "needs_contact_name",
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

  const toggleContactActive = async (recipient: CampaignRecipientRow) => {
    if (recipient.status === "unsubscribed") {
      setCampaignContactMessage("Contactul s-a dezabonat. Nu îl putem reactiva din lista de campanii.");
      return;
    }
    const draft = contactDrafts[recipient.id] ?? campaignRecipientDraft(recipient);
    const nextStatus: CampaignContactDraft["status"] = recipient.status === "suppressed" ? "active" : "suppressed";
    if (nextStatus === "active" && !draft.email.trim() && !recipient.email.trim()) {
      setCampaignContactMessage("Adaugă email înainte să activezi contactul.");
      return;
    }

    setSavingContactId(recipient.id);
    setCampaignContactMessage(null);
    try {
      await updateCampaignRecipientOnServer(recipient.id, {
        status: nextStatus,
      });
      setSummary((currentSummary) => ({
        ...currentSummary,
        campaign: {
          ...currentSummary.campaign,
          recipients: currentSummary.campaign.recipients.map((currentRecipient) =>
            currentRecipient.id === recipient.id
              ? {
                  ...currentRecipient,
                  status: nextStatus === "suppressed"
                    ? "suppressed"
                    : campaignRecipientName(currentRecipient)
                    ? "ready"
                    : "needs_contact_name",
                }
              : currentRecipient,
          ),
        },
      }));
      setContactDrafts((drafts) => ({
        ...drafts,
        [recipient.id]: {
          ...(drafts[recipient.id] ?? campaignRecipientDraft(recipient)),
          status: nextStatus,
        },
      }));
      setCampaignContactMessage(nextStatus === "active" ? "Contactul este activ pentru campanii." : "Contactul este inactiv.");
    } catch (error) {
      setCampaignContactMessage(error instanceof Error ? error.message : "Statusul contactului nu a putut fi actualizat.");
    } finally {
      setSavingContactId(null);
    }
  };

  const toggleSelectedCampaignRecipient = (recipientId: string) => {
    if (!selectableCampaignRecipientIdSet.has(recipientId)) return;
    setSelectedCampaignRecipientIds((currentIds) =>
      currentIds.includes(recipientId)
        ? currentIds.filter((id) => id !== recipientId)
        : [...currentIds, recipientId],
    );
  };

  const toggleAllVisibleCampaignRecipients = () => {
    setSelectedCampaignRecipientIds((currentIds) => {
      const currentSet = new Set(currentIds);
      if (visibleContactsAllSelected) {
        return currentIds.filter((recipientId) => !visibleSelectableCampaignRecipientIds.includes(recipientId));
      }
      for (const recipientId of visibleSelectableCampaignRecipientIds) {
        currentSet.add(recipientId);
      }
      return Array.from(currentSet);
    });
  };

  const toggleInactiveCampaignContacts = () => {
    setShowInactiveCampaignContacts((current) => {
      if (current) {
        const inactiveIds = new Set(inactiveCampaignContacts.map((recipient) => recipient.id));
        setSelectedCampaignRecipientIds((currentIds) =>
          currentIds.filter((recipientId) => !inactiveIds.has(recipientId)),
        );
      }
      return !current;
    });
  };

  const updateSelectedCampaignContactsStatus = async (nextStatus: "active" | "suppressed") => {
    if (visibleSelectedCampaignRecipientIds.length === 0) {
      setCampaignContactMessage("Selectează cel puțin un contact.");
      return;
    }
    if (isSelectedCampaignContactBeingEdited) {
      setCampaignContactMessage("Salvează sau anulează editarea înainte de operațiuni în masă.");
      return;
    }
    const selectedContacts = summary.campaign.recipients.filter((recipient) =>
      visibleSelectedCampaignRecipientIds.includes(recipient.id),
    );
    const contactsToUpdate = selectedContacts.filter((recipient) => {
      if (recipient.status === "unsubscribed") return false;
      const isActive = isCampaignRecipientEffectivelyActive(recipient);
      return nextStatus === "active" ? !isActive : isActive;
    });
    if (contactsToUpdate.length === 0) {
      setCampaignContactMessage(nextStatus === "active" ? "Contactele selectate sunt deja active." : "Contactele selectate sunt deja inactive.");
      return;
    }

    setBulkContactAction(nextStatus === "active" ? "activate" : "suppress");
    setCampaignContactMessage(null);
    try {
      await Promise.all(
        contactsToUpdate.map((recipient) =>
          updateCampaignRecipientOnServer(recipient.id, { status: nextStatus }),
        ),
      );
      setSummary((currentSummary) => ({
        ...currentSummary,
        campaign: {
          ...currentSummary.campaign,
          recipients: currentSummary.campaign.recipients.map((recipient) =>
            contactsToUpdate.some((updated) => updated.id === recipient.id)
              ? {
                  ...recipient,
                  status: nextStatus === "suppressed"
                    ? "suppressed"
                    : campaignRecipientName(recipient)
                    ? "ready"
                    : "needs_contact_name",
                }
              : recipient,
          ),
        },
      }));
      setCampaignContactMessage(
        nextStatus === "active"
          ? `${contactsToUpdate.length} contacte au fost activate.`
          : `${contactsToUpdate.length} contacte au fost dezactivate.`,
      );
    } catch (error) {
      setCampaignContactMessage(error instanceof Error ? error.message : "Operațiunea pe contacte nu a putut fi finalizată.");
    } finally {
      setBulkContactAction(null);
    }
  };

  const deleteSelectedCampaignContacts = async () => {
    if (visibleSelectedCampaignRecipientIds.length === 0) {
      setCampaignContactMessage("Selectează cel puțin un contact.");
      return;
    }
    if (isSelectedCampaignContactBeingEdited) {
      setCampaignContactMessage("Salvează sau anulează editarea înainte de ștergerea în masă.");
      return;
    }
    const confirmed = window.confirm(`Ștergi ${visibleSelectedCampaignRecipientIds.length} contacte selectate? Istoricul agregat de email rămâne în rapoarte.`);
    if (!confirmed) return;

    setBulkContactAction("delete");
    setCampaignContactMessage(null);
    try {
      await Promise.all(visibleSelectedCampaignRecipientIds.map((recipientId) => deleteCampaignRecipientOnServer(recipientId)));
      setSummary((currentSummary) => ({
        ...currentSummary,
        campaign: {
          ...currentSummary.campaign,
          recipients: currentSummary.campaign.recipients.filter(
            (recipient) => !visibleSelectedCampaignRecipientIds.includes(recipient.id),
          ),
        },
      }));
      setSelectedCampaignRecipientIds((currentIds) =>
        currentIds.filter((recipientId) => !visibleSelectedCampaignRecipientIds.includes(recipientId)),
      );
      setCampaignContactMessage(`${visibleSelectedCampaignRecipientIds.length} contacte au fost șterse.`);
    } catch (error) {
      setCampaignContactMessage(error instanceof Error ? error.message : "Contactele selectate nu au putut fi șterse.");
    } finally {
      setBulkContactAction(null);
    }
  };

  const campaignEligibleRecipients = () =>
    summary.campaign.recipients.filter((recipient) =>
      isCampaignRecipientEffectivelyActive(recipient)
      && recipient.email.trim()
    );

  const visibleCampaignEligibleRecipients = (campaign: EmailCampaign) => {
    const search = campaignMembershipSearches[campaign.id] ?? "";
    const typeFilter = campaignMembershipTypeFilters[campaign.id] ?? "all";
    return campaignEligibleRecipients().filter((recipient) =>
      campaignRecipientMatchesSearch(recipient, search)
      && (typeFilter === "all" || campaignRecipientSegment(recipient) === typeFilter),
    );
  };

  const activeCampaignMembershipIds = (campaign: EmailCampaign) =>
    (campaignMemberships[campaign.id] ?? []).filter((recipientId) => {
      const recipient = campaignContactsById.get(recipientId);
      return Boolean(
        recipient
        && isCampaignRecipientEffectivelyActive(recipient)
        && recipient.email.trim(),
      );
    });

  const toggleCampaignMembershipRecipient = (campaign: EmailCampaign, recipientId: string) => {
    const eligibleIds = new Set(campaignEligibleRecipients().map((recipient) => recipient.id));
    if (!eligibleIds.has(recipientId)) return;
    setCampaignMemberships((currentMemberships) => {
      const currentIds = currentMemberships[campaign.id] ?? [];
      return {
        ...currentMemberships,
        [campaign.id]: currentIds.includes(recipientId)
          ? currentIds.filter((id) => id !== recipientId)
          : [...currentIds, recipientId],
      };
    });
  };

  const saveCampaignMembership = async (campaign: EmailCampaign) => {
    setSavingCampaignMembershipId(campaign.id);
    setCampaignMessage(null);
    try {
      const memberIds = activeCampaignMembershipIds(campaign);
      const savedRows = await replaceCampaignRecipientMembershipOnServer(campaign.id, memberIds);
      setCampaignMemberships((currentMemberships) => ({
        ...currentMemberships,
        [campaign.id]: savedRows.map((recipient) => recipient.id),
      }));
      setCampaignMessage(`Lista campaniei „${campaign.name}” a fost salvată: ${savedRows.length} destinatari.`);
    } catch (error) {
      setCampaignMessage(error instanceof Error ? error.message : "Lista campaniei nu a putut fi salvată.");
    } finally {
      setSavingCampaignMembershipId(null);
    }
  };

  const handleSendCampaign = async (
    campaign: EmailCampaign,
    mode: "new" | "all" | "selected" = "new",
  ) => {
    const selectedRecipientIds = mode === "selected" ? activeCampaignMembershipIds(campaign) : undefined;
    const selectedRecipientCount = selectedRecipientIds?.length ?? 0;
    if (mode === "selected" && selectedRecipientCount === 0) {
      setCampaignMessage("Alege cel puțin un destinatar activ în lista acestei campanii.");
      return;
    }
    const confirmed = window.confirm(
      mode === "selected"
        ? `Trimiți campania „${campaign.name}” către ${selectedRecipientCount} destinatari din lista campaniei?`
        : mode === "all"
        ? `Trimiți campania „${campaign.name}” către toți destinatarii salvați ai campaniei, inclusiv cei care au mai primit-o?`
        : `Trimiți campania „${campaign.name}” doar către destinatarii salvați care nu au primit-o încă?`,
    );
    if (!confirmed) return;

    setSendingCampaignId(campaign.id);
    setCampaignMessage(null);
    try {
      if (mode === "selected" && selectedRecipientIds) {
        const savedRows = await replaceCampaignRecipientMembershipOnServer(campaign.id, selectedRecipientIds);
        setCampaignMemberships((currentMemberships) => ({
          ...currentMemberships,
          [campaign.id]: savedRows.map((recipient) => recipient.id),
        }));
      }
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
      setCampaignMemberships((previousMemberships) => {
        const nextMemberships = { ...previousMemberships };
        delete nextMemberships[campaign.id];
        return nextMemberships;
      });
      setCampaignMembershipSearches((previousSearches) => {
        const nextSearches = { ...previousSearches };
        delete nextSearches[campaign.id];
        return nextSearches;
      });
      setCampaignMembershipTypeFilters((previousFilters) => {
        const nextFilters = { ...previousFilters };
        delete nextFilters[campaign.id];
        return nextFilters;
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
  const [searchQuery, setSearchQuery] = useState(get("q") ?? "");

  useEffect(() => {
    setSearchQuery(get("q") ?? "");
  }, [get, searchKey]);

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
      const draft = parseEmailTemplateEditorDraft(selectedTemplate.body, selectedTemplate.subject);
      setEditName(selectedTemplate.name);
      setEditSubject(selectedTemplate.subject);
      setEditHeading(draft.heading);
      setEditBody(draft.body);
      setEditLane(selectedTemplate.lane);
    }
  }, [selectedTemplate]);

  const handleSaveTemplate = async () => {
    if (!selectedTemplateId || !selectedTemplate) return;
    setIsLoadingTemplates(true);
    try {
      const nextBody = buildStyledEmailTemplateBody({
        heading: editHeading,
        body: editBody,
        lane: editLane,
      });
      const nextTextBody = htmlToPlainText(nextBody);
      const updatedTemp: EmailTemplate = {
        ...selectedTemplate,
        subject: editSubject,
        body: nextBody,
        lane: editLane,
        textBody: nextTextBody,
        placeholders: detectedPlaceholders(
          editSubject,
          `${nextBody}\n${nextTextBody}`,
        ),
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
      body: buildStyledEmailTemplateBody({
        heading: "Titlul din email",
        body: "Salut {first_name},\n\nIntroduceți conținutul noului șablon email aici. Puteți folosi coduri între acolade pentru personalizare.",
        lane: "transactional",
      }),
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

  const getRenderedPreview = useCallback((
    subjectText: string,
    bodyText: string,
    lane: string,
    replacements: Record<string, string> = previewReplacements,
  ) => {
    let replacedSubject = subjectText;
    let replacedBody = bodyText;

    replacedSubject = replacePreviewPlaceholders(replacedSubject, replacements);
    replacedBody = replacePreviewPlaceholders(replacedBody, replacements);

    let html = renderEmailTemplatePreviewBody(replacedBody);

    if (lane === "campaign") {
      html = renderCampaignEmailPreviewShell(html, replacements);
    }

    return {
      subject: replacedSubject,
      bodyHtml: html,
    };
  }, [previewReplacements]);

  const preview = useMemo(
    () =>
      selectedTemplate
        ? getRenderedPreview(
            isEditing ? editSubject : selectedTemplate.subject,
            isEditing ? buildStyledEmailTemplateBody({
              heading: editHeading,
              body: editBody,
              lane: editLane,
            }) : selectedTemplate.body,
            isEditing ? editLane : selectedTemplate.lane,
          )
        : { subject: "", bodyHtml: "" },
    [editBody, editHeading, editLane, editSubject, getRenderedPreview, isEditing, selectedTemplate],
  );
  const campaignPreview = useMemo(
    () => getRenderedPreview(
      campaignSubject,
      campaignBody || selectedCampaignTemplate?.body || "",
      "campaign",
      campaignPreviewReplacements,
    ),
    [campaignBody, campaignPreviewReplacements, campaignSubject, getRenderedPreview, selectedCampaignTemplate],
  );

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
                  accept=".csv, application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                  className="hidden" 
                  onChange={handleFileUpload}
                  disabled={isUploadingCSV}
                />
              </label>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => {
                  setShowManualAddModal(true);
                  setParams({ tab: "campaigns", modal: "add-contact" }, "push");
                }}
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
                    campaigns.map((campaign) => {
                      const memberIds = campaignMemberships[campaign.id] ?? [];
                      const activeMemberIds = activeCampaignMembershipIds(campaign);
                      const eligibleRecipients = campaignEligibleRecipients();
                      const visibleEligibleRecipients = visibleCampaignEligibleRecipients(campaign);
                      const membershipSearch = campaignMembershipSearches[campaign.id] ?? "";
                      const membershipTypeFilter = campaignMembershipTypeFilters[campaign.id] ?? "all";

                      return (
                        <article key={campaign.id} className="rounded-xl border border-[var(--border)] bg-surface-muted px-4 py-4 shadow-sm">
                          <div className="flex min-w-0 flex-col gap-3">
                            <div className="min-w-0">
                              <div className="flex flex-wrap items-center gap-2">
                                <p className="text-sm font-bold text-foreground">{campaign.name}</p>
                                <span className="rounded-full border border-[var(--border)] bg-surface px-2.5 py-1 text-[9px] font-bold uppercase tracking-wider text-foreground/55">
                                  {campaign.status === "draft" ? "Draft" : campaign.status === "ready" ? "Pregătită" : campaign.status}
                                </span>
                              </div>
                              <p className="mt-2 line-clamp-2 text-xs font-semibold leading-5 text-foreground/55">
                                {campaignSegmentLabel(campaign.segment)} · {campaign.subject}
                              </p>
                              <div className="mt-3 flex flex-wrap gap-2 text-[10px] font-bold uppercase tracking-wider text-foreground/45">
                                {campaign.video_url ? <span>Video</span> : null}
                                {campaign.thumbnail_url ? <span>Thumbnail</span> : null}
                                {campaign.landing_page_url ? <span>Landing</span> : <span>Direct video</span>}
                                <span>{activeMemberIds.length} destinatari</span>
                              </div>
                            </div>
                            <details className="rounded-xl border border-[var(--border)] bg-surface px-3 py-2">
                              <summary className="tap-soft flex cursor-pointer list-none items-center justify-between gap-3 text-xs font-bold text-foreground/70">
                                <span>Recipienti campanie ({activeMemberIds.length}/{eligibleRecipients.length})</span>
                                <span className="text-foreground/40">⌄</span>
                              </summary>
                              <div className="mt-3 grid gap-2 sm:grid-cols-[minmax(0,1fr)_10rem]">
                                <label className="block">
                                  <span className="sr-only">Caută destinatari pentru {campaign.name}</span>
                                  <input
                                    value={membershipSearch}
                                    onChange={(event) => setCampaignMembershipSearches((current) => ({
                                      ...current,
                                      [campaign.id]: event.target.value,
                                    }))}
                                    className="control-input w-full py-2 text-xs"
                                    placeholder="Caută în toate contactele..."
                                  />
                                </label>
                                <label className="block">
                                  <span className="sr-only">Filtrează destinatari după tip pentru {campaign.name}</span>
                                  <select
                                    value={membershipTypeFilter}
                                    onChange={(event) => setCampaignMembershipTypeFilters((current) => ({
                                      ...current,
                                      [campaign.id]: event.target.value as CampaignContactTypeFilter,
                                    }))}
                                    className="control-input w-full py-2 text-xs"
                                  >
                                    <option value="all">Toate tipurile</option>
                                    <option value="past_customer">Existing</option>
                                    <option value="potential_customer">New</option>
                                  </select>
                                </label>
                              </div>
                              <div className="mt-3 grid max-h-60 gap-2 overflow-y-auto pr-1">
                                {visibleEligibleRecipients.length > 0 ? (
                                  visibleEligibleRecipients.map((recipient) => (
                                    <label
                                      key={recipient.id}
                                      className="flex items-start gap-2 rounded-lg border border-[var(--border)] bg-surface-muted px-3 py-2 text-xs"
                                    >
                                      <input
                                        type="checkbox"
                                        checked={memberIds.includes(recipient.id)}
                                        onChange={() => toggleCampaignMembershipRecipient(campaign, recipient.id)}
                                        className="mt-0.5 h-4 w-4 accent-burgundy"
                                        aria-label={`Include ${recipient.email} în ${campaign.name}`}
                                      />
                                      <span className="min-w-0">
                                        <span className="block font-bold text-foreground">
                                          {campaignRecipientName(recipient) || recipient.email}
                                        </span>
                                        <span className="mt-0.5 block truncate text-foreground/52">
                                          {recipient.company} · {recipient.email}
                                        </span>
                                      </span>
                                    </label>
                                  ))
                                ) : (
                                  <p className="rounded-lg border border-dashed border-[var(--border)] px-3 py-4 text-xs font-semibold text-foreground/45">
                                    {eligibleRecipients.length > 0 ? "Niciun contact nu corespunde căutării." : "Nu există contacte active pentru selecția campaniei."}
                                  </p>
                                )}
                              </div>
                              <div className="mt-3 flex justify-end">
                                <button
                                  type="button"
                                  disabled={savingCampaignMembershipId === campaign.id}
                                  onClick={() => void saveCampaignMembership(campaign)}
                                  className="btn-secondary px-3 py-1.5 text-[10px]"
                                >
                                  {savingCampaignMembershipId === campaign.id ? "Se salvează..." : "Salvează destinatarii"}
                                </button>
                              </div>
                            </details>
                            <div className="flex flex-wrap items-center gap-2 border-t border-[var(--border)] pt-3">
                              <button
                                type="button"
                                disabled={sendingCampaignId === campaign.id || deletingCampaignId === campaign.id || activeMemberIds.length === 0}
                                onClick={() => handleSendCampaign(campaign, "selected")}
                                className="btn-secondary px-3 py-1.5 text-[10px]"
                              >
                                Trimite lista ({activeMemberIds.length})
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
                              <IconButton
                                label={deletingCampaignId === campaign.id ? "Se șterge campania" : `Șterge campania ${campaign.name}`}
                                tone="danger"
                                disabled={sendingCampaignId === campaign.id || deletingCampaignId === campaign.id}
                                onClick={() => handleDeleteCampaign(campaign)}
                              >
                                <TrashIcon />
                              </IconButton>
                              <IconButton
                                label={`Editează campania ${campaign.name}`}
                                disabled={sendingCampaignId === campaign.id || deletingCampaignId === campaign.id}
                                onClick={() => openEditCampaignModal(campaign)}
                              >
                                <EditIcon />
                              </IconButton>
                            </div>
                          </div>
                          {campaignSendResults[campaign.id] ? (
                            <p className="mt-2 rounded-xl bg-surface px-3 py-2 text-[11px] font-semibold text-foreground/60">
                              {campaignSendResults[campaign.id].sent} trimise · {campaignSendResults[campaign.id].failed} eșuate · {campaignSendResults[campaign.id].skipped} omise
                            </p>
                          ) : null}
                        </article>
                      );
                    })
                  )}
                </div>
              </div>
            ) : (
              <div className="p-4">
                {campaignContactMessage ? (
                  <p aria-live="polite" className="mb-4 rounded-xl border border-[var(--border)] bg-surface-muted px-4 py-3 text-xs font-semibold text-foreground/65">
                    {campaignContactMessage}
                  </p>
                ) : null}
                <div className="mb-4 flex flex-col gap-3 rounded-2xl border border-[var(--border)] bg-surface-muted p-3 shadow-sm lg:flex-row lg:items-center lg:justify-between">
                  <div className="flex flex-1 flex-col gap-2 md:flex-row md:items-center">
                    <input
                      value={campaignContactSearch}
                      onChange={(event) => setCampaignContactSearch(event.target.value)}
                      placeholder="Caută nume, email sau companie"
                      className="control-input min-w-0 flex-1 px-3 py-2 text-xs"
                      aria-label="Caută contacte campanie"
                    />
                    <div className="inline-flex w-fit rounded-full border border-[var(--border)] bg-surface p-1">
                      {[
                        ["all", "Toate"],
                        ["past_customer", "Existing"],
                        ["potential_customer", "New"],
                      ].map(([value, label]) => (
                        <button
                          key={value}
                          type="button"
                          onClick={() => setCampaignContactTypeFilter(value as CampaignContactTypeFilter)}
                          className={`rounded-full px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider transition ${
                            campaignContactTypeFilter === value
                              ? "bg-burgundy text-white"
                              : "text-foreground/55 hover:text-burgundy"
                          }`}
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={toggleAllVisibleCampaignRecipients}
                      disabled={visibleSelectableCampaignRecipientIds.length === 0}
                      className="btn-secondary px-3 py-2 text-xs"
                    >
                      {visibleContactsAllSelected ? "Deselectează vizibile" : "Selectează vizibile"}
                    </button>
                    <span className="rounded-full border border-[var(--border)] bg-surface px-3 py-1.5 text-[11px] font-bold text-foreground/60">
                      {visibleSelectedCampaignRecipientIds.length} selectate
                    </span>
                    <button
                      type="button"
                      onClick={toggleInactiveCampaignContacts}
                      className="btn-secondary px-3 py-2 text-xs"
                      aria-expanded={showInactiveCampaignContacts}
                    >
                      {showInactiveCampaignContacts ? "Ascunde inactive" : `Arată inactive (${inactiveCampaignContacts.length})`}
                    </button>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => void updateSelectedCampaignContactsStatus("active")}
                      disabled={bulkContactAction !== null || visibleSelectedCampaignRecipientIds.length === 0 || isSelectedCampaignContactBeingEdited}
                      className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs font-bold text-emerald-700 transition hover:bg-emerald-500/15 disabled:cursor-not-allowed disabled:opacity-55 dark:text-emerald-200"
                    >
                      {bulkContactAction === "activate" ? "Activez..." : "Activează"}
                    </button>
                    <button
                      type="button"
                      onClick={() => void updateSelectedCampaignContactsStatus("suppressed")}
                      disabled={bulkContactAction !== null || visibleSelectedCampaignRecipientIds.length === 0 || isSelectedCampaignContactBeingEdited}
                      className="btn-secondary px-3 py-2 text-xs"
                    >
                      {bulkContactAction === "suppress" ? "Dezactivez..." : "Dezactivează"}
                    </button>
                    <IconButton
                      label="Șterge contactele selectate"
                      tone="danger"
                      disabled={bulkContactAction !== null || visibleSelectedCampaignRecipientIds.length === 0 || isSelectedCampaignContactBeingEdited}
                      onClick={() => void deleteSelectedCampaignContacts()}
                    >
                      <TrashIcon />
                    </IconButton>
                  </div>
                </div>
                <div className="overflow-x-auto rounded-2xl border border-[var(--border)]">
                <table className="min-w-full text-left text-xs">
                  <thead className="border-b border-[var(--border)] bg-surface-muted text-[10px] font-bold uppercase tracking-[0.15em] text-foreground/50">
                    <tr>
                      <th className="w-12 px-4 py-3">Select</th>
                      <th className="px-4 py-3">Contact</th>
                      <th className="px-4 py-3">Tip / status</th>
                      <th className="px-4 py-3">Evenimente</th>
                      <th className="px-4 py-3">Reply / Calendly</th>
                      <th className="px-4 py-3">Rezultat</th>
                      <th className="px-4 py-3 text-right">Acțiuni</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)]">
                    {visibleCampaignContacts.length > 0 ? (
                      visibleCampaignContacts.map((recipient) => {
                        const isEditingContact = editingContactId === recipient.id;
                        const draft = contactDrafts[recipient.id] ?? campaignRecipientDraft(recipient);
                        const isUnsubscribedContact = recipient.status === "unsubscribed";
                        const isContactActive = recipient.status !== "suppressed" && !isUnsubscribedContact;
                        return (
                          <tr key={recipient.id} className={`transition-colors hover:bg-surface-muted ${!isContactActive ? "bg-surface-muted/50 text-foreground/55" : ""}`}>
                            <td className="px-4 py-2.5 align-top">
                              <input
                                type="checkbox"
                                checked={selectableCampaignRecipientIdSet.has(recipient.id) && selectedCampaignRecipientIds.includes(recipient.id)}
                                disabled={!selectableCampaignRecipientIdSet.has(recipient.id)}
                                onChange={() => toggleSelectedCampaignRecipient(recipient.id)}
                                className="h-4 w-4 accent-burgundy disabled:opacity-40"
                                aria-label={`Selectează ${recipient.email}`}
                              />
                            </td>
                            <td className="min-w-[17rem] px-4 py-2.5 align-top">
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
                                  <div className="mt-2 flex flex-wrap gap-1.5">
                                    <span className="rounded-full border border-[var(--border)] bg-surface px-2 py-0.5 text-[9px] font-bold uppercase tracking-wider text-foreground/50">
                                      {campaignRecipientSourceLabel(recipient.emailVariant)}
                                    </span>
                                  </div>
                                </>
                              )}
                            </td>
                            <td className="min-w-[11rem] px-4 py-2.5 align-top">
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
                                    disabled={isUnsubscribedContact}
                                    className="control-input w-full px-3 py-2 text-xs"
                                  >
                                    <option value="active">Da - activ în campanii</option>
                                    <option value="suppressed">Nu - inactiv</option>
                                    {isUnsubscribedContact ? (
                                      <option value="unsubscribed">Dezabonat</option>
                                    ) : null}
                                  </select>
                                </div>
                              ) : (
                                <div className="flex min-w-[9rem] flex-col items-start gap-2">
                                  <span className="capitalize text-[11px] font-bold uppercase tracking-wider text-foreground/60">
                                    {recipient.clientType === "tip_1" ? "Client existent" : "Prospect"}
                                  </span>
                                  <button
                                    type="button"
                                    disabled={savingContactId === recipient.id || isEditingContact || isUnsubscribedContact}
                                    onClick={() => toggleContactActive(recipient)}
                                    aria-pressed={isContactActive}
                                    className={`inline-flex min-w-[5.5rem] items-center justify-center rounded-full border px-3 py-1.5 text-[10px] font-bold uppercase tracking-wider shadow-sm transition disabled:cursor-not-allowed disabled:opacity-60 ${
                                      isContactActive
                                        ? "border-emerald-500/30 bg-emerald-500/12 text-emerald-700 hover:border-emerald-600/50 dark:text-emerald-200"
                                        : "border-[var(--border)] bg-surface text-foreground/50 hover:border-burgundy/35 hover:text-burgundy"
                                    }`}
                                    aria-label={`${isUnsubscribedContact ? "Dezabonat din campanii" : isContactActive ? "Activ în campanii" : "Inactiv în campanii"} pentru ${recipient.email}`}
                                    title={
                                      isUnsubscribedContact
                                        ? "Contactul s-a dezabonat și nu poate fi reactivat din listă."
                                        : isEditingContact
                                        ? "Salvează sau anulează editarea înainte de schimbarea statusului."
                                        : undefined
                                    }
                                  >
                                    {isUnsubscribedContact ? "Stop" : isContactActive ? "Da" : "Nu"}
                                  </button>
                                  <span className="rounded-full border border-[var(--border)] bg-surface px-2.5 py-1 text-[9px] font-bold uppercase tracking-wider text-foreground/55">
                                    {campaignRecipientStatusLabel(recipient.status)}
                                  </span>
                                </div>
                              )}
                            </td>
                            <td className="px-4 py-2.5 align-top">
                              <div className="grid min-w-[8.5rem] grid-cols-3 overflow-hidden rounded-xl border border-[var(--border)] bg-surface text-center">
                                <span className="border-r border-[var(--border)] px-2 py-1.5"><strong className="block text-foreground">{recipient.openCount ?? 0}</strong><span className="text-[9px] font-bold uppercase tracking-wider text-foreground/45">desch.</span></span>
                                <span className="border-r border-[var(--border)] px-2 py-1.5"><strong className="block text-foreground">{recipient.clickCount ?? 0}</strong><span className="text-[9px] font-bold uppercase tracking-wider text-foreground/45">click</span></span>
                                <span className="px-2 py-1.5"><strong className="block text-foreground">{recipient.viewCount ?? 0}</strong><span className="text-[9px] font-bold uppercase tracking-wider text-foreground/45">video</span></span>
                              </div>
                            </td>
                            <td className="px-4 py-2.5 align-top">
                              <div className="grid min-w-[7rem] grid-cols-2 overflow-hidden rounded-xl border border-[var(--border)] bg-surface text-center">
                                <span className="border-r border-[var(--border)] px-2 py-1.5"><strong className="block text-foreground">{recipient.replyCount ?? 0}</strong><span className="text-[9px] font-bold uppercase tracking-wider text-foreground/45">reply</span></span>
                                <span className="px-2 py-1.5"><strong className="block text-foreground">{recipient.calendlyClickCount ?? 0}</strong><span className="text-[9px] font-bold uppercase tracking-wider text-foreground/45">cal.</span></span>
                              </div>
                            </td>
                            <td className="px-4 py-2.5 align-top">
                              <span className="rounded-full bg-burgundy/10 border border-burgundy/20 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-burgundy shadow-sm">
                                {recipient.outcome ?? "pending"}
                              </span>
                            </td>
                            <td className="px-4 py-2.5 align-top">
                              <div className="flex justify-end gap-2">
                                {isEditingContact ? (
                                  <>
                                    <IconButton
                                      label={savingContactId === recipient.id ? "Se salvează contactul" : `Salvează ${recipient.email}`}
                                      tone="success"
                                      disabled={savingContactId === recipient.id}
                                      onClick={() => saveContact(recipient)}
                                    >
                                      <SaveIcon />
                                    </IconButton>
                                    <IconButton
                                      label={`Anulează editarea pentru ${recipient.email}`}
                                      disabled={savingContactId === recipient.id}
                                      onClick={() => cancelEditingContact(recipient.id)}
                                    >
                                      <CloseIcon />
                                    </IconButton>
                                  </>
                                ) : (
                                  <>
                                    <IconButton
                                      label={`Editează ${recipient.email}`}
                                      onClick={() => startEditingContact(recipient)}
                                    >
                                      <EditIcon />
                                    </IconButton>
                                    <IconButton
                                      label={deletingContactId === recipient.id ? "Se șterge contactul" : `Șterge ${recipient.email}`}
                                      tone="danger"
                                      disabled={deletingContactId === recipient.id}
                                      onClick={() => deleteContact(recipient)}
                                    >
                                      <TrashIcon />
                                    </IconButton>
                                  </>
                                )}
                              </div>
                            </td>
                          </tr>
                        );
                      })
                    ) : (
                      <tr>
                        <td colSpan={7} className="px-6 py-12 text-center text-foreground/50 text-sm font-medium">
                          <p>Niciun contact înregistrat încă.</p>
                          <div className="mt-4 flex items-center justify-center gap-3">
                            <span className="text-foreground/40">Importă un fișier CSV sau</span>
                        <button
                          onClick={() => {
                            setShowManualAddModal(true);
                            setParams({ tab: "campaigns", modal: "add-contact" }, "push");
                          }}
                          className="tap-soft rounded-full border border-[var(--border)] bg-surface px-3 py-1.5 text-xs font-bold text-burgundy hover:border-burgundy/45 hover:text-burgundy-dark"
                        >
                          adaugă manual
                        </button>
                          </div>
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
                </div>
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
                      onChange={(e) => {
                        setSearchQuery(e.target.value);
                        setParam("q", e.target.value, "replace");
                      }}
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
                        <IconButton
                          label="Editează șablonul"
                          onClick={() => setIsEditing(true)}
                          disabled={isLoadingTemplates}
                        >
                          <EditIcon />
                        </IconButton>
                        <button
                          onClick={handleCreateTemplateVersion}
                          disabled={isLoadingTemplates}
                          className="tap-soft rounded-full border border-[var(--border)] bg-surface px-4 py-2 text-xs font-bold text-foreground/70 hover:border-burgundy/40 hover:text-burgundy transition-all shadow-sm"
                        >
                          Versiune nouă
                        </button>
                        <IconButton
                          label="Șterge șablonul"
                          tone="danger"
                          onClick={handleDeleteTemplate}
                          disabled={isLoadingTemplates}
                        >
                          <TrashIcon />
                        </IconButton>
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

                  <label className="block">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-2 block">Titlu mare în email</span>
                    <input
                      type="text"
                      disabled={!isEditing}
                      value={isEditing ? editHeading : parseEmailTemplateEditorDraft(selectedTemplate.body, selectedTemplate.subject).heading}
                      onChange={(e) => setEditHeading(e.target.value)}
                      className="control-input w-full py-3 disabled:opacity-60"
                    />
                  </label>

                  <label className="block flex-1 flex flex-col">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-2 block">Corp email</span>
                    {isEditing ? (
                      <div className="mb-2 flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => setEditBody((current) => `${current.trim() ? `${current.trim()}\n\n` : ""}${DEFAULT_ACTION_TOKEN}`)}
                          className="tap-soft rounded-full border border-[var(--border)] bg-surface px-3 py-1.5 text-[10px] font-bold text-foreground/65 hover:border-burgundy/35 hover:text-burgundy"
                        >
                          Adaugă buton link
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditBody((current) => `${current.trim() ? `${current.trim()}\n\n` : ""}${DEFAULT_VIDEO_TOKEN}`)}
                          className="tap-soft rounded-full border border-[var(--border)] bg-surface px-3 py-1.5 text-[10px] font-bold text-foreground/65 hover:border-burgundy/35 hover:text-burgundy"
                        >
                          Adaugă video
                        </button>
                      </div>
                    ) : null}
                    <textarea
                      disabled={!isEditing}
                      value={isEditing ? editBody : parseEmailTemplateEditorDraft(selectedTemplate.body, selectedTemplate.subject).body}
                      onChange={(e) => setEditBody(e.target.value)}
                      className="control-input min-h-[200px] w-full flex-1 resize-none py-4 leading-relaxed disabled:opacity-60"
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
                      <p><strong className="text-foreground/80">De la:</strong> Andrei Văcaru</p>
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

                <label className="mt-5 block rounded-xl border border-[var(--border)] bg-surface-muted p-4">
                  <span className="mb-2 block text-[10px] font-bold uppercase tracking-wider text-foreground/60">
                    Link Calendly pentru previzualizare
                  </span>
                  <input
                    type="url"
                    value={previewCalendlyUrl}
                    onChange={(event) => setPreviewCalendlyUrl(event.target.value)}
                    className="control-input w-full py-3 font-mono text-xs"
                    placeholder="https://calendly.com/andreivacaru/intalnire-de-apropiere"
                  />
                  <span className="mt-2 block text-[11px] font-medium leading-relaxed text-foreground/55">
                    Folosit pentru tag-ul <code className="rounded bg-foreground/5 px-1">{`{calendly_url}`}</code> în previzualizare. La trimitere, backendul inserează linkul real configurat pentru campanii.
                  </span>
                </label>

                <div className="mt-5 rounded-xl bg-surface-muted p-4 border border-[var(--border)]">
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 text-burgundy/60">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                    </div>
                    <div>
                      <p className="text-[10px] font-bold uppercase tracking-wider text-foreground/60 mb-1">Informație utilă</p>
                      <p className="text-[11px] text-foreground/60 leading-relaxed font-medium">
                        Tag-urile ca <code className="bg-foreground/5 px-1 rounded mx-0.5">{`{first_name}`}</code> și <code className="bg-foreground/5 px-1 rounded mx-0.5">{`{calendly_url}`}</code> sunt înlocuite automat la expediere. Puteți formata corpul emailului folosind <strong className="text-foreground">**text**</strong> pentru bold și <span className="text-burgundy underline">[linkuri](url)</span>.
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
        <ModalLayer
          labelledBy="campaign-modal-title"
          onClose={() => {
            if (!isCreatingCampaign) closeCampaignModal();
          }}
          closeOnBackdrop={!isCreatingCampaign}
          panelClassName="flex h-[88vh] max-w-6xl flex-col overflow-hidden p-0"
        >
            <div className="border-b border-[var(--border)] bg-surface-muted px-6 py-5">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80">
                  {editingCampaign ? "Editează campanie" : "Campanie nouă"}
                </p>
                <h2 id="campaign-modal-title" className="mt-2 text-xl font-bold text-foreground">Email campanie</h2>
                <p className="mt-2 max-w-2xl text-xs font-medium leading-relaxed text-foreground/55">
                  Configurează șablonul, Calendly și opțional video/thumbnail. Previewul din dreapta arată emailul pe care îl va vedea contactul.
                </p>
              </div>
              <button
                type="button"
                onClick={() => closeCampaignModal()}
                disabled={isCreatingCampaign}
                className="tap-soft rounded-full border border-[var(--border)] bg-surface px-3 py-1.5 text-xs font-bold text-foreground/60 hover:border-burgundy/30 hover:text-burgundy"
              >
                Închide
              </button>
            </div>
            </div>

            <form onSubmit={handleSaveCampaign} className="flex min-h-0 flex-1 flex-col">
              <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
                <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(22rem,0.82fr)]">
                  <div className="space-y-4">
                    <div className="rounded-xl border border-[var(--border)] bg-surface-muted p-4">
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
                            value={campaignSegment ?? ""}
                            onChange={(event) => {
                              setCampaignSegment(event.target.value ? event.target.value as CampaignSegmentKey : null);
                              setCampaignTemplateId("");
                            }}
                            className="control-input w-full py-3"
                          >
                            <option value="">Fără grup preselectat</option>
                            <option value="potential_customer">Prospect / client potențial</option>
                            <option value="past_customer">Client vechi / existent</option>
                          </select>
                        </label>
                      </div>

                      <label className="mt-4 block">
                        <span className="mb-1 block text-xs font-bold uppercase tracking-wider text-foreground/60">Șablon email</span>
                        <select
                          value={campaignTemplateId}
                          onChange={(event) => {
                            const nextTemplate = campaignTemplates.find((template) => template.id === event.target.value);
                            setCampaignTemplateId(event.target.value);
                            if (nextTemplate) {
                              setCampaignSubject(nextTemplate.subject);
                              setCampaignBody(nextTemplate.body);
                              setCampaignPlainBody(htmlToPlainText(nextTemplate.body));
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
                    </div>

                    <div className="rounded-xl border border-[var(--border)] bg-surface-muted p-4">
                      <label className="block">
                        <span className="mb-1 block text-xs font-bold uppercase tracking-wider text-foreground/60">Subiect</span>
                        <input
                          value={campaignSubject}
                          onChange={(event) => setCampaignSubject(event.target.value)}
                          className="control-input w-full py-3"
                        />
                      </label>

                      <div className="mt-4 rounded-xl border border-[var(--border)] bg-surface px-4 py-3">
                        <p className="text-xs font-bold uppercase tracking-wider text-foreground/60">Conținut email</p>
                        <p className="mt-1 text-sm font-semibold leading-6 text-foreground/72">
                          {campaignTemplateId
                            ? "Șablonul selectat este folosit în preview și la trimitere. Poți ajusta textul fără să lucrezi direct în HTML."
                            : "Scrie mesajul principal. Codruț îl așază în shell-ul de email la trimitere."}
                        </p>
                        <label className="mt-3 block rounded-xl border border-[var(--border)] bg-surface-muted p-3">
                          <span className="block text-[10px] font-bold uppercase tracking-[0.18em] text-burgundy/75">
                            Andrei Văcaru
                          </span>
                          <span className="mt-1 block text-xs font-bold uppercase tracking-wider text-foreground/60">
                            Mesaj email
                          </span>
                          <textarea
                            value={campaignPlainBody}
                            onChange={(event) => {
                              setCampaignPlainBody(event.target.value);
                              setCampaignBody(plainCampaignContentToHtml(event.target.value));
                            }}
                            rows={8}
                            placeholder="Scrie mesajul emailului aici. Folosește rânduri libere pentru paragrafe."
                            className="mt-2 min-h-[13rem] w-full resize-y rounded-xl border border-[var(--border)] bg-surface px-3 py-3 text-sm leading-6 text-foreground shadow-inner outline-none focus:border-burgundy/45 focus:ring-2 focus:ring-burgundy/10"
                          />
                        </label>
                        <details className="mt-3 group">
                          <summary className="tap-soft flex cursor-pointer list-none items-center justify-between rounded-full border border-[var(--border)] bg-surface-muted px-4 py-2 text-xs font-bold text-foreground/65 transition hover:border-burgundy/30 hover:text-burgundy">
                            <span>Editor HTML avansat</span>
                            <span className="text-foreground/40 transition group-open:rotate-180">⌄</span>
                          </summary>
                          <label className="mt-3 block">
                            <span className="mb-1 block text-xs font-bold uppercase tracking-wider text-foreground/60">Corp email</span>
                            <textarea
                              value={campaignBody}
                              onChange={(event) => {
                                setCampaignBody(event.target.value);
                                setCampaignPlainBody(htmlToPlainText(event.target.value));
                              }}
                              rows={7}
                              placeholder="Alege un șablon sau scrie corpul emailului."
                              className="control-input max-h-[18rem] min-h-[11rem] w-full resize-y py-3 font-mono text-xs leading-relaxed"
                            />
                          </label>
                        </details>
                      </div>
                    </div>

                    <div className="rounded-xl border border-[var(--border)] bg-surface-muted p-4">
                      <div className="grid gap-4 md:grid-cols-2">
                        <label className="block">
                          <span className="mb-1 block text-xs font-bold uppercase tracking-wider text-foreground/60">Link video (opțional)</span>
                          <input
                            type="url"
                            value={campaignVideoUrl}
                            onChange={(event) => setCampaignVideoUrl(event.target.value)}
                            placeholder="https://vimeo.com/..."
                            className="control-input w-full py-3"
                          />
                        </label>
                        <label className="block">
                          <span className="mb-1 block text-xs font-bold uppercase tracking-wider text-foreground/60">Landing page Codruț (opțional)</span>
                          <input
                            type="url"
                            value={campaignLandingUrl}
                            onChange={(event) => setCampaignLandingUrl(event.target.value)}
                            placeholder="Gol = direct la Vimeo"
                            className="control-input w-full py-3"
                          />
                        </label>
                      </div>

                      <div className="mt-4">
                        <div className="mb-2 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
                          <div>
                            <span className="block text-xs font-bold uppercase tracking-wider text-foreground/60">Thumbnail (opțional)</span>
                            <p className="mt-1 text-[11px] font-medium text-foreground/50">Necesar doar pentru campaniile cu video.</p>
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
                          aria-label="Thumbnail campanie"
                          className="control-input w-full py-3"
                        />
                        {campaignAssetMessage ? (
                          <p className="mt-2 text-xs font-semibold text-foreground/62">{campaignAssetMessage}</p>
                        ) : null}
                      </div>
                    </div>
                  </div>

                  <aside className="space-y-4 lg:sticky lg:top-0 lg:self-start">
                    <div className="rounded-xl border border-[var(--border)] bg-surface-muted p-4">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-foreground/60">Video opțional</p>
                      {campaignThumbnailUrl ? (
                        <div className="relative mt-3 overflow-hidden rounded-xl border border-[var(--border)] bg-surface">
                          <Image
                            src={campaignThumbnailUrl}
                            alt="Previzualizare thumbnail campanie"
                            width={640}
                            height={320}
                            unoptimized
                            className="h-36 w-full object-cover"
                          />
                          <div aria-hidden="true" className="absolute inset-0 flex items-center justify-center bg-black/10">
                            <span className="flex h-14 w-14 items-center justify-center rounded-full border border-white/65 bg-white/86 shadow-xl backdrop-blur-sm">
                              <span className="ml-1 block h-0 w-0 border-y-[9px] border-l-[14px] border-y-transparent border-l-burgundy" />
                            </span>
                          </div>
                        </div>
                      ) : (
                        <div className="mt-3 flex h-36 items-center justify-center rounded-xl border border-dashed border-[var(--border)] bg-surface text-xs font-semibold text-foreground/45">
                          Fără video pentru această campanie
                        </div>
                      )}
                      {campaignMediaHasChanges ? (
                        <div
                          aria-live="polite"
                          className="mt-3 rounded-xl border border-burgundy/20 bg-burgundy/5 px-3 py-2 text-xs font-semibold leading-5 text-burgundy"
                        >
                          Preview actualizat. După salvare, această campanie va folosi linkul video și thumbnailul afișate aici.
                        </div>
                      ) : null}
                    </div>

                    <div className="rounded-xl border border-[var(--border)] bg-surface-muted p-4">
                      <p className="text-[10px] font-bold uppercase tracking-wider text-foreground/60">Preview email campanie</p>
                      <div className="mt-3 overflow-hidden rounded-xl border border-[var(--border)] bg-surface shadow-sm">
                        <div className="border-b border-[var(--border)] bg-surface-muted px-4 py-3">
                          <p className="text-[11px] font-semibold text-foreground/50">Către: {MOCK_REPLACEMENTS["{first_name}"]}</p>
                          <p className="mt-1 text-sm font-bold leading-5 text-foreground">{campaignPreview.subject || "Subiect campanie"}</p>
                        </div>
                        <div
                          className="max-h-[20rem] overflow-y-auto p-4 text-sm leading-relaxed text-foreground"
                          dangerouslySetInnerHTML={{ __html: campaignPreview.bodyHtml }}
                        />
                      </div>
                    </div>
                  </aside>
                </div>
              </div>

              {campaignMessage ? (
                <p aria-live="polite" className="mx-6 mb-3 rounded-xl bg-surface-muted px-3 py-2 text-xs font-semibold text-foreground/62">
                  {campaignMessage}
                </p>
              ) : null}

              <div className="flex shrink-0 justify-end gap-3 border-t border-[var(--border)] bg-surface-muted px-6 py-4">
                <button
                  type="button"
                  onClick={() => closeCampaignModal()}
                  className="tap-soft rounded-full px-4 py-2 font-bold text-foreground/60 hover:bg-surface"
                >
                  Anulează
                </button>
                <button type="submit" disabled={isCreatingCampaign} className="btn-primary !rounded-full !px-6 !py-2 !text-sm">
                  {isCreatingCampaign ? "Se salvează..." : editingCampaign ? "Salvează modificările" : "Salvează campania"}
                </button>
              </div>
            </form>
        </ModalLayer>
      )}

      {importDrafts.length > 0 && (
        <ModalLayer
          labelledBy="campaign-import-title"
          onClose={() => {
            if (!isImportingContacts) {
              setImportDrafts([]);
              setImportSheetName(null);
            }
          }}
          closeOnBackdrop={!isImportingContacts}
          panelClassName="flex max-w-6xl flex-col overflow-hidden p-0"
        >
            <div className="border-b border-[var(--border)] bg-surface-muted px-6 py-4">
              <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-burgundy/80">Import contacte</p>
                  <h2 id="campaign-import-title" className="mt-1 text-xl font-bold text-foreground">Previzualizare {importSheetName ?? "sheet"}</h2>
                  <p className="mt-1 text-xs font-semibold text-foreground/55">
                    {importDrafts.length} contacte · {activeImportDraftCount} active · {importDrafts.length - activeImportDraftCount} inactive · {invalidImportDraftCount} emailuri de corectat{duplicateImportDraftEmailCount > 0 ? ` · ${duplicateImportDraftEmailCount} duplicate` : ""}
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
                    <th className="px-3 py-2">Activ</th>
                    <th className="px-3 py-2">Nume</th>
                    <th className="px-3 py-2">Organizație</th>
                    <th className="px-3 py-2">Email</th>
                    <th className="px-3 py-2">Tip client</th>
                    <th className="px-3 py-2">Rând</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[var(--border)]">
                  {importDrafts.map((draft) => {
                    const invalidEmail = importDraftHasEmailError(draft);
                    return (
                      <tr key={draft.id} className={draft.send ? "bg-surface" : "bg-surface-muted/70 text-foreground/50"}>
                        <td className="px-3 py-2">
                          <button
                            type="button"
                            onClick={() => updateImportDraft(draft.id, "send", !draft.send)}
                            aria-pressed={draft.send}
                            aria-label={`${draft.send ? "Activ" : "Inactiv"} pentru importul rândului ${draft.rowNumber}`}
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
        </ModalLayer>
      )}

      {/* Manual Add Contact Modal */}
      {showManualAddModal && (
        <ModalLayer
          labelledBy="manual-contact-title"
          onClose={() => {
            if (!isAddingManual) closeManualAddModal();
          }}
          closeOnBackdrop={!isAddingManual}
          panelClassName="max-w-md"
        >
            <h2 id="manual-contact-title" className="text-xl font-bold text-foreground mb-4">Adaugă contact manual</h2>
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
                <button type="button" onClick={() => closeManualAddModal()} disabled={isAddingManual} className="rounded-full px-4 py-2 font-bold text-foreground/60 hover:bg-surface-muted disabled:opacity-50">Anulează</button>
                <button type="submit" disabled={isAddingManual} className="btn-primary !px-6 !py-2 !rounded-full !text-sm">
                  {isAddingManual ? "Se adaugă..." : "Adaugă contact"}
                </button>
              </div>
            </form>
        </ModalLayer>
      )}
    </div>
  );
}
