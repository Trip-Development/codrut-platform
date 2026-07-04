import { describe, expect, it } from "vitest";

import { participantNavItems } from "./nav";

describe("participant navigation", () => {
  it("keeps participant navigation on persisted product surfaces", () => {
    expect(participantNavItems).toEqual([
      { href: "/participant", label: "Acasă", shortLabel: "Acasă" },
      { href: "/participant/questionnaires", label: "Chestionare", shortLabel: "Forme" },
      { href: "/participant/results", label: "Rezultate", shortLabel: "Rez." },
      { href: "/participant/account", label: "Cont", shortLabel: "Cont" },
    ]);
  });
});
