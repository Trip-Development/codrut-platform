import { describe, expect, it } from "vitest";

import { PASSWORD_MAX_LENGTH, PASSWORD_POLICY_MESSAGE, validatePasswordPolicy } from "./password-policy";

describe("password policy", () => {
  it("accepts long passphrases without composition rules", () => {
    expect(validatePasswordPolicy("o frază lungă și memorabilă")).toBeNull();
  });

  it("accepts Unicode passphrases", () => {
    expect(validatePasswordPolicy("Învăț în fiecare săptămână")).toBeNull();
  });

  it("rejects common passwords", () => {
    expect(validatePasswordPolicy("password" + "1234")).toBe(
      "Parola este prea frecventă. Alege o frază mai greu de ghicit.",
    );
  });

  it("rejects passwords over the backend maximum length", () => {
    expect(validatePasswordPolicy(`Aa1!${"a".repeat(PASSWORD_MAX_LENGTH - 3)}`)).toBe(
      `Parola nu poate depăși ${PASSWORD_MAX_LENGTH} de caractere.`,
    );
  });

  it.each(["prea-scurta", "scurtă"])(
    "rejects short password %s",
    (password) => {
      expect(validatePasswordPolicy(password)).toBe(PASSWORD_POLICY_MESSAGE);
    },
  );
});
