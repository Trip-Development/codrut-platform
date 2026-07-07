import { describe, expect, it } from "vitest";

import { PASSWORD_POLICY_MESSAGE, validatePasswordPolicy } from "./password-policy";

describe("password policy", () => {
  it("accepts eight-character passwords when all required character classes are present", () => {
    expect(validatePasswordPolicy("Aa12345!")).toBeNull();
  });

  it.each(["Short1!", "lowercase1!", "UPPERCASE1!", "NoNumber!", "NoSpecial1"])(
    "rejects incomplete password %s",
    (password) => {
      expect(validatePasswordPolicy(password)).toBe(PASSWORD_POLICY_MESSAGE);
    },
  );
});
