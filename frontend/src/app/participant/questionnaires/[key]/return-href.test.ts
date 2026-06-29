import { describe, expect, it } from "vitest";

import { safeReturnHref } from "./return-href";

describe("safeReturnHref", () => {
  it("allows root-relative return destinations for normal participant questionnaire pages", () => {
    expect(safeReturnHref("/participant/questionnaires", "/fallback")).toBe("/participant/questionnaires");
  });

  it("rejects missing, external, and protocol-relative destinations", () => {
    expect(safeReturnHref(undefined, "/fallback")).toBe("/fallback");
    expect(safeReturnHref("https://example.com", "/fallback")).toBe("/fallback");
    expect(safeReturnHref("//example.com", "/fallback")).toBe("/fallback");
  });

  it("only allows invite return destinations for secure invite questionnaires", () => {
    expect(safeReturnHref("/invite/demo-token", "/", { secureInvite: true })).toBe("/invite/demo-token");
    expect(safeReturnHref("/participant/questionnaires", "/", { secureInvite: true })).toBe("/participant/questionnaires");
    expect(safeReturnHref("/participant", "/", { secureInvite: true })).toBe("/");
    expect(safeReturnHref("/trainer/projects", "/", { secureInvite: true })).toBe("/");
    expect(safeReturnHref("/invite/demo-token/extra", "/", { secureInvite: true })).toBe("/");
    expect(safeReturnHref("/invite/demo-token?next=/participant", "/", { secureInvite: true })).toBe("/");
  });
});
