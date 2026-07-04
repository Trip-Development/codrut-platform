import { describe, expect, it } from "vitest";

import {
  buildCampaignRecipientImport,
  buildCampaignRecipientImportDrafts,
  renderEmailTemplatePreviewBody,
  replacePreviewPlaceholders,
  selectCampaignRecipientImportSheetName,
} from "./EmailWorkspace";

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
      ],
      skippedBySendFlag: 0,
      skippedMissingEmail: 0,
      skippedInvalidEmail: 1,
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
    ]);

    expect(drafts[0]).toMatchObject({
      rowNumber: 2,
      contact_name: "Maria Ionescu",
      organization_name: "Example",
      segment: "past_customer",
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
