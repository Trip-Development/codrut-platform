import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { EmailCampaign, EmailOpsSummary } from "@/api/email";
import {
  buildCampaignRecipientImport,
  buildCampaignRecipientImportDrafts,
  EmailWorkspace,
  renderCampaignEmailPreviewShell,
  renderEmailTemplatePreviewBody,
  replacePreviewPlaceholders,
  selectCampaignRecipientImportSheetName,
  uniqueCampaignImportDrafts,
} from "./EmailWorkspace";

const emailApiMocks = vi.hoisted(() => ({
  bulkCreateCampaignRecipientsOnServer: vi.fn(),
  buildVideoCampaignCreatePayload: vi.fn(),
  createCampaignOnServer: vi.fn(),
  createEmailTemplateOnServer: vi.fn(),
  deleteCampaignOnServer: vi.fn(),
  deleteCampaignRecipientOnServer: vi.fn(),
  deleteEmailTemplateOnServer: vi.fn(),
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
    deleteCampaignOnServer: emailApiMocks.deleteCampaignOnServer,
    deleteCampaignRecipientOnServer: emailApiMocks.deleteCampaignRecipientOnServer,
    deleteEmailTemplateOnServer: emailApiMocks.deleteEmailTemplateOnServer,
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

beforeEach(() => {
  Object.values(emailApiMocks).forEach((mock) => mock.mockReset());
  navigationMocks.searchParams = new URLSearchParams();
  navigationMocks.push.mockReset();
  navigationMocks.replace.mockReset();
  navigationMocks.prefetch.mockReset();
  navigationMocks.back.mockReset();
  navigationMocks.refresh.mockReset();
  emailApiMocks.listCampaignsOnServer.mockResolvedValue([]);
  emailApiMocks.listCampaignRecipientMembershipOnServer.mockResolvedValue([]);
  emailApiMocks.replaceCampaignRecipientMembershipOnServer.mockResolvedValue([]);
  emailApiMocks.listEmailTemplatesOnServer.mockResolvedValue([]);
  emailApiMocks.updateCampaignRecipientOnServer.mockResolvedValue({});
});

afterEach(() => {
  cleanup();
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
      '<table role="presentation"><tbody><tr><td>✓</td><td>A supraviețuit tranziției</td></tr><tr><td>✗</td><td>A neglijat reconectarea</td></tr></tbody></table>',
    );

    expect(html).toContain("<table");
    expect(html).toContain("<td>✓</td>");
    expect(html).toContain("A neglijat reconectarea");
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
  });

  it("wraps plain campaign previews in the branded promotional email shell", () => {
    const html = renderCampaignEmailPreviewShell("<p>Mesaj simplu</p>", {
      "{unsubscribe_url}": "https://codrut.example/unsubscribe/demo",
    });

    expect(html).toContain("Andrei Văcaru");
    expect(html).toContain("<p>Mesaj simplu</p>");
    expect(html).toContain("Ai primit acest email deoarece");
    expect(html).toContain("https://codrut.example/unsubscribe/demo");
  });

  it("does not double-wrap campaign previews that already have the branded shell", () => {
    const wrapped = renderCampaignEmailPreviewShell(
      '<div style="font-family:Inter,Arial,sans-serif"><p>Andrei Văcaru</p><p>Mesaj</p></div>',
    );

    expect(wrapped.match(/Andrei Văcaru/g)).toHaveLength(1);
  });
});

describe("EmailWorkspace campaign contacts", () => {
  it("removes the global archive tab and normalizes legacy delivery links", async () => {
    navigationMocks.searchParams = new URLSearchParams("tab=delivery");
    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    expect(screen.queryByRole("button", { name: "Arhivă globală" })).toBeNull();
    expect(screen.queryByText("Invitațiile live se operează din companie")).toBeNull();
    expect(screen.getByRole("button", { name: "Șabloane email" })).toBeTruthy();

    await waitFor(() => {
      expect(navigationMocks.replace).toHaveBeenCalledWith("/trainer/email", { scroll: false });
    });
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
    fireEvent.change(messageInput, { target: { value: "Mesaj simplu" } });
    expect((messageInput as HTMLTextAreaElement).value).toBe("Mesaj simplu");
    const advancedEditorSummary = screen.getByText("Editor HTML avansat");
    expect((advancedEditorSummary.closest("details") as HTMLDetailsElement | null)?.open).toBe(false);

    fireEvent.click(advancedEditorSummary);
    expect((advancedEditorSummary.closest("details") as HTMLDetailsElement | null)?.open).toBe(true);
    const bodyInput = screen.getByLabelText("Corp email");
    fireEvent.change(bodyInput, { target: { value: "Primul rând" } });
    fireEvent.change(bodyInput, { target: { value: "Primul rând\nAl doilea rând" } });
    expect((bodyInput as HTMLTextAreaElement).value).toBe("Primul rând\nAl doilea rând");
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

    fireEvent.click(screen.getByRole("button", { name: "Campanii" }));

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
    fireEvent.click(screen.getByRole("button", { name: "Existing" }));
    expect(screen.getByText("Client Co")).toBeTruthy();
    expect(screen.queryByText("Prospect Co")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "New" }));
    expect(screen.queryByText("Client Co")).toBeNull();
    expect(screen.getByText("Prospect Co")).toBeTruthy();
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
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);

    emailApiMocks.listCampaignsOnServer.mockResolvedValue(campaigns);
    emailApiMocks.listCampaignRecipientMembershipOnServer.mockImplementation((campaignId: string) =>
      Promise.resolve(campaignId === "campaign-a" ? [recipients[0]] : [recipients[1]]),
    );
    emailApiMocks.replaceCampaignRecipientMembershipOnServer.mockImplementation(
      (_campaignId: string, recipientIds: string[]) =>
        Promise.resolve(recipients.filter((recipient) => recipientIds.includes(recipient.id))),
    );
    emailApiMocks.sendCampaignOnServer.mockResolvedValue({
      campaign_id: "campaign-b",
      total: 1,
      sent: 1,
      failed: 0,
      skipped: 0,
      dry_run: false,
      results: [],
    });
    navigationMocks.searchParams = new URLSearchParams("tab=campaigns&view=campaigns");

    try {
      render(React.createElement(EmailWorkspace, {
        initialSummary: makeEmailSummary("ready", recipients),
      }));

      const campaignA = (await screen.findByText("Campania A")).closest("article");
      const campaignB = screen.getByText("Campania B").closest("article");
      expect(campaignA).not.toBeNull();
      expect(campaignB).not.toBeNull();

      fireEvent.click(within(campaignA as HTMLElement).getByLabelText("Include mara@example.com în Campania A"));
      fireEvent.click(within(campaignA as HTMLElement).getByRole("button", { name: "Salvează destinatarii" }));

      await waitFor(() => {
        expect(emailApiMocks.replaceCampaignRecipientMembershipOnServer).toHaveBeenCalledWith(
          "campaign-a",
          ["recipient-1", "recipient-2"],
        );
      });

      fireEvent.click(within(campaignB as HTMLElement).getByRole("button", { name: "Trimite lista (1)" }));

      await waitFor(() => {
        expect(emailApiMocks.sendCampaignOnServer).toHaveBeenCalledWith("campaign-b", {
          mode: "selected",
          recipientIds: ["recipient-2"],
        });
      });
    } finally {
      confirmSpy.mockRestore();
    }
  });

  it("toggles an inactive campaign contact to active with clear Da/Nu state", async () => {
    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    fireEvent.click(screen.getByRole("button", { name: "Campanii" }));
    fireEvent.click(await screen.findByRole("button", { name: "Arată inactive (1)" }));

    const inactiveButton = await screen.findByRole("button", {
      name: "Inactiv în campanii pentru ioana@example.com",
    });
    expect(inactiveButton.getAttribute("aria-pressed")).toBe("false");
    expect(inactiveButton.textContent).toContain("Nu");

    fireEvent.click(inactiveButton);

    await waitFor(() => {
      expect(emailApiMocks.updateCampaignRecipientOnServer).toHaveBeenCalledWith(
        "recipient-1",
        { status: "active" },
      );
    });

    const activeButton = await screen.findByRole("button", {
      name: "Activ în campanii pentru ioana@example.com",
    });
    expect(activeButton.getAttribute("aria-pressed")).toBe("true");
    expect(activeButton.textContent).toContain("Da");
    expect(screen.getByText("Pregătit")).toBeTruthy();
  });

  it("shows unsubscribed campaign contacts as protected and does not reactivate them", async () => {
    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary("unsubscribed") }));

    fireEvent.click(screen.getByRole("button", { name: "Campanii" }));

    const unsubscribedButton = await screen.findByRole("button", {
      name: "Dezabonat din campanii pentru ioana@example.com",
    });
    expect((unsubscribedButton as HTMLButtonElement).disabled).toBe(true);
    expect(unsubscribedButton.textContent).toContain("Stop");
    expect(screen.getByText("Dezabonat")).toBeTruthy();
    expect(emailApiMocks.updateCampaignRecipientOnServer).not.toHaveBeenCalled();
  });

  it("blocks bulk contact operations while a selected contact is being edited", async () => {
    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary("ready") }));

    fireEvent.click(screen.getByRole("button", { name: "Campanii" }));
    fireEvent.click(await screen.findByRole("checkbox", { name: "Selectează ioana@example.com" }));
    fireEvent.click(await screen.findByRole("button", { name: "Editează ioana@example.com" }));

    expect((screen.getByRole("button", { name: "Activează" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Dezactivează" }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole("button", { name: "Șterge contactele selectate" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("clears hidden inactive selections when inactive contacts are hidden", async () => {
    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    fireEvent.click(screen.getByRole("button", { name: "Campanii" }));
    fireEvent.click(await screen.findByRole("button", { name: "Arată inactive (1)" }));

    const selection = await screen.findByRole("checkbox", { name: "Selectează ioana@example.com" });
    fireEvent.click(selection);
    expect((selection as HTMLInputElement).checked).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "Ascunde inactive" }));
    fireEvent.click(await screen.findByRole("button", { name: "Arată inactive (1)" }));

    expect(((await screen.findByRole("checkbox", { name: "Selectează ioana@example.com" })) as HTMLInputElement).checked).toBe(false);
  });
});

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
        "Email": "andreicristian.popescu@genpact.com",
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
          email: "andreicristian.popescu@genpact.com",
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
        Email: "cristina.luncan@viarom.ro",
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
