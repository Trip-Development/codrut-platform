import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  CampaignPersistenceError,
  type CampaignAssetUpload,
  type EmailCampaign,
  type EmailOpsSummary,
  type EmailTemplate,
} from "@/api/email";
import {
  EmailWorkspace,
} from "./EmailWorkspace";
import {
  buildStyledEmailTemplateBody,
  parseEmailTemplateEditorDraft,
  renderCampaignEmailPreviewShell,
  renderEmailTemplatePreviewBody,
  replacePreviewPlaceholders,
} from "./email-template-domain";
import {
  buildCampaignRecipientImport,
  buildCampaignRecipientImportDrafts,
  selectCampaignRecipientImportSheetName,
  uniqueCampaignImportDrafts,
} from "./contact-import-domain";

const emailApiMocks = vi.hoisted(() => ({
  bulkCreateCampaignRecipientsOnServer: vi.fn(),
  buildVideoCampaignCreatePayload: vi.fn(),
  createCampaignOnServer: vi.fn(),
  createEmailTemplateOnServer: vi.fn(),
  deleteCampaignAssetOnServer: vi.fn(),
  deleteCampaignOnServer: vi.fn(),
  deleteCampaignRecipientOnServer: vi.fn(),
  deleteEmailTemplateOnServer: vi.fn(),
  getEmailOpsSummary: vi.fn(),
  listCampaignRecipientMembershipOnServer: vi.fn(),
  listCampaignsOnServer: vi.fn(),
  listEmailTemplatesOnServer: vi.fn(),
  replaceCampaignRecipientMembershipOnServer: vi.fn(),
  sendCampaignOnServer: vi.fn(),
  updateCampaignOnServer: vi.fn(),
  updateCampaignRecipientOnServer: vi.fn(),
  updateEmailTemplateOnServer: vi.fn(),
  uploadCampaignAssetOnServer: vi.fn(),
}));

const navigationMocks = vi.hoisted(() => ({
  searchParams: new URLSearchParams(),
  push: vi.fn(),
  replace: vi.fn(),
  prefetch: vi.fn(),
  back: vi.fn(),
  refresh: vi.fn(),
}));
const nativePushState = window.history.pushState.bind(window.history);
const nativeReplaceState = window.history.replaceState.bind(window.history);

const spreadsheetMocks = vi.hoisted(() => ({
  readSpreadsheetFile: vi.fn(),
}));

function applyNavigationHref(href: string) {
  navigationMocks.searchParams = new URLSearchParams(href.includes("?") ? href.split("?")[1] : "");
}

function expectCheckboxState(element: HTMLElement, checked: boolean) {
  expect(element.getAttribute("aria-checked")).toBe(checked ? "true" : "false");
}

function openCampaignControls(card: HTMLElement) {
  fireEvent.click(within(card).getByRole("button", { name: /Deschide/i }));
}

function chooseComboboxOption(card: HTMLElement, label: string, option: string | RegExp) {
  fireEvent.click(within(card).getByRole("combobox", { name: label }));
  fireEvent.click(screen.getByRole("option", { name: option }));
}

vi.mock("next/navigation", () => ({
  useRouter: () => navigationMocks,
  useSearchParams: () => navigationMocks.searchParams,
  usePathname: () => "/trainer/email",
}));

vi.mock("@/api/email", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/api/email")>();
  return {
    ...original,
    bulkCreateCampaignRecipientsOnServer: emailApiMocks.bulkCreateCampaignRecipientsOnServer,
    buildVideoCampaignCreatePayload: emailApiMocks.buildVideoCampaignCreatePayload,
    createCampaignOnServer: emailApiMocks.createCampaignOnServer,
    createEmailTemplateOnServer: emailApiMocks.createEmailTemplateOnServer,
    deleteCampaignAssetOnServer: emailApiMocks.deleteCampaignAssetOnServer,
    deleteCampaignOnServer: emailApiMocks.deleteCampaignOnServer,
    deleteCampaignRecipientOnServer: emailApiMocks.deleteCampaignRecipientOnServer,
    deleteEmailTemplateOnServer: emailApiMocks.deleteEmailTemplateOnServer,
    getEmailOpsSummary: emailApiMocks.getEmailOpsSummary,
    listCampaignRecipientMembershipOnServer: emailApiMocks.listCampaignRecipientMembershipOnServer,
    listCampaignsOnServer: emailApiMocks.listCampaignsOnServer,
    listEmailTemplatesOnServer: emailApiMocks.listEmailTemplatesOnServer,
    replaceCampaignRecipientMembershipOnServer: emailApiMocks.replaceCampaignRecipientMembershipOnServer,
    sendCampaignOnServer: emailApiMocks.sendCampaignOnServer,
    updateCampaignOnServer: emailApiMocks.updateCampaignOnServer,
    updateCampaignRecipientOnServer: emailApiMocks.updateCampaignRecipientOnServer,
    updateEmailTemplateOnServer: emailApiMocks.updateEmailTemplateOnServer,
    uploadCampaignAssetOnServer: emailApiMocks.uploadCampaignAssetOnServer,
  };
});

vi.mock("@/utils/spreadsheet-import", async (importOriginal) => {
  const original = await importOriginal<typeof import("@/utils/spreadsheet-import")>();
  return {
    ...original,
    readSpreadsheetFile: spreadsheetMocks.readSpreadsheetFile,
  };
});

beforeEach(() => {
  Object.values(emailApiMocks).forEach((mock) => mock.mockReset());
  spreadsheetMocks.readSpreadsheetFile.mockReset();
  navigationMocks.searchParams = new URLSearchParams();
  navigationMocks.push.mockReset();
  navigationMocks.replace.mockReset();
  navigationMocks.prefetch.mockReset();
  navigationMocks.back.mockReset();
  navigationMocks.refresh.mockReset();
  nativeReplaceState(null, "", "/trainer/email");
  vi.spyOn(window.history, "pushState").mockImplementation((data, unused, url) => {
    nativePushState(data, unused, url);
    if (url) applyNavigationHref(String(url));
  });
  vi.spyOn(window.history, "replaceState").mockImplementation((data, unused, url) => {
    nativeReplaceState(data, unused, url);
    if (url) applyNavigationHref(String(url));
  });
  navigationMocks.push.mockImplementation((href: string) => {
    applyNavigationHref(href);
  });
  navigationMocks.replace.mockImplementation((href: string) => {
    applyNavigationHref(href);
  });
  emailApiMocks.listCampaignsOnServer.mockResolvedValue([]);
  emailApiMocks.listCampaignRecipientMembershipOnServer.mockResolvedValue([]);
  emailApiMocks.replaceCampaignRecipientMembershipOnServer.mockResolvedValue([]);
  emailApiMocks.listEmailTemplatesOnServer.mockResolvedValue([]);
  emailApiMocks.getEmailOpsSummary.mockResolvedValue(makeEmailSummary());
  emailApiMocks.updateCampaignRecipientOnServer.mockResolvedValue({});
});

afterEach(() => {
  cleanup();
  document.body.style.overflow = "";
  vi.restoreAllMocks();
});

type CampaignRecipient = EmailOpsSummary["campaign"]["recipients"][number];

function makeCampaignRecipient(overrides: Partial<CampaignRecipient> = {}): CampaignRecipient {
  return {
    id: "recipient-1",
    company: "Demo Co",
    firstName: "Ioana",
    lastName: "Popescu",
    email: "ioana@example.com",
    clientType: "tip_2",
    status: "suppressed",
    openCount: 0,
    clickCount: 0,
    viewCount: 0,
    replyCount: 0,
    calendlyClickCount: 0,
    ...overrides,
  };
}

function makeEmailSummary(
  recipientStatus: CampaignRecipient["status"] = "suppressed",
  recipients?: CampaignRecipient[],
): EmailOpsSummary {
  return {
    metrics: [],
    assessmentRows: [],
    rules: [],
    campaign: {
      videoHost: {
        provider: "Vimeo",
        status: "ready",
        note: "Config pregătit.",
      },
      template: {
        subject: "Subiect",
        personalization: "Prenume",
        ctaPrimary: "CTA",
        ctaSecondary: "CTA secundar",
      },
      recipients: recipients ?? [makeCampaignRecipient({ status: recipientStatus })],
      weeklyReport: {
        cadence: "Săptămânal",
        metrics: [],
        notification: "Email",
      },
    },
  };
}

function makeCampaign(overrides: Partial<EmailCampaign> = {}): EmailCampaign {
  return {
    id: "campaign-1",
    name: "Campanie demo",
    segment: "potential_customer",
    status: "ready",
    subject: "Salut, {first_name}",
    html_body: "<p>Salut.</p>",
    text_body: "Salut.",
    ...overrides,
  };
}

function makeTemplate(overrides: Partial<EmailTemplate> = {}): EmailTemplate {
  return {
    id: "welcome@1",
    baseKey: "welcome",
    version: 1,
    name: "Invitație inițială",
    subject: "Bună, {first_name}",
    body: "<p>Bună.</p>",
    lane: "campaign",
    placeholders: ["{first_name}", "{action_url}"],
    ...overrides,
  };
}

describe("renderEmailTemplatePreviewBody", () => {
  it("escapes arbitrary HTML while preserving supported markdown", () => {
    const html = renderEmailTemplatePreviewBody(
      "Salut **Ioana**\n<script>alert('xss')</script>\n[calendar](javascript:alert(1)) [site](https://codrut.ro)",
    );

    expect(html).toContain("<strong>Ioana</strong>");
    expect(html).toContain("&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;");
    expect(html).not.toContain("<script>");
    expect(html).not.toContain("javascript:alert");
    expect(html).toContain('href="#"');
    expect(html).toContain('href="https://codrut.ro"');
  });

  it("renders saved html templates instead of escaping them as text", () => {
    const html = renderEmailTemplatePreviewBody(
      '<div><p>Bună, Ioana.</p><a href="https://codrut.ro">Activează</a><script>alert("x")</script></div>',
    );

    expect(html).toContain("<div><p>Bună, Ioana.</p>");
    expect(html).toContain('href="https://codrut.ro"');
    expect(html).not.toContain("&lt;div&gt;");
    expect(html).not.toContain("<script>");
  });

  it("preserves email-safe table checklist markup in previews", () => {
    const html = renderEmailTemplatePreviewBody(
      '<table role="presentation"><tbody><tr><td>✓</td><td>Exemplul sintetic a fost verificat</td></tr><tr><td>✗</td><td>Exemplul sintetic necesită revizuire</td></tr></tbody></table>',
    );

    expect(html).toContain("<table");
    expect(html).toContain("<td>✓</td>");
    expect(html).toContain("Exemplul sintetic necesită revizuire");
  });

  it("sanitizes unsafe html preview attributes and urls", () => {
    const html = renderEmailTemplatePreviewBody(
      '<div><a href=javascript:alert(1) onclick="alert(2)">Click</a><img src="JaVaScRiPt:alert(3)" onerror="alert(4)" style="background:url(javascript:alert(5))" /></div>',
    );

    expect(html).toContain('href="#"');
    expect(html).toContain('src="#"');
    expect(html).not.toContain("javascript:");
    expect(html).not.toContain("onclick");
    expect(html).not.toContain("onerror");
    expect(html).not.toContain("background:url");
  });

  it("previews both brace and backend-style placeholders cleanly", () => {
    expect(replacePreviewPlaceholders("Bună, {first_name}.")).toBe("Bună, Ioana.");
    expect(replacePreviewPlaceholders("Bună, ${first_name}.")).toBe("Bună, Ioana.");
    expect(replacePreviewPlaceholders("Programează aici: {calendly_url}.")).toContain("calendly.com/andreivacaru");
    expect(replacePreviewPlaceholders("Sediu: ${legal_address}.")).toBe("Sediu: București, România.");
  });

  it("wraps plain campaign previews in the branded promotional email shell", () => {
    const html = renderCampaignEmailPreviewShell("<p>Mesaj simplu</p>", {
      "{unsubscribe_url}": "https://codrut.example/unsubscribe/demo",
    });

    expect(html).toContain("Andrei Văcaru");
    expect(html).toContain("<p>Mesaj simplu</p>");
    expect(html).toContain("Ai primit acest email deoarece");
    expect(html).toContain("https://codrut.example/unsubscribe/demo");
    expect(html).toContain("București, România");
    expect(html).not.toContain("{legal_address}");
    expect(html).not.toContain("Str. Exemplu");
  });

  it("does not double-wrap campaign previews that already have the branded shell", () => {
    const wrapped = renderCampaignEmailPreviewShell(
      '<div style="font-family:Inter,Arial,sans-serif"><p>Andrei Văcaru</p><p>Mesaj</p></div>',
    );

    expect(wrapped.match(/Andrei Văcaru/g)).toHaveLength(1);
  });

  it("extracts a friendly editor draft from styled templates and keeps subject separate from heading", () => {
    const draft = parseEmailTemplateEditorDraft(
      buildStyledEmailTemplateBody({
        heading: "Titlul vizibil din email",
        body: "Salut {first_name}.\n\n{video_block}\n\n{action_button:Deschide chestionarele|{action_url}}",
        lane: "transactional",
      }),
      "Subiect oficial",
    );

    expect(draft.heading).toBe("Titlul vizibil din email");
    expect(draft.body).toContain("Salut {first_name}.");
    expect(draft.body).toContain("{video_block}");
    expect(draft.body).toContain("{action_button:Deschide chestionarele|{action_url}}");

    const html = buildStyledEmailTemplateBody({
      heading: draft.heading,
      body: draft.body,
      lane: "transactional",
    });
    expect(html).toContain("Titlul vizibil din email");
    expect(html).toContain("{thumbnail_url}");
    expect(html).toContain('href="{action_url}"');
    expect(html).toContain("Andrei Văcaru");
  });

  it("keeps legacy campaign content when the footer shares its wrapper", () => {
    const draft = parseEmailTemplateEditorDraft(
      [
        "<div>",
        "<p>Mesajul important rămâne.</p>",
        "<p>Ai primit acest email deoarece ești abonat.</p>",
        "<p><a href=\"{unsubscribe_url}\">Dezabonare</a></p>",
        "</div>",
      ].join(""),
      "",
    );

    expect(draft.body).toContain("Mesajul important rămâne.");
    expect(draft.body).not.toContain("Ai primit acest email deoarece");
    expect(draft.body).not.toContain("Dezabonare");
  });
});

describe("EmailWorkspace campaign contacts", () => {
  it("shows template catalog load failures instead of dropping the error", async () => {
    emailApiMocks.listEmailTemplatesOnServer.mockRejectedValueOnce(new Error("Șabloanele nu au putut fi citite."));

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    expect(await screen.findByText("Șabloanele nu au putut fi citite.")).toBeTruthy();
  });

  it("uses the shared button primitive for template catalog cards", async () => {
    const template = makeTemplate();
    navigationMocks.searchParams = new URLSearchParams("tab=templates");
    emailApiMocks.listEmailTemplatesOnServer.mockResolvedValueOnce([template]);

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    const catalogCard = await screen.findByRole("button", { name: "Deschide șablon Invitație inițială" });
    expect(catalogCard.getAttribute("data-slot")).toBe("button");
    expect(catalogCard.getAttribute("data-variant")).toBe("outline");
  });

  it("locks template creation and prevents duplicate create requests", async () => {
    const createRequest = createDeferred<EmailTemplate>();
    navigationMocks.searchParams = new URLSearchParams("tab=templates");
    emailApiMocks.createEmailTemplateOnServer.mockReturnValueOnce(createRequest.promise);

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    const createButton = await screen.findByRole("button", { name: "Creează șablon" });
    fireEvent.click(createButton);
    fireEvent.click(createButton);

    expect(await screen.findAllByText("Creăm șablonul")).toHaveLength(2);
    expect(emailApiMocks.createEmailTemplateOnServer).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("button", { name: "Creăm șablonul" })).toHaveProperty("disabled", true);

    createRequest.resolve(makeTemplate({ id: "template_local_1@1", baseKey: "template_local_1" }));

    await waitFor(() => {
      expect(screen.queryByText("Creăm șablonul")).toBeNull();
    });
  });

  it("locks template saving and prevents duplicate save requests", async () => {
    const template = makeTemplate();
    const saveRequest = createDeferred<EmailTemplate>();
    navigationMocks.searchParams = new URLSearchParams("tab=templates");
    emailApiMocks.listEmailTemplatesOnServer.mockResolvedValueOnce([template]);
    emailApiMocks.updateEmailTemplateOnServer.mockReturnValueOnce(saveRequest.promise);

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    fireEvent.click(await screen.findByRole("button", { name: "Deschide șablon Invitație inițială" }));
    fireEvent.click(await screen.findByRole("button", { name: "Editează șablonul" }));
    const subjectInput = await screen.findByLabelText("Subiect email") as HTMLInputElement;
    fireEvent.change(subjectInput, { target: { value: "Subiect nou" } });

    const saveButton = screen.getByRole("button", { name: "Salvează" });
    fireEvent.click(saveButton);
    fireEvent.click(saveButton);

    expect(await screen.findByText("Actualizăm șablonul")).toBeTruthy();
    expect(emailApiMocks.updateEmailTemplateOnServer).toHaveBeenCalledTimes(1);
    expect(subjectInput.disabled).toBe(true);
    expect(screen.getByRole("button", { name: "Salvăm" })).toHaveProperty("disabled", true);

    saveRequest.resolve(makeTemplate({ subject: "Subiect nou" }));

    await waitFor(() => {
      expect(screen.queryByText("Actualizăm șablonul")).toBeNull();
    });
  });

  it("removes the global archive tab and normalizes legacy delivery links", async () => {
    navigationMocks.searchParams = new URLSearchParams("tab=delivery");
    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    expect(screen.queryByRole("button", { name: "Arhivă globală" })).toBeNull();
    expect(screen.queryByText("Invitațiile live se operează din companie")).toBeNull();
    expect(screen.getByRole("button", { name: "Șabloane" })).toBeTruthy();

    await waitFor(() => {
      expect(`${window.location.pathname}${window.location.search}`).toBe("/trainer/email");
    });
  });

  it("shows Campanii, Contacte and Șabloane once in a single Comunicare navigation", () => {
    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    const navigation = screen.getByRole("navigation", { name: "Navigare Comunicare" });
    expect(screen.getByRole("heading", { name: "Comunicare" })).toBeTruthy();
    expect(within(navigation).getAllByRole("button")).toHaveLength(3);
    expect(within(navigation).getByRole("button", { name: "Campanii" })).toBeTruthy();
    expect(within(navigation).getByRole("button", { name: "Contacte" })).toBeTruthy();
    expect(within(navigation).getByRole("button", { name: "Campanii" }).getAttribute("aria-current")).toBe("page");

    fireEvent.click(within(navigation).getByRole("button", { name: "Campanii" }));
    expect(`${window.location.pathname}${window.location.search}`).toBe("/trainer/email");
    fireEvent.click(within(navigation).getByRole("button", { name: "Contacte" }));
    expect(`${window.location.pathname}${window.location.search}`).toBe(
      "/trainer/email?view=contacts",
    );
    fireEvent.click(within(navigation).getByRole("button", { name: "Șabloane" }));
    expect(`${window.location.pathname}${window.location.search}`).toBe(
      "/trainer/email?tab=templates",
    );
  });

  it("shows a customer-facing contact source instead of the local preview sentinel", async () => {
    render(React.createElement(EmailWorkspace, {
      initialSummary: makeEmailSummary("ready", [makeCampaignRecipient({
        status: "ready",
        source: "local_preview",
      })]),
    }));

    fireEvent.click(screen.getByRole("button", { name: "Contacte" }));

    expect(await screen.findByText("Import contacte")).toBeTruthy();
    expect(screen.queryByText("local preview")).toBeNull();
  });

  it("keeps campaign modal fields focused while typing", async () => {
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&modal=new-campaign");
    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    const nameInput = await screen.findByLabelText("Nume campanie");
    nameInput.focus();
    fireEvent.change(nameInput, { target: { value: "A" } });
    expect(document.activeElement).toBe(nameInput);
    fireEvent.change(nameInput, { target: { value: "AB" } });
    expect(document.activeElement).toBe(nameInput);
    expect((nameInput as HTMLInputElement).value).toBe("AB");

    const subjectInput = screen.getByLabelText("Subiect");
    fireEvent.click(subjectInput);
    subjectInput.focus();
    fireEvent.change(subjectInput, { target: { value: "Salut A" } });
    fireEvent.change(subjectInput, { target: { value: "Salut AB" } });
    expect((subjectInput as HTMLInputElement).value).toBe("Salut AB");

    const messageInput = screen.getByLabelText(/Mesaj email/);
    expect(messageInput.getAttribute("data-slot")).toBe("textarea");
    fireEvent.change(messageInput, { target: { value: "Mesaj simplu" } });
    expect((messageInput as HTMLTextAreaElement).value).toBe("Mesaj simplu");
    const advancedEditorSummary = screen.getByText("Editor HTML avansat");
    expect((advancedEditorSummary.closest("details") as HTMLDetailsElement | null)?.open).toBe(false);

    fireEvent.click(advancedEditorSummary);
    expect((advancedEditorSummary.closest("details") as HTMLDetailsElement | null)?.open).toBe(true);
    const bodyInput = screen.getByLabelText("Corp email");
    expect(bodyInput.getAttribute("data-slot")).toBe("textarea");
    fireEvent.change(bodyInput, { target: { value: "Primul rând" } });
    fireEvent.change(bodyInput, { target: { value: "Primul rând\nAl doilea rând" } });
    expect((bodyInput as HTMLTextAreaElement).value).toBe("Primul rând\nAl doilea rând");
  });

  it("preserves campaign video and Calendly blocks when editing friendly text", async () => {
    const template = makeTemplate({
      id: "campaign-rich@1",
      baseKey: "campaign-rich",
      name: "Campanie cu video",
      audience: "potential_customer",
      body: buildStyledEmailTemplateBody({
        heading: "Material pentru echipă",
        body: [
          "Salut {first_name}.",
          "{video_block}",
          "{calendly_button:Programează o discuție}",
        ].join("\n\n"),
        lane: "campaign",
      }),
    });
    const savedCampaign = makeCampaign({
      id: "campaign-rich",
      name: "Campanie video leadership",
    });
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&modal=new-campaign");
    emailApiMocks.listEmailTemplatesOnServer.mockResolvedValue([template]);
    emailApiMocks.buildVideoCampaignCreatePayload.mockImplementation((draft) => ({
      name: draft.name,
      segment: draft.segment,
      subject: draft.subject,
      html_body: draft.htmlBody ?? "",
      text_body: draft.textBody ?? "",
    }));
    emailApiMocks.createCampaignOnServer.mockResolvedValue(savedCampaign);

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    const templateSelect = await screen.findByLabelText("Șablon email");
    fireEvent.change(templateSelect, { target: { value: template.id } });
    const messageInput = screen.getByLabelText("Mesaj email") as HTMLTextAreaElement;
    expect(messageInput.value).toContain("{video_block}");
    expect(messageInput.value).toContain("{calendly_button:Programează o discuție}");

    fireEvent.change(messageInput, {
      target: { value: `${messageInput.value}\n\nText ajustat pentru campanie.` },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvează campania" }));

    await waitFor(() => expect(emailApiMocks.buildVideoCampaignCreatePayload).toHaveBeenCalled());
    const draft = emailApiMocks.buildVideoCampaignCreatePayload.mock.calls[0]?.[0];
    expect(draft.htmlBody).toContain('src="{thumbnail_url}"');
    expect(draft.htmlBody).toContain('href="{landing_page_url}"');
    expect(draft.htmlBody).toContain('href="{calendly_url}"');
    expect(draft.htmlBody).toContain("Text ajustat pentru campanie.");
    expect(draft.htmlBody).not.toContain("{legal_address}</p><p");
  });

  it("shows a newly created campaign after saving from the contacts view", async () => {
    const savedCampaign = makeCampaign({
      id: "campaign-visible",
      name: "Campanie vizibilă",
      segment: null,
      subject: "Subiect vizibil",
    });

    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&modal=new-campaign");
    emailApiMocks.listCampaignsOnServer
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([savedCampaign]);
    emailApiMocks.buildVideoCampaignCreatePayload.mockImplementation((draft) => ({
      name: draft.name.trim(),
      segment: draft.segment,
      subject: draft.subject,
      html_body: "<p>Bună, ${first_name}.</p>",
      text_body: "Bună, ${first_name}.",
      thumbnail_url: draft.thumbnailUrl || undefined,
    }));
    emailApiMocks.createCampaignOnServer.mockResolvedValue(savedCampaign);

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    fireEvent.change(await screen.findByLabelText("Nume campanie"), {
      target: { value: "Campanie vizibilă" },
    });
    fireEvent.change(screen.getByLabelText("Imagine campanie"), {
      target: { value: "https://cdn.codrut.ro/thumb-only.jpg" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvează campania" }));

    await waitFor(() => {
      expect(emailApiMocks.createCampaignOnServer).toHaveBeenCalledWith(expect.objectContaining({
        thumbnail_url: "https://cdn.codrut.ro/thumb-only.jpg",
      }));
    });
    expect(await screen.findByText("Campanie vizibilă")).toBeTruthy();
    expect(screen.getByText(/Subiect vizibil/)).toBeTruthy();
    expect(screen.getByText("Campania „Campanie vizibilă” a fost creată.")).toBeTruthy();
    expect(`${window.location.pathname}${window.location.search}`).toBe(
      "/trainer/email?tab=campaigns&view=campaigns",
    );
  });

  it("shows field-specific campaign errors and focuses the first invalid field", async () => {
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&modal=new-campaign");
    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    const nameInput = await screen.findByLabelText("Nume campanie") as HTMLInputElement;
    fireEvent.change(nameInput, { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Subiect"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Link video (opțional)"), { target: { value: "javascript:alert(1)" } });
    fireEvent.change(screen.getByLabelText("Landing page Cody (opțional)"), { target: { value: "ftp://example.com" } });
    fireEvent.change(screen.getByLabelText("Imagine campanie"), { target: { value: "not-a-url" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvează campania" }));

    expect(await screen.findByText("Adaugă un nume pentru campanie.")).toBeTruthy();
    expect(screen.getByText("Adaugă subiectul emailului.")).toBeTruthy();
    expect(screen.getByText("Linkul video trebuie să înceapă cu http:// sau https://.")).toBeTruthy();
    expect(screen.getByText("Linkul imaginii trebuie să înceapă cu http:// sau https://.")).toBeTruthy();
    expect(screen.getByText("Linkul paginii trebuie să înceapă cu http:// sau https://.")).toBeTruthy();
    expect(screen.getByText("Corectează 5 câmpuri înainte de salvare:")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Nume campanie" })).toBeTruthy();
    expect(nameInput.getAttribute("aria-invalid")).toBe("true");
    await waitFor(() => expect(document.activeElement).toBe(nameInput));
    expect(emailApiMocks.buildVideoCampaignCreatePayload).not.toHaveBeenCalled();
    expect(emailApiMocks.createCampaignOnServer).not.toHaveBeenCalled();
  });

  it("persists a video draft without a thumbnail and keeps it blocked only for sending", async () => {
    const savedCampaign = makeCampaign({
      id: "campaign-video-draft",
      name: "Video în lucru",
      status: "draft",
      video_url: "https://video.example/demo",
    });
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&modal=new-campaign");
    emailApiMocks.listCampaignsOnServer
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([savedCampaign]);
    emailApiMocks.buildVideoCampaignCreatePayload.mockImplementation((draft) => ({
      name: draft.name.trim(),
      segment: draft.segment,
      subject: draft.subject,
      html_body: "<p>Draft</p>",
      text_body: "Draft",
    }));
    emailApiMocks.createCampaignOnServer.mockResolvedValue(savedCampaign);

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));
    fireEvent.change(await screen.findByLabelText("Nume campanie"), { target: { value: "Video în lucru" } });
    fireEvent.change(screen.getByLabelText("Link video (opțional)"), { target: { value: "https://video.example/demo" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvează campania" }));

    await waitFor(() => {
      expect(emailApiMocks.buildVideoCampaignCreatePayload).toHaveBeenCalledWith(expect.objectContaining({ videoUrl: "" }));
      expect(emailApiMocks.createCampaignOnServer).toHaveBeenCalledWith(expect.objectContaining({
        video_url: "https://video.example/demo",
        thumbnail_url: undefined,
      }));
    });
    expect(await screen.findByText("Campania „Video în lucru” a fost creată.")).toBeTruthy();

    const campaignCard = (await screen.findByText("Video în lucru")).closest("article");
    expect(campaignCard).not.toBeNull();
    expect(within(campaignCard as HTMLElement).getByRole("button", { name: /Închide/i }).getAttribute("aria-expanded")).toBe("true");
    expect(within(campaignCard as HTMLElement).getByText("Adaugă o imagine de previzualizare înainte de a trimite campania video.")).toBeTruthy();
    expect((within(campaignCard as HTMLElement).getByRole("button", { name: "Trimite campania" }) as HTMLButtonElement).disabled).toBe(true);
    expect(emailApiMocks.sendCampaignOnServer).not.toHaveBeenCalled();
  });

  it("retains campaign values and retries a failed network save", async () => {
    const savedCampaign = makeCampaign({
      id: "campaign-retried",
      name: "Campanie păstrată",
      subject: "Subiect păstrat",
    });
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&modal=new-campaign");
    emailApiMocks.listCampaignsOnServer
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([savedCampaign]);
    emailApiMocks.buildVideoCampaignCreatePayload.mockImplementation((draft) => ({
      name: draft.name.trim(),
      segment: draft.segment,
      subject: draft.subject,
      html_body: draft.htmlBody || "<p>Mesaj</p>",
      text_body: draft.textBody || "Mesaj",
    }));
    emailApiMocks.createCampaignOnServer
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce(savedCampaign);

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    const nameInput = await screen.findByLabelText("Nume campanie") as HTMLInputElement;
    const subjectInput = screen.getByLabelText("Subiect") as HTMLInputElement;
    const bodyInput = screen.getByLabelText("Mesaj email") as HTMLTextAreaElement;
    fireEvent.change(nameInput, { target: { value: "Campanie păstrată" } });
    fireEvent.change(subjectInput, { target: { value: "Subiect păstrat" } });
    fireEvent.change(bodyInput, { target: { value: "Mesaj păstrat pentru retry" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvează campania" }));

    expect(await screen.findByText("Nu ne-am putut conecta la server. Datele au rămas în formular.")).toBeTruthy();
    expect(nameInput.value).toBe("Campanie păstrată");
    expect(subjectInput.value).toBe("Subiect păstrat");
    expect(bodyInput.value).toBe("Mesaj păstrat pentru retry");

    fireEvent.click(screen.getByRole("button", { name: "Reîncearcă salvarea" }));

    await waitFor(() => expect(emailApiMocks.createCampaignOnServer).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Campania „Campanie păstrată” a fost creată.")).toBeTruthy();
    expect(screen.getByText("Campanie păstrată")).toBeTruthy();
  });

  it("shows why sending is disabled when the campaign list has no recipients", async () => {
    const campaign = makeCampaign({ id: "campaign-empty-list", name: "Campanie fără destinatari" });
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&view=campaigns");
    emailApiMocks.listCampaignsOnServer.mockResolvedValue([campaign]);
    emailApiMocks.listCampaignRecipientMembershipOnServer.mockResolvedValue([]);

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary("ready") }));

    const campaignCard = (await screen.findByText("Campanie fără destinatari")).closest("article");
    expect(campaignCard).not.toBeNull();
    openCampaignControls(campaignCard as HTMLElement);

    const reason = within(campaignCard as HTMLElement).getByText("Selectează cel puțin un destinatar care nu a primit campania.");
    const sendButton = within(campaignCard as HTMLElement).getByRole("button", { name: "Trimite campania" }) as HTMLButtonElement;
    expect(reason).toBeTruthy();
    expect(sendButton.disabled).toBe(true);
    expect(sendButton.getAttribute("aria-describedby")).toBe(`campaign-${campaign.id}-send-blocked-reason`);
    expect(sendButton.title).toBe("Selectează cel puțin un destinatar care nu a primit campania.");
  });

  it("maps an edit rejection to the message field and keeps the draft open", async () => {
    const campaign = makeCampaign({
      id: "campaign-invalid-variable",
      name: "Campanie editabilă",
      subject: "Salut, {first_name}",
      html_body: "<p>Salut.</p>",
      text_body: "Salut.",
    });
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&view=campaigns");
    emailApiMocks.listCampaignsOnServer.mockResolvedValue([campaign]);
    emailApiMocks.buildVideoCampaignCreatePayload.mockImplementation((draft) => ({
      name: draft.name.trim(),
      segment: draft.segment,
      subject: draft.subject,
      html_body: draft.htmlBody || "<p>Mesaj</p>",
      text_body: draft.textBody || "Mesaj",
    }));
    emailApiMocks.updateCampaignOnServer.mockRejectedValue(
      new CampaignPersistenceError("Campaign contains unsupported variables: secret_score", 400),
    );

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    const campaignCard = (await screen.findByText("Campanie editabilă")).closest("article");
    expect(campaignCard).not.toBeNull();
    openCampaignControls(campaignCard as HTMLElement);
    fireEvent.click(within(campaignCard as HTMLElement).getByRole("button", { name: "Editează campania Campanie editabilă" }));

    const bodyInput = await screen.findByLabelText("Mesaj email") as HTMLTextAreaElement;
    fireEvent.change(bodyInput, { target: { value: "Salut {secret_score}" } });
    fireEvent.click(screen.getByRole("button", { name: "Salvează modificările" }));

    expect(await screen.findByText("Campania nu a fost salvată. Corectează câmpurile marcate.")).toBeTruthy();
    expect(screen.getByText("Mesajul conține o variabilă neacceptată. Elimin-o și salvează din nou.")).toBeTruthy();
    expect(bodyInput.value).toBe("Salut {secret_score}");
    await waitFor(() => expect(document.activeElement).toBe(bodyInput));
    expect(screen.getByRole("button", { name: "Salvează modificările" })).toBeTruthy();
  });

  it("shows boxed feedback and locks campaign fields while saving", async () => {
    const savedCampaign = makeCampaign({
      id: "campaign-pending",
      name: "Campanie pending",
      segment: null,
      subject: "Subiect pending",
    });
    const saveRequest = createDeferred<EmailCampaign>();

    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&modal=new-campaign");
    emailApiMocks.listCampaignsOnServer
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([savedCampaign]);
    emailApiMocks.buildVideoCampaignCreatePayload.mockImplementation((draft) => ({
      name: draft.name.trim(),
      segment: draft.segment,
      subject: draft.subject,
      html_body: "<p>Bună, ${first_name}.</p>",
      text_body: "Bună, ${first_name}.",
    }));
    emailApiMocks.createCampaignOnServer.mockReturnValueOnce(saveRequest.promise);

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    const nameInput = await screen.findByLabelText("Nume campanie") as HTMLInputElement;
    expect(screen.getByLabelText("Segment campanie").getAttribute("data-slot")).toBe("select");
    expect(screen.getByLabelText("Șablon email").getAttribute("data-slot")).toBe("select");
    fireEvent.change(nameInput, { target: { value: "Campanie pending" } });
    const saveButton = screen.getByRole("button", { name: "Salvează campania" });
    const saveForm = saveButton.closest("form");
    expect(saveForm).not.toBeNull();
    fireEvent.submit(saveForm!);
    fireEvent.submit(saveForm!);

    expect(await screen.findAllByText("Salvăm campania")).toHaveLength(2);
    expect(emailApiMocks.createCampaignOnServer).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Pregătim campania pentru selectarea destinatarilor.")).toBeTruthy();
    expect(nameInput.disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Anulează" }) as HTMLButtonElement).disabled).toBe(true);

    saveRequest.resolve(savedCampaign);

    await waitFor(() => {
      expect(screen.queryAllByText("Salvăm campania")).toHaveLength(0);
    });
  });

  it("shows media changes inline and saves without blocking confirmation", async () => {
    const campaign = makeCampaign({
      id: "campaign-media",
      name: "Campanie media",
      subject: "Salut, {first_name}",
      video_url: "https://old.example/video",
      thumbnail_url: "https://old.example/thumb.jpg",
      landing_page_url: "https://old.example/landing",
      html_body:
        '<p>Salut.</p><p><a href="https://old.example/landing"><img src="https://old.example/thumb.jpg" alt="Previzualizare video" /></a></p>',
      text_body: "Salut. Video: https://old.example/landing",
    });
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);

    emailApiMocks.listCampaignsOnServer.mockResolvedValue([campaign]);
    emailApiMocks.updateCampaignOnServer.mockResolvedValue({
      ...campaign,
      video_url: "https://new.example/video",
      thumbnail_url: "https://new.example/thumb.jpg",
      landing_page_url: "https://new.example/landing",
    });
    emailApiMocks.buildVideoCampaignCreatePayload.mockImplementation((draft) => ({
      name: draft.name.trim(),
      segment: draft.segment,
      subject: draft.subject.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "$${$1}"),
      html_body: draft.htmlBody.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "$${$1}"),
      text_body: draft.textBody.replace(/\{([a-zA-Z_][a-zA-Z0-9_]*)\}/g, "$${$1}"),
      video_url: draft.videoUrl,
      thumbnail_url: draft.thumbnailUrl,
      landing_page_url: draft.landingUrl,
    }));
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&view=campaigns");

    try {
      render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

      const campaignCard = (await screen.findByText("Campanie media")).closest("article");
      expect(campaignCard).not.toBeNull();
      openCampaignControls(campaignCard as HTMLElement);
      fireEvent.click(within(campaignCard as HTMLElement).getByRole("button", { name: "Editează campania Campanie media" }));

      fireEvent.change(await screen.findByLabelText("Link video (opțional)"), {
        target: { value: "https://new.example/video" },
      });
      fireEvent.change(screen.getByLabelText("Landing page Cody (opțional)"), {
        target: { value: "https://new.example/landing" },
      });
      fireEvent.change(screen.getByLabelText("Imagine campanie"), {
        target: { value: "https://new.example/thumb.jpg" },
      });

      await waitFor(() => {
        expect(document.querySelector('a[href="https://new.example/landing"] img[src="https://new.example/thumb.jpg"]')).not.toBeNull();
      });
      expect(screen.getByText("Modificări nesalvate")).toBeTruthy();

      fireEvent.click(screen.getByRole("button", { name: "Salvează modificările" }));

      expect(confirmSpy).not.toHaveBeenCalled();
      await waitFor(() => {
        expect(emailApiMocks.updateCampaignOnServer).toHaveBeenCalledWith(
          "campaign-media",
          expect.objectContaining({
            video_url: "https://new.example/video",
            thumbnail_url: "https://new.example/thumb.jpg",
            landing_page_url: "https://new.example/landing",
          }),
        );
      });
      const updatePayload = emailApiMocks.updateCampaignOnServer.mock.calls[0][1];
      expect(updatePayload.html_body).toContain("${landing_page_url}");
      expect(updatePayload.html_body).toContain("${thumbnail_url}");
      expect(updatePayload.html_body).not.toContain("https://old.example/landing");
      expect(updatePayload.html_body).not.toContain("https://old.example/thumb.jpg");
    } finally {
      confirmSpy.mockRestore();
    }
  });

  it("uploads a selected campaign image only when the campaign is saved", async () => {
    const assetRequest = createDeferred<CampaignAssetUpload>();
    emailApiMocks.uploadCampaignAssetOnServer.mockReturnValue(assetRequest.promise);
    emailApiMocks.buildVideoCampaignCreatePayload.mockImplementation((draft) => ({
      name: draft.name.trim(),
      segment: draft.segment,
      subject: draft.subject,
      html_body: "<p>Campanie</p>",
      text_body: "Campanie",
      thumbnail_url: draft.thumbnailUrl,
    }));
    emailApiMocks.createCampaignOnServer.mockResolvedValue(makeCampaign({
      id: "campaign-with-upload",
      name: "Campanie video leadership",
      thumbnail_url: "https://cdn.example.test/thumbnail.png",
    }));
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&modal=new-campaign");

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    expect(await screen.findByLabelText("Nume campanie")).toBeTruthy();
    const assetInput = Array.from(document.querySelectorAll<HTMLInputElement>('input[type="file"]'))
      .find((input) => input.accept.includes("image/"));
    expect(assetInput).toBeDefined();

    const file = new File(["image"], "thumbnail.png", { type: "image/png" });
    fireEvent.change(assetInput!, { target: { files: [file] } });

    expect(await screen.findByText("thumbnail.png este pregătit pentru salvare.")).toBeTruthy();
    expect(emailApiMocks.uploadCampaignAssetOnServer).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("button", { name: "Salvează campania" }));

    expect(await screen.findByRole("button", { name: "Încărcăm imaginea" })).toBeTruthy();
    expect(emailApiMocks.uploadCampaignAssetOnServer).toHaveBeenCalledTimes(1);

    await act(async () => {
      assetRequest.resolve({
        url: "https://cdn.example.test/thumbnail.png",
        file_name: "thumbnail.png",
        content_type: "image/png",
        size_bytes: 2048,
      });
    });

    await waitFor(() => {
      expect(emailApiMocks.createCampaignOnServer).toHaveBeenCalledWith(
        expect.objectContaining({ thumbnail_url: "https://cdn.example.test/thumbnail.png" }),
      );
    });
  });

  it("removes a newly uploaded image when campaign persistence is rejected", async () => {
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&modal=new-campaign");
    emailApiMocks.deleteCampaignAssetOnServer.mockResolvedValue(undefined);
    emailApiMocks.uploadCampaignAssetOnServer.mockResolvedValue({
      url: "https://cdn.example.test/rejected.png",
      file_name: "rejected-owner-token.png",
      content_type: "image/png",
      size_bytes: 2048,
    });
    emailApiMocks.buildVideoCampaignCreatePayload.mockImplementation((draft) => ({
      name: draft.name.trim(),
      segment: draft.segment,
      subject: draft.subject,
      html_body: "<p>Campanie</p>",
      text_body: "Campanie",
      thumbnail_url: draft.thumbnailUrl,
    }));
    emailApiMocks.createCampaignOnServer.mockRejectedValue(
      new CampaignPersistenceError("Campania nu a fost salvată.", 422),
    );

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));
    expect(await screen.findByLabelText("Nume campanie")).toBeTruthy();
    const assetInput = Array.from(document.querySelectorAll<HTMLInputElement>('input[type="file"]'))
      .find((input) => input.accept.includes("image/"));
    fireEvent.change(assetInput!, {
      target: { files: [new File(["image"], "rejected.png", { type: "image/png" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvează campania" }));

    expect(await screen.findByText("Campania nu a fost salvată.")).toBeTruthy();
    expect(emailApiMocks.deleteCampaignAssetOnServer).toHaveBeenCalledWith(
      "rejected-owner-token.png",
    );
  });

  it("shows a retry action when uploaded image cleanup fails", async () => {
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&modal=new-campaign");
    emailApiMocks.deleteCampaignAssetOnServer
      .mockRejectedValueOnce(new Error("cleanup unavailable"))
      .mockResolvedValueOnce(undefined);
    emailApiMocks.uploadCampaignAssetOnServer.mockResolvedValue({
      url: "https://cdn.example.test/rejected.png",
      file_name: "rejected-owner-token.png",
      content_type: "image/png",
      size_bytes: 2048,
    });
    emailApiMocks.buildVideoCampaignCreatePayload.mockImplementation((draft) => ({
      name: draft.name.trim(),
      segment: draft.segment,
      subject: draft.subject,
      html_body: "<p>Campanie</p>",
      text_body: "Campanie",
      thumbnail_url: draft.thumbnailUrl,
    }));
    emailApiMocks.createCampaignOnServer.mockRejectedValue(
      new CampaignPersistenceError("Campania nu a fost salvată.", 422),
    );

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));
    expect(await screen.findByLabelText("Nume campanie")).toBeTruthy();
    const assetInput = Array.from(document.querySelectorAll<HTMLInputElement>('input[type="file"]'))
      .find((input) => input.accept.includes("image/"));
    fireEvent.change(assetInput!, {
      target: { files: [new File(["image"], "rejected.png", { type: "image/png" })] },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvează campania" }));

    expect(
      await screen.findByText(
        "Campania nu a fost salvată, iar imaginea încărcată nu a putut fi eliminată. Reîncearcă.",
      ),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Reîncearcă eliminarea" }));

    await waitFor(() => {
      expect(emailApiMocks.deleteCampaignAssetOnServer).toHaveBeenCalledTimes(2);
    });
    expect(await screen.findByText("Imaginea rămasă a fost eliminată.")).toBeTruthy();
  });

  it("filters global campaign contacts by search and Existing/New client type", async () => {
    render(React.createElement(EmailWorkspace, {
      initialSummary: makeEmailSummary("ready", [
        makeCampaignRecipient({
          id: "recipient-existing",
          company: "Client Co",
          firstName: "Ana",
          lastName: "Client",
          email: "ana@client.example",
          clientType: "tip_1",
          status: "ready",
        }),
        makeCampaignRecipient({
          id: "recipient-new",
          company: "Prospect Co",
          firstName: "Bogdan",
          lastName: "Nou",
          email: "bogdan@prospect.example",
          clientType: "tip_2",
          status: "ready",
        }),
      ]),
    }));

    fireEvent.click(screen.getByRole("button", { name: "Contacte" }));

    expect(await screen.findByText("Client Co")).toBeTruthy();
    expect(screen.getByText("Prospect Co")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Caută contacte campanie"), {
      target: { value: "prospect" },
    });
    expect(screen.queryByText("Client Co")).toBeNull();
    expect(screen.getByText("Prospect Co")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Caută contacte campanie"), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Clienți existenți" }));
    expect(screen.getByText("Client Co")).toBeTruthy();
    expect(screen.queryByText("Prospect Co")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Prospecte" }));
    expect(screen.queryByText("Client Co")).toBeNull();
    expect(screen.getByText("Prospect Co")).toBeTruthy();
  });

  it("restores the contact type filter from the URL after refresh", async () => {
    navigationMocks.searchParams = new URLSearchParams("view=contacts&contactType=past_customer");
    render(React.createElement(EmailWorkspace, {
      initialSummary: makeEmailSummary("ready", [
        makeCampaignRecipient({
          id: "recipient-client",
          company: "Client Co",
          clientType: "tip_1",
          status: "ready",
        }),
        makeCampaignRecipient({
          id: "recipient-prospect",
          company: "Prospect Co",
          clientType: "tip_2",
          status: "ready",
        }),
      ]),
    }));

    expect((await screen.findByRole("button", { name: "Clienți existenți" })).getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByText("Client Co")).toBeTruthy();
    expect(screen.queryByText("Prospect Co")).toBeNull();
  });

  it("refreshes and shows a manually added contact", async () => {
    const addedContact = makeCampaignRecipient({
      id: "recipient-added",
      company: "Manual Co",
      firstName: "Ada",
      lastName: "Manual",
      email: "ada@manual.example",
      status: "ready",
    });
    emailApiMocks.bulkCreateCampaignRecipientsOnServer.mockResolvedValue({
      status: "success",
      count: 1,
      created: 1,
      updated: 0,
    });
    emailApiMocks.getEmailOpsSummary.mockResolvedValue(makeEmailSummary("ready", [addedContact]));
    navigationMocks.searchParams = new URLSearchParams("view=contacts&modal=add-contact");

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary("ready", []) }));

    fireEvent.change(await screen.findByLabelText("Email"), {
      target: { value: "ada@manual.example" },
    });
    expect(screen.getByLabelText("Segment contact manual").getAttribute("data-slot")).toBe("select");
    fireEvent.change(screen.getByLabelText("Nume (opțional)"), {
      target: { value: "Ada Manual" },
    });
    fireEvent.change(screen.getByLabelText("Companie"), {
      target: { value: "Manual Co" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvează contact" }));

    await waitFor(() => {
      expect(emailApiMocks.bulkCreateCampaignRecipientsOnServer).toHaveBeenCalledWith([
        {
          email: "ada@manual.example",
          contact_name: "Ada Manual",
          organization_name: "Manual Co",
          segment: "potential_customer",
        },
      ]);
    });
    expect(await screen.findByText("Manual Co")).toBeTruthy();
    expect(screen.getByText("ada@manual.example")).toBeTruthy();
  });

  it("shows boxed feedback and locks manual contact fields while saving", async () => {
    const addRequest = createDeferred<Awaited<ReturnType<typeof emailApiMocks.bulkCreateCampaignRecipientsOnServer>>>();

    emailApiMocks.bulkCreateCampaignRecipientsOnServer.mockReturnValueOnce(addRequest.promise);
    navigationMocks.searchParams = new URLSearchParams("view=contacts&modal=add-contact");

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary("ready", []) }));

    const emailInput = await screen.findByLabelText("Email") as HTMLInputElement;
    fireEvent.change(emailInput, {
      target: { value: "ada@manual.example" },
    });
    const saveButton = screen.getByRole("button", { name: "Salvează contact" });
    const saveForm = saveButton.closest("form");
    expect(saveForm).not.toBeNull();
    fireEvent.submit(saveForm!);
    fireEvent.submit(saveForm!);

    expect(await screen.findAllByText("Salvăm contactul")).toHaveLength(2);
    expect(emailApiMocks.bulkCreateCampaignRecipientsOnServer).toHaveBeenCalledTimes(1);
    expect(screen.getByText("Adăugăm contactul în lista campaniilor și reîncărcăm datele.")).toBeTruthy();
    expect(emailInput.disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Anulează" }) as HTMLButtonElement).disabled).toBe(true);

    addRequest.resolve({
      status: "success",
      count: 1,
      created: 1,
      updated: 0,
    });

    await waitFor(() => {
      expect(screen.queryByText("Salvăm contactul")).toBeNull();
    });
  });

  it("locks campaign contact file parsing while the spreadsheet is pending", async () => {
    const spreadsheetRequest = createDeferred<{
      sheetName: string | null;
      sheetNames: string[];
      rows: unknown[][];
      cells: unknown[][];
    }>();
    spreadsheetMocks.readSpreadsheetFile.mockReturnValue(spreadsheetRequest.promise);
    navigationMocks.searchParams = new URLSearchParams("view=contacts");

    const { container } = render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary("ready", []) }));

    expect(await screen.findByRole("button", { name: "Importă contacte" })).toBeTruthy();
    const importInput = container.querySelector<HTMLInputElement>('input[type="file"][accept^=".csv"]');
    expect(importInput).not.toBeNull();

    const file = new File(["Email,Nume,Companie\nada@example.com,Ada Contact,Manual Co"], "contacts.csv", {
      type: "text/csv",
    });
    fireEvent.change(importInput!, { target: { files: [file] } });
    fireEvent.change(importInput!, { target: { files: [file] } });

    expect(await screen.findByRole("button", { name: "Importăm contactele" })).toBeTruthy();
    expect(spreadsheetMocks.readSpreadsheetFile).toHaveBeenCalledTimes(1);

    await act(async () => {
      spreadsheetRequest.resolve({
        sheetName: "Revised",
        sheetNames: ["Revised"],
        rows: [["Email", "Nume", "Companie"], ["ada@example.com", "Ada Contact", "Manual Co"]],
        cells: [],
      });
    });

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Importăm contactele" })).toBeNull();
    });
    expect(screen.getByRole("button", { name: "Importă contacte" })).toBeTruthy();
  });

  it("keeps the recipient picker focusable and only reports membership state changes", async () => {
    const recipient = makeCampaignRecipient({
      id: "recipient-focus",
      email: "focus@example.com",
      status: "ready",
    });
    const campaign = makeCampaign({ id: "campaign-focus", name: "Campanie focus" });
    const saveRequest = createDeferred<CampaignRecipient[]>();
    emailApiMocks.listCampaignsOnServer.mockResolvedValue([campaign]);
    emailApiMocks.listCampaignRecipientMembershipOnServer.mockResolvedValue([]);
    emailApiMocks.replaceCampaignRecipientMembershipOnServer.mockReturnValue(saveRequest.promise);
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&view=campaigns");

    render(React.createElement(EmailWorkspace, {
      initialSummary: makeEmailSummary("ready", [recipient]),
    }));

    const campaignCard = (await screen.findByText("Campanie focus")).closest("article");
    expect(campaignCard).not.toBeNull();
    openCampaignControls(campaignCard as HTMLElement);
    const picker = within(campaignCard as HTMLElement).getByRole("region", { name: "Destinatari pentru Campanie focus" });
    const scrollArea = picker.querySelector<HTMLElement>("[tabindex='0']");
    expect(scrollArea).not.toBeNull();
    scrollArea?.focus();
    expect(document.activeElement).toBe(scrollArea);
    expect(screen.queryByText(/Bifele se salvează automat/i)).toBeNull();

    fireEvent.click(within(campaignCard as HTMLElement).getByLabelText("Include focus@example.com în Campanie focus"));
    expect(await within(campaignCard as HTMLElement).findByText("Se salvează")).toBeTruthy();

    await act(async () => saveRequest.reject(new Error("Destinatarii nu au putut fi salvați.")));
    expect(await within(campaignCard as HTMLElement).findByText("Destinatarii nu au putut fi salvați.")).toBeTruthy();
    expect(within(campaignCard as HTMLElement).queryByText("Se salvează")).toBeNull();
  });

  it("keeps recipient membership isolated between campaigns using the same segment", async () => {
    const recipients = [
      makeCampaignRecipient({
        id: "recipient-1",
        company: "Alpha Co",
        firstName: "Ioana",
        lastName: "Popescu",
        email: "ioana@example.com",
        clientType: "tip_2",
        status: "ready",
      }),
      makeCampaignRecipient({
        id: "recipient-2",
        company: "Beta Co",
        firstName: "Mara",
        lastName: "Ionescu",
        email: "mara@example.com",
        clientType: "tip_2",
        status: "ready",
      }),
    ];
    const campaigns = [
      makeCampaign({ id: "campaign-a", name: "Campania A", segment: "potential_customer" }),
      makeCampaign({ id: "campaign-b", name: "Campania B", segment: "potential_customer" }),
    ];
    emailApiMocks.listCampaignsOnServer.mockResolvedValue(campaigns);
    emailApiMocks.listCampaignRecipientMembershipOnServer.mockImplementation((campaignId: string) =>
      Promise.resolve(campaignId === "campaign-a" ? [recipients[0]] : [recipients[1]]),
    );
    emailApiMocks.replaceCampaignRecipientMembershipOnServer.mockImplementation(
      (_campaignId: string, recipientIds: string[]) =>
        Promise.resolve(recipients.filter((recipient) => recipientIds.includes(recipient.id))),
    );
    const sendRequest = createDeferred<{
      campaign_id: string;
      total: number;
      sent: number;
      failed: number;
      skipped: number;
      dry_run: boolean;
      results: [];
    }>();
    emailApiMocks.sendCampaignOnServer.mockReturnValue(sendRequest.promise);
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&view=campaigns");

    render(React.createElement(EmailWorkspace, {
      initialSummary: makeEmailSummary("ready", recipients),
    }));

    const campaignA = (await screen.findByText("Campania A")).closest("article");
    const campaignB = screen.getByText("Campania B").closest("article");
    expect(campaignA).not.toBeNull();
    expect(campaignB).not.toBeNull();

    openCampaignControls(campaignA as HTMLElement);
    fireEvent.click(within(campaignA as HTMLElement).getByLabelText("Include mara@example.com în Campania A"));

    await waitFor(() => {
      expect(emailApiMocks.replaceCampaignRecipientMembershipOnServer).toHaveBeenCalledWith(
        "campaign-a",
        ["recipient-1", "recipient-2"],
      );
    });

    openCampaignControls(campaignB as HTMLElement);
    fireEvent.click(within(campaignB as HTMLElement).getByRole("button", { name: "Trimite campania" }));
    const confirmSendButton = await screen.findByRole("button", { name: "Trimite" });
    fireEvent.click(confirmSendButton);
    fireEvent.click(confirmSendButton);

    expect(await within(campaignB as HTMLElement).findByRole("button", { name: "Trimitem campania" })).toBeTruthy();
    expect(emailApiMocks.sendCampaignOnServer).toHaveBeenCalledTimes(1);
    expect((within(campaignB as HTMLElement).getByLabelText("Mod trimitere pentru Campania B") as HTMLSelectElement).disabled).toBe(true);

    await waitFor(() => {
      expect(emailApiMocks.sendCampaignOnServer).toHaveBeenCalledWith("campaign-b", expect.objectContaining({
        mode: "selected",
        recipientIds: ["recipient-2"],
        idempotencyKey: expect.stringMatching(/^campaign-ui-/),
      }));
    });

    sendRequest.resolve({
      campaign_id: "campaign-b",
      total: 1,
      sent: 1,
      failed: 0,
      skipped: 0,
      dry_run: false,
      results: [],
    });

    await waitFor(() => {
      expect(within(campaignB as HTMLElement).queryByRole("button", { name: "Trimitem campania" })).toBeNull();
    });
  });

  it("marks campaign recipients already sent as checked and disabled without resending them", async () => {
    const recipients = [
      makeCampaignRecipient({
        id: "recipient-sent",
        company: "Alpha Co",
        firstName: "Ana",
        lastName: "Sent",
        email: "ana.sent@example.com",
        clientType: "tip_2",
        status: "ready",
      }),
      makeCampaignRecipient({
        id: "recipient-unsent",
        company: "Alpha Co",
        firstName: "Mara",
        lastName: "Unsent",
        email: "mara.unsent@example.com",
        clientType: "tip_2",
        status: "ready",
      }),
    ];
    const campaign = makeCampaign({
      id: "campaign-markers",
      name: "Campanie cu marker",
      segment: "potential_customer",
    });
    emailApiMocks.listCampaignsOnServer.mockResolvedValue([campaign]);
    emailApiMocks.listCampaignRecipientMembershipOnServer.mockResolvedValue([
      { ...recipients[0], membershipSource: "manual", campaignDelivery: "sent" },
      { ...recipients[1], membershipSource: "manual", campaignDelivery: "not_sent" },
    ]);
    emailApiMocks.replaceCampaignRecipientMembershipOnServer.mockResolvedValue([
      { ...recipients[0], membershipSource: "manual", campaignDelivery: "sent" },
      { ...recipients[1], membershipSource: "manual", campaignDelivery: "not_sent" },
    ]);
    emailApiMocks.sendCampaignOnServer.mockResolvedValue({
      campaign_id: "campaign-markers",
      total: 1,
      sent: 1,
      failed: 0,
      skipped: 0,
      dry_run: false,
      results: [],
    });
    emailApiMocks.getEmailOpsSummary.mockResolvedValue(
      makeEmailSummary("ready", recipients),
    );
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&view=campaigns");

    render(React.createElement(EmailWorkspace, {
      initialSummary: makeEmailSummary("ready", recipients),
    }));

    const campaignCard = (await screen.findByText("Campanie cu marker")).closest("article");
    expect(campaignCard).not.toBeNull();
    expect(within(campaignCard as HTMLElement).getByText("Destinatari (2/2, 1 netrimis)")).toBeTruthy();
    openCampaignControls(campaignCard as HTMLElement);
    expect(within(campaignCard as HTMLElement).getByText("În lista de trimitere")).toBeTruthy();
    expect(within(campaignCard as HTMLElement).getByText("Pregătiți de trimis")).toBeTruthy();
    expect(within(campaignCard as HTMLElement).getByText("Afișați de filtre")).toBeTruthy();
    expect(within(campaignCard as HTMLElement).getByText(
      "Filtrele schimbă doar contactele afișate, nu lista de trimitere.",
    )).toBeTruthy();

    const sentCheckbox = within(campaignCard as HTMLElement).getByLabelText(
      "Include ana.sent@example.com în Campanie cu marker",
    ) as HTMLButtonElement;
    const unsentCheckbox = within(campaignCard as HTMLElement).getByLabelText(
      "Include mara.unsent@example.com în Campanie cu marker",
    ) as HTMLButtonElement;
    expectCheckboxState(sentCheckbox, true);
    expect(sentCheckbox.disabled).toBe(true);
    expectCheckboxState(unsentCheckbox, true);
    expect(unsentCheckbox.disabled).toBe(false);
    expect(within(campaignCard as HTMLElement).getByText("Trimis")).toBeTruthy();
    expect(within(campaignCard as HTMLElement).getByText("Netrimis")).toBeTruthy();

    fireEvent.click(within(campaignCard as HTMLElement).getByRole("button", {
      name: "Trimite campania Campanie cu marker către mara.unsent@example.com",
    }));
    expect(await screen.findByText(
      /Ceilalți destinatari selectați rămân netrimiși/,
    )).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: "Trimite" }));
    await waitFor(() => {
      expect(emailApiMocks.sendCampaignOnServer).toHaveBeenCalledWith(
        "campaign-markers",
        expect.objectContaining({
          mode: "selected",
          recipientIds: ["recipient-unsent"],
          idempotencyKey: expect.stringMatching(/^campaign-ui-/),
        }),
      );
    });
    expect(await screen.findByText(
      "Trimiterea către Mara Unsent a fost procesată: 1 trimise.",
    )).toBeTruthy();
    emailApiMocks.sendCampaignOnServer.mockClear();

    fireEvent.click(within(campaignCard as HTMLElement).getByRole("button", {
      name: "Retrimite campania Campanie cu marker către ana.sent@example.com",
    }));
    expect(await screen.findByText(/trece explicit peste marcajul „Trimis”/)).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: "Retrimite" }));
    await waitFor(() => {
      expect(emailApiMocks.sendCampaignOnServer).toHaveBeenCalledWith(
        "campaign-markers",
        expect.objectContaining({
          mode: "selected",
          recipientIds: ["recipient-sent"],
          idempotencyKey: expect.stringMatching(/^campaign-ui-/),
        }),
      );
    });
    expect(await screen.findByText(
      "Retrimiterea către Ana Sent a fost procesată: 1 trimise.",
    )).toBeTruthy();
    await waitFor(() => {
      expect(
        (within(campaignCard as HTMLElement).getByRole("button", {
          name: "Trimite campania",
        }) as HTMLButtonElement).disabled,
      ).toBe(false);
    });
    emailApiMocks.sendCampaignOnServer.mockClear();

    fireEvent.click(within(campaignCard as HTMLElement).getByRole("button", { name: "Trimite campania" }));
    expect(await screen.findByText(
      "Campania „Campanie cu marker” va fi trimisă către 1 destinatar netrimis din lista campaniei.",
    )).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: "Trimite" }));

    await waitFor(() => {
      expect(emailApiMocks.replaceCampaignRecipientMembershipOnServer).toHaveBeenCalledWith(
        "campaign-markers",
        ["recipient-sent", "recipient-unsent"],
      );
      expect(emailApiMocks.sendCampaignOnServer).toHaveBeenCalledWith("campaign-markers", expect.objectContaining({
        mode: "selected",
        recipientIds: ["recipient-unsent"],
        idempotencyKey: expect.stringMatching(/^campaign-ui-/),
      }));
    });
  });

  it("lets typed campaigns add recipients from other segments", async () => {
    const recipients = [
      makeCampaignRecipient({
        id: "recipient-existing",
        company: "Client Co",
        firstName: "Ana",
        lastName: "Client",
        email: "ana@client.example",
        clientType: "tip_1",
        status: "ready",
      }),
      makeCampaignRecipient({
        id: "recipient-prospect",
        company: "Prospect Co",
        firstName: "Mara",
        lastName: "Prospect",
        email: "mara@prospect.example",
        clientType: "tip_2",
        status: "ready",
      }),
    ];
    const campaign = makeCampaign({
      id: "campaign-existing",
      name: "Campanie clienți existenți",
      segment: "past_customer",
    });

    emailApiMocks.listCampaignsOnServer.mockResolvedValue([campaign]);
    emailApiMocks.listCampaignRecipientMembershipOnServer.mockResolvedValue([recipients[0]]);
    emailApiMocks.replaceCampaignRecipientMembershipOnServer.mockImplementation(
      (_campaignId: string, recipientIds: string[]) =>
        Promise.resolve(recipients.filter((recipient) => recipientIds.includes(recipient.id))),
    );
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&view=campaigns");

    render(React.createElement(EmailWorkspace, {
      initialSummary: makeEmailSummary("ready", recipients),
    }));

    const campaignCard = (await screen.findByText("Campanie clienți existenți")).closest("article");
    expect(campaignCard).not.toBeNull();
    expect(within(campaignCard as HTMLElement).getByText("Destinatari (1/2, 1 netrimis)")).toBeTruthy();
    openCampaignControls(campaignCard as HTMLElement);

    const existingCheckbox = within(campaignCard as HTMLElement).getByLabelText(
      "Include ana@client.example în Campanie clienți existenți",
    );
    const prospectCheckbox = within(campaignCard as HTMLElement).getByLabelText(
      "Include mara@prospect.example în Campanie clienți existenți",
    );
    const typeFilterLabel = "Filtrează destinatari după tip pentru Campanie clienți existenți";
    expect(within(campaignCard as HTMLElement).getByRole("combobox", { name: typeFilterLabel })).toBeTruthy();
    expectCheckboxState(existingCheckbox, true);
    expectCheckboxState(prospectCheckbox, false);

    chooseComboboxOption(campaignCard as HTMLElement, typeFilterLabel, "Clienți existenți");
    expect(within(campaignCard as HTMLElement).getByLabelText(
      "Include ana@client.example în Campanie clienți existenți",
    )).toBeTruthy();
    expect(within(campaignCard as HTMLElement).queryByLabelText(
      "Include mara@prospect.example în Campanie clienți existenți",
    )).toBeNull();

    chooseComboboxOption(campaignCard as HTMLElement, typeFilterLabel, "Prospecte");
    expect(within(campaignCard as HTMLElement).queryByLabelText(
      "Include ana@client.example în Campanie clienți existenți",
    )).toBeNull();
    expect(within(campaignCard as HTMLElement).getByLabelText(
      "Include mara@prospect.example în Campanie clienți existenți",
    )).toBeTruthy();

    chooseComboboxOption(campaignCard as HTMLElement, typeFilterLabel, "Toate tipurile");
    fireEvent.click(within(campaignCard as HTMLElement).getByLabelText(
      "Include mara@prospect.example în Campanie clienți existenți",
    ));

    await waitFor(() => {
      expect(emailApiMocks.replaceCampaignRecipientMembershipOnServer).toHaveBeenCalledWith(
        "campaign-existing",
        ["recipient-existing", "recipient-prospect"],
      );
    });
  });

  it("bulk selects and deselects campaign recipients by company", async () => {
    const recipients = [
      makeCampaignRecipient({
        id: "recipient-alpha-1",
        company: "Alpha Co",
        firstName: "Ana",
        lastName: "Alpha",
        email: "ana@alpha.example",
        clientType: "tip_1",
        status: "ready",
      }),
      makeCampaignRecipient({
        id: "recipient-alpha-2",
        company: "Alpha Co",
        firstName: "Alex",
        lastName: "Alpha",
        email: "alex@alpha.example",
        clientType: "tip_2",
        status: "ready",
      }),
      makeCampaignRecipient({
        id: "recipient-beta",
        company: "Beta Co",
        firstName: "Bianca",
        lastName: "Beta",
        email: "bianca@beta.example",
        clientType: "tip_2",
        status: "ready",
      }),
    ];
    const campaign = makeCampaign({
      id: "campaign-company",
      name: "Campanie pe companii",
      segment: null,
    });

    emailApiMocks.listCampaignsOnServer.mockResolvedValue([campaign]);
    emailApiMocks.listCampaignRecipientMembershipOnServer.mockResolvedValue([recipients[0]]);
    emailApiMocks.replaceCampaignRecipientMembershipOnServer.mockImplementation(
      (_campaignId: string, recipientIds: string[]) =>
        Promise.resolve(recipients.filter((recipient) => recipientIds.includes(recipient.id))),
    );
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&view=campaigns");

    render(React.createElement(EmailWorkspace, {
      initialSummary: makeEmailSummary("ready", recipients),
    }));

    const campaignCard = (await screen.findByText("Campanie pe companii")).closest("article");
    expect(campaignCard).not.toBeNull();
    openCampaignControls(campaignCard as HTMLElement);

    const companyFilterLabel = "Alege companie pentru Campanie pe companii";
    expect(within(campaignCard as HTMLElement).getByRole("combobox", { name: companyFilterLabel })).toBeTruthy();
    chooseComboboxOption(campaignCard as HTMLElement, companyFilterLabel, /^Alpha Co/);
    expect(within(campaignCard as HTMLElement).getByText("Alpha Co: 1/2 selectați")).toBeTruthy();
    expect(within(campaignCard as HTMLElement).queryByLabelText(
      "Include bianca@beta.example în Campanie pe companii",
    )).toBeNull();

    fireEvent.click(within(campaignCard as HTMLElement).getByRole("button", { name: "Selectează compania" }));

    expectCheckboxState(
      within(campaignCard as HTMLElement).getByLabelText("Include ana@alpha.example în Campanie pe companii"),
      true,
    );
    expectCheckboxState(
      within(campaignCard as HTMLElement).getByLabelText("Include alex@alpha.example în Campanie pe companii"),
      true,
    );
    expect(within(campaignCard as HTMLElement).queryByLabelText("Include bianca@beta.example în Campanie pe companii")).toBeNull();

    await waitFor(() => {
      expect(emailApiMocks.replaceCampaignRecipientMembershipOnServer).toHaveBeenCalledWith(
        "campaign-company",
        ["recipient-alpha-1", "recipient-alpha-2"],
      );
    });
    expectCheckboxState(
      within(campaignCard as HTMLElement).getByLabelText("Include ana@alpha.example în Campanie pe companii"),
      true,
    );
    expectCheckboxState(
      within(campaignCard as HTMLElement).getByLabelText("Include alex@alpha.example în Campanie pe companii"),
      true,
    );

    fireEvent.click(within(campaignCard as HTMLElement).getByRole("button", { name: "Deselectează" }));

    await waitFor(() => {
      expect(emailApiMocks.replaceCampaignRecipientMembershipOnServer).toHaveBeenLastCalledWith(
        "campaign-company",
        [],
      );
    });
  });

  it("shows operation feedback while campaign recipients are saving", async () => {
    const recipient = makeCampaignRecipient({
      id: "recipient-alpha",
      company: "Alpha Co",
      firstName: "Ana",
      lastName: "Alpha",
      email: "ana@alpha.example",
      clientType: "tip_1",
      status: "ready",
    });
    const campaign = makeCampaign({
      id: "campaign-feedback",
      name: "Campanie feedback",
      segment: null,
    });
    const saveRequest = createDeferred<CampaignRecipient[]>();

    emailApiMocks.listCampaignsOnServer.mockResolvedValue([campaign]);
    emailApiMocks.listCampaignRecipientMembershipOnServer.mockResolvedValue([]);
    emailApiMocks.replaceCampaignRecipientMembershipOnServer.mockReturnValueOnce(saveRequest.promise);
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&view=campaigns");

    render(React.createElement(EmailWorkspace, {
      initialSummary: makeEmailSummary("ready", [recipient]),
    }));

    const campaignCard = (await screen.findByText("Campanie feedback")).closest("article");
    expect(campaignCard).not.toBeNull();
    openCampaignControls(campaignCard as HTMLElement);

    const recipientCheckbox = within(campaignCard as HTMLElement).getByLabelText("Include ana@alpha.example în Campanie feedback");
    fireEvent.click(recipientCheckbox);
    fireEvent.click(recipientCheckbox);

    expect(await screen.findByText("Se salvează")).toBeTruthy();
    expect(emailApiMocks.replaceCampaignRecipientMembershipOnServer).toHaveBeenCalledTimes(1);
    expect((within(campaignCard as HTMLElement).getByRole("button", {
      name: "Trimite campania Campanie feedback către ana@alpha.example",
    }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByText(/salvează automat/i)).toBeNull();

    saveRequest.resolve([recipient]);

    await waitFor(() => {
      expect(screen.queryByText("Se salvează")).toBeNull();
    });
  });

  it("locks campaign deletion while the backend request is pending", async () => {
    const campaign = makeCampaign({
      id: "campaign-delete",
      name: "Campanie de șters",
      segment: null,
    });
    const deleteRequest = createDeferred<void>();

    emailApiMocks.listCampaignsOnServer
      .mockResolvedValueOnce([campaign])
      .mockResolvedValueOnce([]);
    emailApiMocks.listCampaignRecipientMembershipOnServer.mockResolvedValue([]);
    emailApiMocks.deleteCampaignOnServer.mockReturnValueOnce(deleteRequest.promise);
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&view=campaigns");

    render(React.createElement(EmailWorkspace, {
      initialSummary: makeEmailSummary("ready", []),
    }));

    const campaignCard = (await screen.findByText("Campanie de șters")).closest("article");
    expect(campaignCard).not.toBeNull();
    openCampaignControls(campaignCard as HTMLElement);

    fireEvent.click(within(campaignCard as HTMLElement).getByRole("button", { name: "Șterge campania Campanie de șters" }));
    const confirmDeleteButton = await screen.findByRole("button", { name: "Șterge" });
    fireEvent.click(confirmDeleteButton);
    fireEvent.click(confirmDeleteButton);

    expect(emailApiMocks.deleteCampaignOnServer).toHaveBeenCalledTimes(1);
    expect(await within(campaignCard as HTMLElement).findByRole("button", { name: "Ștergem campania" })).toBeTruthy();

    deleteRequest.resolve(undefined);

    await waitFor(() => {
      expect(screen.queryByText("Campanie de șters")).toBeNull();
    });
  });

  it("keeps campaign deletion successful and exposes failed asset cleanup", async () => {
    const campaign = makeCampaign({
      id: "campaign-delete-cleanup",
      name: "Campanie cu imagine",
      thumbnail_url: "/api/campaign-assets/delete-owner-token.png",
    });
    emailApiMocks.listCampaignsOnServer
      .mockResolvedValueOnce([campaign])
      .mockResolvedValueOnce([]);
    emailApiMocks.deleteCampaignOnServer.mockResolvedValue(undefined);
    emailApiMocks.deleteCampaignAssetOnServer.mockRejectedValueOnce(new Error("cleanup unavailable"));
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&view=campaigns");

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary("ready", []) }));
    const campaignCard = (await screen.findByText("Campanie cu imagine")).closest("article");
    expect(campaignCard).not.toBeNull();
    openCampaignControls(campaignCard as HTMLElement);
    fireEvent.click(
      within(campaignCard as HTMLElement).getByRole("button", {
        name: "Șterge campania Campanie cu imagine",
      }),
    );
    fireEvent.click(await screen.findByRole("button", { name: "Șterge" }));

    expect(
      await screen.findByText(
        "Campania a fost ștearsă, dar imaginea ei nu a putut fi eliminată. Reîncearcă.",
      ),
    ).toBeTruthy();
    expect(screen.getByRole("button", { name: "Reîncearcă eliminarea" })).toBeTruthy();
    expect(screen.queryByText("Campanie cu imagine")).toBeNull();
  });

  it("lets no-group campaigns search and select contacts across segments", async () => {
    const recipients = [
      makeCampaignRecipient({
        id: "recipient-new",
        company: "Prospect Co",
        firstName: "Mara",
        lastName: "Nou",
        email: "mara@prospect.example",
        clientType: "tip_2",
        status: "ready",
      }),
      makeCampaignRecipient({
        id: "recipient-existing",
        company: "Client Co",
        firstName: "Ana",
        lastName: "Client",
        email: "ana@client.example",
        clientType: "tip_1",
        status: "ready",
      }),
    ];
    const campaign = makeCampaign({
      id: "campaign-open",
      name: "Campanie fără grup",
      segment: null,
    });
    emailApiMocks.listCampaignsOnServer.mockResolvedValue([campaign]);
    emailApiMocks.listCampaignRecipientMembershipOnServer.mockResolvedValue([]);
    emailApiMocks.replaceCampaignRecipientMembershipOnServer.mockImplementation(
      (_campaignId: string, recipientIds: string[]) =>
        Promise.resolve(recipients.filter((recipient) => recipientIds.includes(recipient.id))),
    );
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&view=campaigns");

    render(React.createElement(EmailWorkspace, {
      initialSummary: makeEmailSummary("ready", recipients),
    }));

    const campaignCard = (await screen.findByText("Campanie fără grup")).closest("article");
    expect(campaignCard).not.toBeNull();
    expect(within(campaignCard as HTMLElement).getByText(/Fără grup/)).toBeTruthy();
    openCampaignControls(campaignCard as HTMLElement);
    expect(within(campaignCard as HTMLElement).getByLabelText("Include mara@prospect.example în Campanie fără grup")).toBeTruthy();
    expect(within(campaignCard as HTMLElement).getByLabelText("Include ana@client.example în Campanie fără grup")).toBeTruthy();

    fireEvent.change(within(campaignCard as HTMLElement).getByLabelText("Caută destinatari pentru Campanie fără grup"), {
      target: { value: "client" },
    });

    expect(within(campaignCard as HTMLElement).queryByLabelText("Include mara@prospect.example în Campanie fără grup")).toBeNull();
    fireEvent.click(within(campaignCard as HTMLElement).getByLabelText("Include ana@client.example în Campanie fără grup"));

    await waitFor(() => {
      expect(emailApiMocks.replaceCampaignRecipientMembershipOnServer).toHaveBeenCalledWith(
        "campaign-open",
        ["recipient-existing"],
      );
    });
  });

  it("renders contact status as text and changes it only through edit mode", async () => {
    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    fireEvent.click(screen.getByRole("button", { name: "Contacte" }));
    fireEvent.click(await screen.findByRole("button", { name: "Arată inactive (1)" }));

    expect(await screen.findByText("Inactiv")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Inactiv în campanii/ })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Editează ioana@example.com" }));
    fireEvent.change(screen.getByLabelText("Status campanie pentru Ioana Popescu"), {
      target: { value: "active" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Salvează ioana@example.com" }));

    await waitFor(() => {
      expect(emailApiMocks.updateCampaignRecipientOnServer).toHaveBeenCalledWith(
        "recipient-1",
        expect.objectContaining({ status: "active" }),
      );
    });
    expect(screen.getByText("Pregătit")).toBeTruthy();
  });

  it("prevents duplicate bulk contact status updates", async () => {
    const updateRequest = createDeferred<Record<string, never>>();
    emailApiMocks.updateCampaignRecipientOnServer.mockReturnValueOnce(updateRequest.promise);

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    fireEvent.click(screen.getByRole("button", { name: "Contacte" }));
    fireEvent.click(await screen.findByRole("button", { name: "Arată inactive (1)" }));
    fireEvent.click(await screen.findByRole("checkbox", { name: "Selectează ioana@example.com" }));

    const activateButton = screen.getByRole("button", { name: "Activează" });
    fireEvent.click(activateButton);
    fireEvent.click(activateButton);

    expect(await screen.findByText("Activăm contactele")).toBeTruthy();
    expect(emailApiMocks.updateCampaignRecipientOnServer).toHaveBeenCalledTimes(1);

    updateRequest.resolve({});

    await waitFor(() => {
      expect(screen.queryByText("Activăm contactele")).toBeNull();
    });
  });

  it("reconciles partial bulk status updates and keeps only failed contacts selected", async () => {
    const recipients = [
      makeCampaignRecipient({ id: "recipient-1", email: "one@example.com" }),
      makeCampaignRecipient({ id: "recipient-2", email: "two@example.com" }),
    ];
    emailApiMocks.updateCampaignRecipientOnServer
      .mockResolvedValueOnce({})
      .mockRejectedValueOnce(new Error("temporary failure"));
    emailApiMocks.getEmailOpsSummary.mockResolvedValue(makeEmailSummary("suppressed", [
      { ...recipients[0], status: "ready" },
      recipients[1],
    ]));

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary("suppressed", recipients) }));
    fireEvent.click(screen.getByRole("button", { name: "Contacte" }));
    fireEvent.click(await screen.findByRole("button", { name: "Arată inactive (2)" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Selectează one@example.com" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Selectează two@example.com" }));
    fireEvent.click(screen.getByRole("button", { name: "Activează" }));

    expect(await screen.findByText(/1 reușite, 1 eșuate/)).toBeTruthy();
    expectCheckboxState(screen.getByRole("checkbox", { name: "Selectează two@example.com" }), true);
    expectCheckboxState(screen.getByRole("checkbox", { name: "Selectează one@example.com" }), false);
  });

  it("prevents duplicate contact delete confirmations", async () => {
    const deleteRequest = createDeferred<void>();
    emailApiMocks.deleteCampaignRecipientOnServer.mockReturnValueOnce(deleteRequest.promise);

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary("ready") }));

    fireEvent.click(screen.getByRole("button", { name: "Contacte" }));
    fireEvent.click(await screen.findByRole("button", { name: "Șterge ioana@example.com" }));

    const confirmButton = await screen.findByRole("button", { name: "Șterge" });
    fireEvent.click(confirmButton);
    fireEvent.click(confirmButton);

    expect(emailApiMocks.deleteCampaignRecipientOnServer).toHaveBeenCalledTimes(1);

    deleteRequest.resolve(undefined);

    await waitFor(() => {
      expect(screen.queryByText("Ștergi contactul?")).toBeNull();
    });
  });

  it("reconciles partial bulk deletion and keeps only failed contacts selected", async () => {
    const recipients = [
      makeCampaignRecipient({ id: "recipient-1", email: "one@example.com", status: "ready" }),
      makeCampaignRecipient({ id: "recipient-2", email: "two@example.com", status: "ready" }),
    ];
    emailApiMocks.deleteCampaignRecipientOnServer
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error("temporary failure"));
    emailApiMocks.getEmailOpsSummary.mockResolvedValue(
      makeEmailSummary("ready", [recipients[1]]),
    );

    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary("ready", recipients) }));
    fireEvent.click(screen.getByRole("button", { name: "Contacte" }));
    fireEvent.click(await screen.findByRole("checkbox", { name: "Selectează one@example.com" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "Selectează two@example.com" }));
    fireEvent.click(screen.getByRole("button", { name: "Șterge contactele selectate" }));
    fireEvent.click(await screen.findByRole("button", { name: "Șterge" }));

    expect(await screen.findByText(/1 șterse, 1 eșuate/)).toBeTruthy();
    expect(screen.queryByRole("checkbox", { name: "Selectează one@example.com" })).toBeNull();
    expectCheckboxState(screen.getByRole("checkbox", { name: "Selectează two@example.com" }), true);
  });

  it("shows unsubscribed campaign contacts as protected and does not reactivate them", async () => {
    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary("unsubscribed") }));

    fireEvent.click(screen.getByRole("button", { name: "Contacte" }));
    fireEvent.click(await screen.findByRole("button", { name: "Arată inactive (1)" }));

    expect(await screen.findByText("Dezabonat")).toBeTruthy();
    expect(screen.queryByRole("button", { name: /Dezabonat din campanii/ })).toBeNull();
    expect(emailApiMocks.updateCampaignRecipientOnServer).not.toHaveBeenCalled();
  });

  it("blocks bulk contact operations while a selected contact is being edited", async () => {
    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary("ready") }));

    fireEvent.click(screen.getByRole("button", { name: "Contacte" }));
    fireEvent.click(await screen.findByRole("checkbox", { name: "Selectează ioana@example.com" }));
    fireEvent.click(await screen.findByRole("button", { name: "Editează ioana@example.com" }));

    expect(screen.getByLabelText("Segment pentru Ioana Popescu").getAttribute("data-slot")).toBe("select");
    expect(screen.getByLabelText("Status campanie pentru Ioana Popescu").getAttribute("data-slot")).toBe("select");
    expect((screen.getByRole("button", { name: "Activează" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Dezactivează" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Șterge contactele selectate" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("clears hidden inactive selections when inactive contacts are hidden", async () => {
    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    fireEvent.click(screen.getByRole("button", { name: "Contacte" }));
    fireEvent.click(await screen.findByRole("button", { name: "Arată inactive (1)" }));

    const selection = await screen.findByRole("checkbox", { name: "Selectează ioana@example.com" });
    fireEvent.click(selection);
    expectCheckboxState(selection, true);

    fireEvent.click(screen.getByRole("button", { name: "Ascunde inactive" }));
    fireEvent.click(await screen.findByRole("button", { name: "Arată inactive (1)" }));

    expectCheckboxState(await screen.findByRole("checkbox", { name: "Selectează ioana@example.com" }), false);
  });
});

function createDeferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason?: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

describe("buildCampaignRecipientImport", () => {
  it("normalizes the Romanian campaign recipient template and suppresses rows not marked for sending", () => {
    const result = buildCampaignRecipientImport([
      {
        "De trimis": "Da",
        "Primul prenume": "Andrei",
        "Al doilea prenume": "Cristian",
        "Nume de familie": "Popescu",
        "Tip Client": "Nu e client",
        "Organizație": "(Genpact) Vodaphone",
        "Email": "andrei.popescu@example.com",
        "Telefon": "0771 382 348",
        "Funcția": "-",
      },
      {
        "De trimis": "Nu",
        "Primul prenume": "Maria",
        "Nume de familie": "Ionescu",
        "Tip Client": "Client",
        "Organizație": "Example",
        "Email": "maria@example.com",
      },
      {
        "De trimis": "Da",
        "Primul prenume": "Invalid",
        "Nume de familie": "Email",
        "Tip Client": "Nu e client",
        "Organizație": "Example",
        "Email": "not an email",
      },
      {
        "De trimis": "Nu",
        "Primul prenume": "Missing",
        "Nume de familie": "Email",
        "Tip Client": "Nu e client",
        "Organizație": "No Mail Co",
      },
    ]);

    expect(result).toEqual({
      recipients: [
        {
          email: "andrei.popescu@example.com",
          contact_name: "Andrei Cristian Popescu",
          organization_name: "(Genpact) Vodaphone",
          segment: "potential_customer",
          status: "active",
          source: "excel_import",
        },
        {
          email: "maria@example.com",
          contact_name: "Maria Ionescu",
          organization_name: "Example",
          segment: "past_customer",
          status: "suppressed",
          source: "excel_import",
        },
        {
          email: undefined,
          contact_name: "Invalid Email",
          organization_name: "Example",
          segment: "potential_customer",
          status: "suppressed",
          source: "excel_import",
        },
        {
          email: undefined,
          contact_name: "Missing Email",
          organization_name: "No Mail Co",
          segment: "potential_customer",
          status: "suppressed",
          source: "excel_import",
        },
      ],
      skippedBySendFlag: 0,
      skippedMissingEmail: 0,
      skippedInvalidEmail: 0,
    });
  });

  it("keeps the existing generic import headers working", () => {
    const result = buildCampaignRecipientImport([
      {
        Email: "client@example.com",
        Nume: "Client Existing",
        Companie: "Client Co",
        Segment: "past",
      },
    ]);

    expect(result.recipients).toEqual([
      {
        email: "client@example.com",
        contact_name: "Client Existing",
        organization_name: "Client Co",
        segment: "past_customer",
        status: "active",
        source: "excel_import",
      },
    ]);
  });

  it("accepts name surname aliases and unaccented organization headers", () => {
    const drafts = buildCampaignRecipientImportDrafts([
      {
        Trimite: "Da",
        Prenume: "Cristina",
        Nume: "Luncan",
        "Tip Client": "Nu e client",
        Organizatie: "Viarom",
        Email: "cristina.luncan@example.com",
      },
      {
        Send: "yes",
        "First name": "Diana",
        "Middle name": "Maria",
        Surname: "Ene",
        Segment: "past customer",
        Company: "Clinica Meridian",
        Email: "diana.ene@example.com",
      },
      {
        "De trimis": "Nu",
        Name: "Full Name Fallback",
        Company: "Fallback Co",
        Email: "fallback@example.com",
      },
    ]);

    expect(drafts[0]).toMatchObject({
      contact_name: "Cristina Luncan",
      organization_name: "Viarom",
      send: true,
    });
    expect(drafts[1]).toMatchObject({
      contact_name: "Diana Maria Ene",
      organization_name: "Clinica Meridian",
      segment: "past_customer",
      send: true,
    });
    expect(drafts[2]).toMatchObject({
      contact_name: "Full Name Fallback",
      organization_name: "Fallback Co",
      send: false,
    });
  });

  it("prefers explicit full name when mixed exports also include surname columns", () => {
    const drafts = buildCampaignRecipientImportDrafts([
      {
        Name: "Ana Popescu",
        Surname: "Popescu",
        Company: "Mixed Export Co",
        Email: "ana.popescu@example.com",
      },
    ]);

    expect(drafts[0]).toMatchObject({
      contact_name: "Ana Popescu",
      organization_name: "Mixed Export Co",
      send: true,
    });
  });

  it("counts duplicate valid emails and keeps the last row before bulk import", () => {
    const drafts = buildCampaignRecipientImportDrafts([
      {
        Name: "First Contact",
        Company: "First Co",
        Email: "duplicate@example.com",
      },
      {
        Name: "Second Contact",
        Company: "Second Co",
        Email: "DUPLICATE@example.com",
      },
      {
        Name: "No Email Contact",
        Company: "No Email Co",
      },
    ]);

    const result = uniqueCampaignImportDrafts(drafts);

    expect(result.duplicateEmailCount).toBe(1);
    expect(result.uniqueDrafts).toHaveLength(2);
    expect(result.uniqueDrafts[0]).toMatchObject({
      contact_name: "Second Contact",
      email: "DUPLICATE@example.com",
    });
    expect(result.uniqueDrafts[1]).toMatchObject({
      contact_name: "No Email Contact",
      email: "",
    });
  });

  it("builds editable import drafts with original send flags", () => {
    const drafts = buildCampaignRecipientImportDrafts([
      {
        "De trimis": "Nu",
        "Primul prenume": "Maria",
        "Nume de familie": "Ionescu",
        "Tip Client": "Client",
        "Organizație": "Example",
        "Email": "",
      },
      {
        "De trimis": "Da",
        "Primul prenume": "Invalid",
        "Nume de familie": "Email",
        "Tip Client": "Nu e client",
        "Organizație": "Example",
        "Email": "not an email",
      },
    ]);

    expect(drafts[0]).toMatchObject({
      rowNumber: 2,
      contact_name: "Maria Ionescu",
      organization_name: "Example",
      segment: "past_customer",
      send: false,
    });
    expect(drafts[1]).toMatchObject({
      contact_name: "Invalid Email",
      email: "not an email",
      send: false,
    });
  });

  it("prefers the Revised sheet from the campaign workbook", () => {
    expect(selectCampaignRecipientImportSheetName([
      "Extragere Nume din Document",
      "Revised",
      "Sheet2",
    ])).toBe("Revised");
  });
});
