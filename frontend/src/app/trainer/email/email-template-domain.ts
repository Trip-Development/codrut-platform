import type { EmailCampaign, EmailTemplate } from "@/api/email";

export const MOCK_REPLACEMENTS: Record<string, string> = {
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
  "{legal_address}": "București, România",
};

export const DEFAULT_ACTION_TOKEN = "{action_button:Deschide chestionarele|{action_url}}";
export const DEFAULT_VIDEO_TOKEN = "{video_block}";

const EMAIL_PREVIEW_SHELL_OPEN =
  '<div style="font-family:Inter,Arial,sans-serif;max-width:620px;margin:0 auto;padding:28px;color:#2b211f;"><div style="border:1px solid #eadfdb;border-radius:18px;padding:28px;background:#fffdfb;"><p style="margin:0 0 8px;font-size:13px;font-weight:700;color:#890505;letter-spacing:.08em;text-transform:uppercase;">Andrei Văcaru</p>';
const EMAIL_PREVIEW_SHELL_CLOSE = "</div></div>";
const PROMOTIONAL_EMAIL_PREVIEW_SHELL_CLOSE =
  '</div><div style="margin-top:24px;padding-top:24px;border-top:1px solid #eadfdb;font-size:12px;line-height:1.5;color:#8c7e7b;text-align:center;"><p style="margin:0 0 8px;">Ai primit acest email deoarece ești abonat la actualizările noastre sau ești un client.</p><p style="margin:0 0 8px;"><a href="{unsubscribe_url}" style="color:#6d5f5b;text-decoration:underline;">Dezabonare</a></p><p style="margin:0;">{legal_address}</p></div></div>';
const EMAIL_HEADING_STYLE = "margin:0 0 16px;font-size:24px;line-height:1.25;";
const EMAIL_PARAGRAPH_STYLE = "margin:0 0 18px;font-size:15px;line-height:1.65;";
const EMAIL_BUTTON_STYLE = "display:inline-block;background:#890505;color:#ffffff;text-decoration:none;border-radius:12px;padding:13px 18px;font-weight:700;";

export function detectedPlaceholders(subject: string, body: string): string[] {
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

export function renderEditablePlaceholders(value: string): string {
  return value.replace(/\$\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "{$1}");
}

function replaceLiteral(value: string, literal: string | null | undefined, replacement: string): string {
  if (!literal) return value;
  const escapedLiteral = escapeHtmlAttribute(literal);
  return value.split(literal).join(replacement).split(escapedLiteral).join(replacement);
}

export function renderEditableCampaignBody(campaign: EmailCampaign): string {
  let body = renderEditablePlaceholders(campaign.html_body);
  body = replaceLiteral(body, campaign.landing_page_url ?? campaign.video_url, "{landing_page_url}");
  body = replaceLiteral(body, campaign.thumbnail_url, "{thumbnail_url}");
  body = replaceLiteral(body, campaign.video_url, "{video_url}");
  return body;
}

export function plainCampaignContentToHtml(value: string): string {
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
    // Invalid editor URLs become inert in preview instead of executing arbitrary schemes.
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
  const skipTexts = ["Andrei Văcaru", "Ai primit acest email deoarece", "Str. Exemplu Nr. 10"];

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
    "A", "B", "BR", "DIV", "EM", "H1", "H2", "H3", "IMG", "LI", "OL", "P", "SPAN",
    "STRONG", "TABLE", "TBODY", "TD", "TH", "THEAD", "TR", "UL",
  ]);
  const allowedAttributes = new Set(["alt", "class", "height", "href", "src", "style", "target", "width"]);
  const allowedUrlAttributes = new Set(["href", "src"]);
  const parser = new DOMParser();
  const document = parser.parseFromString(value, "text/html");

  Array.from(document.body.querySelectorAll("*")).forEach((node) => {
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
        node.setAttribute(attribute.name, sanitizePreviewHref(attribute.value));
      } else if (attributeName === "style" && /(javascript\s*:|expression\s*\(|url\s*\()/i.test(attribute.value)) {
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
  const shellClose = replacePreviewPlaceholders(PROMOTIONAL_EMAIL_PREVIEW_SHELL_CLOSE, {
    ...MOCK_REPLACEMENTS,
    ...replacements,
  });
  return `${EMAIL_PREVIEW_SHELL_OPEN}${bodyHtml || ""}${shellClose}`;
}

export function upsertEmailTemplate(templates: EmailTemplate[], template: EmailTemplate): EmailTemplate[] {
  const nextTemplates = [...templates];
  const existingIndex = nextTemplates.findIndex((item) => item.id === template.id);
  if (existingIndex >= 0) nextTemplates[existingIndex] = template;
  else nextTemplates.unshift(template);
  return nextTemplates;
}
