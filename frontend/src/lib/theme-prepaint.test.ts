import { createHash } from "node:crypto";
import { describe, expect, it } from "vitest";

import { THEME_PREPAINT_CSP_HASH, THEME_PREPAINT_SCRIPT } from "./theme-prepaint";

describe("theme prepaint CSP", () => {
  it("keeps the CSP hash synchronized with the inline script", () => {
    const digest = createHash("sha256").update(THEME_PREPAINT_SCRIPT).digest("base64");

    expect(THEME_PREPAINT_CSP_HASH).toBe(`'sha256-${digest}'`);
  });
});
