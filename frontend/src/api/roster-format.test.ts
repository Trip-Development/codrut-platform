import { describe, expect, it } from "vitest";

import {
  buildManagerReferenceKeySet,
  displayReportsToName,
  isExternalMatrixManagerLabel,
  managerReferenceKey,
  normalizeReportsToName,
} from "./roster-format";

describe("roster manager formatting", () => {
  it("treats top-level manager markers as empty reports-to values", () => {
    expect(normalizeReportsToName(" Rădăcină ")).toBe("");
    expect(normalizeReportsToName("root")).toBe("");
    expect(normalizeReportsToName("Fără manager")).toBe("");
    expect(normalizeReportsToName("—")).toBe("");
    expect(normalizeReportsToName("1")).toBe("");
    expect(normalizeReportsToName(" 002 ")).toBe("");
  });

  it("preserves real manager names and displays empty values as a dash", () => {
    expect(normalizeReportsToName("Maria Popescu")).toBe("Maria Popescu");
    expect(displayReportsToName("radacina")).toBe("—");
    expect(displayReportsToName("Maria Popescu")).toBe("Maria Popescu");
  });

  it("builds the same manager key for compact and display names", () => {
    expect(managerReferenceKey("Ana Maria Popescu")).toBe("anamariapopescu");
    expect(managerReferenceKey("AnaMariaPopescu")).toBe("anamariapopescu");
    expect(managerReferenceKey("Ștefan-Manager")).toBe("stefanmanager");
  });

  it("builds roster lookup keys that resolve compact manager references", () => {
    const keys = buildManagerReferenceKeySet(["Titus Julien Botis", "Ștefan Manager", ""]);

    expect(keys.has(managerReferenceKey("TitusJulienBotis"))).toBe(true);
    expect(keys.has(managerReferenceKey("StefanManager"))).toBe(true);
  });

  it("recognizes matrix manager labels as external manager hints", () => {
    expect(isExternalMatrixManagerLabel("External Leader - Matrix")).toBe(true);
    expect(isExternalMatrixManagerLabel("External Leader")).toBe(false);
  });
});
