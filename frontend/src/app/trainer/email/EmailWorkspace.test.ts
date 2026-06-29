import { describe, expect, it } from "vitest";

import { renderEmailTemplatePreviewBody } from "./EmailWorkspace";

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
});
