import { describe, expect, it } from "vitest";

import { participantNavItems } from "./nav";

describe("participant navigation", () => {
  it("keeps production navigation limited to persisted participant surfaces", () => {
    expect(participantNavItems).toEqual([
      { href: "/participant", label: "Acasă", shortLabel: "Acasă" },
      { href: "/participant/questionnaires", label: "Chestionare", shortLabel: "Forme" },
      { href: "/participant/account", label: "Cont", shortLabel: "Cont" },
    ]);
    expect(participantNavItems.map((item) => item.href)).not.toContain("/participant/chat");
    expect(participantNavItems.map((item) => item.href)).not.toContain("/participant/final-evaluation");
  });
});
