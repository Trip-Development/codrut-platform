import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { EmailOpsSummary } from "@/api/email";
import {
  buildCampaignRecipientImport,
  buildCampaignRecipientImportDrafts,
  EmailWorkspace,
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
  listCampaignsOnServer: vi.fn(),
  listEmailTemplatesOnServer: vi.fn(),
  sendCampaignOnServer: vi.fn(),
  updateCampaignOnServer: vi.fn(),
  updateCampaignRecipientOnServer: vi.fn(),
  updateEmailTemplateOnServer: vi.fn(),
  uploadCampaignAssetOnServer: vi.fn(),
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
    listCampaignsOnServer: emailApiMocks.listCampaignsOnServer,
    listEmailTemplatesOnServer: emailApiMocks.listEmailTemplatesOnServer,
    sendCampaignOnServer: emailApiMocks.sendCampaignOnServer,
    updateCampaignOnServer: emailApiMocks.updateCampaignOnServer,
    updateCampaignRecipientOnServer: emailApiMocks.updateCampaignRecipientOnServer,
    updateEmailTemplateOnServer: emailApiMocks.updateEmailTemplateOnServer,
    uploadCampaignAssetOnServer: emailApiMocks.uploadCampaignAssetOnServer,
  };
});

beforeEach(() => {
  Object.values(emailApiMocks).forEach((mock) => mock.mockReset());
  emailApiMocks.listCampaignsOnServer.mockResolvedValue([]);
  emailApiMocks.listEmailTemplatesOnServer.mockResolvedValue([]);
  emailApiMocks.updateCampaignRecipientOnServer.mockResolvedValue({});
});

afterEach(() => {
  cleanup();
});

function makeEmailSummary(
  recipientStatus: EmailOpsSummary["campaign"]["recipients"][number]["status"] = "suppressed",
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
      recipients: [
        {
          id: "recipient-1",
          company: "Demo Co",
          firstName: "Ioana",
          lastName: "Popescu",
          email: "ioana@example.com",
          clientType: "tip_2",
          status: recipientStatus,
          openCount: 0,
          clickCount: 0,
          viewCount: 0,
          replyCount: 0,
          calendlyClickCount: 0,
        },
      ],
      weeklyReport: {
        cadence: "Săptămânal",
        metrics: [],
        notification: "Email",
      },
    },
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
  });
});

describe("EmailWorkspace campaign contacts", () => {
  it("toggles an inactive campaign contact to active with clear Da/Nu state", async () => {
    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary() }));

    fireEvent.click(screen.getByRole("button", { name: "Campanii" }));

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
    expect(screen.getByText("pregătit")).toBeTruthy();
  });

  it("shows unsubscribed campaign contacts as protected and does not reactivate them", async () => {
    render(React.createElement(EmailWorkspace, { initialSummary: makeEmailSummary("unsubscribed") }));

    fireEvent.click(screen.getByRole("button", { name: "Campanii" }));

    const unsubscribedButton = await screen.findByRole("button", {
      name: "Dezabonat din campanii pentru ioana@example.com",
    });
    expect((unsubscribedButton as HTMLButtonElement).disabled).toBe(true);
    expect(unsubscribedButton.textContent).toContain("Stop");
    expect(screen.getByText("dezabonat")).toBeTruthy();
    expect(emailApiMocks.updateCampaignRecipientOnServer).not.toHaveBeenCalled();
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
