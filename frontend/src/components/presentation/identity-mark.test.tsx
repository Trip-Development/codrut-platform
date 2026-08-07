import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import {
  IdentityMark,
  identityInitials,
  identityMarkVisual,
} from "./identity-mark";

afterEach(cleanup);

describe("IdentityMark", () => {
  it("keeps a linked participant aligned with the persisted account palette", () => {
    expect(identityMarkVisual("person", "participant:first", 12_345)).toEqual(
      identityMarkVisual("person", "participant:second", 12_345),
    );
  });

  it("keeps fallback identities stable while giving entity kinds distinct treatments", () => {
    const person = identityMarkVisual("person", "participant:person-1");
    const repeatedPerson = identityMarkVisual("person", "participant:person-1");
    const contact = identityMarkVisual("contact", "contact:person-1");
    const company = identityMarkVisual("company", "company:person-1");

    expect(repeatedPerson).toEqual(person);
    expect(contact.style.backgroundImage).not.toBe(person.style.backgroundImage);
    expect(company.style.backgroundImage).not.toBe(person.style.backgroundImage);
  });

  it("renders Romanian-aware initials and the requested entity shape", () => {
    render(
      <IdentityMark
        kind="company"
        label="Școala Meridian"
        seed="company:meridian"
        size="md"
      />,
    );

    expect(screen.getByText("ȘM")).toBeTruthy();
    expect(document.querySelector("[data-identity-kind='company']")).toBeTruthy();
  });

  it.each([
    ["Andrei Pop", "AP"],
    ["andrei.pop", "AP"],
    ["Participant", "P"],
    ["", "?"],
  ])("derives initials from %j", (label, expected) => {
    expect(identityInitials(label)).toBe(expected);
  });
});
