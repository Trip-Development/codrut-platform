import { describe, expect, it } from "vitest";

import { displayReportsToName, normalizeReportsToName } from "./roster-format";

describe("roster manager formatting", () => {
  it("treats top-level manager markers as empty reports-to values", () => {
    expect(normalizeReportsToName(" Rădăcină ")).toBe("");
    expect(normalizeReportsToName("root")).toBe("");
    expect(normalizeReportsToName("Fără manager")).toBe("");
    expect(normalizeReportsToName("—")).toBe("");
  });

  it("preserves real manager names and displays empty values as a dash", () => {
    expect(normalizeReportsToName("Maria Popescu")).toBe("Maria Popescu");
    expect(displayReportsToName("radacina")).toBe("—");
    expect(displayReportsToName("Maria Popescu")).toBe("Maria Popescu");
  });
});
