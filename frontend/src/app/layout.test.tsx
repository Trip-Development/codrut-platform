import { renderToStaticMarkup } from "react-dom/server";
import { headers } from "next/headers";
import { describe, expect, it, vi } from "vitest";

import RootLayout, { dynamic } from "./layout";

vi.mock("next/headers", () => ({
  headers: vi.fn(),
}));

describe("RootLayout", () => {
  it("renders dynamically and forwards the request nonce to inline scripts", async () => {
    vi.mocked(headers).mockResolvedValue(new Headers({ "x-nonce": "request-nonce" }) as never);

    const markup = renderToStaticMarkup(
      await RootLayout({ children: <main>Conținut</main> }),
    );

    expect(dynamic).toBe("force-dynamic");
    expect(markup).toContain('id="codrut-theme-prepaint"');
    expect(markup).toContain('nonce="request-nonce"');
  });
});
