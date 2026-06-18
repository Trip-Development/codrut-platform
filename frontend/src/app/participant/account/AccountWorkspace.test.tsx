import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import type { SessionState } from "@/api/auth";
import { AccountWorkspace } from "./AccountWorkspace";

const session: SessionState = {
  state: "authenticated",
  user: {
    id: "participant-1",
    name: "Ana Participant",
    role: "participant",
  },
};

describe("AccountWorkspace", () => {
  afterEach(() => {
    cleanup();
  });

  it("displays the PCM base and phase without showing a CTA button", () => {
    render(
      <AccountWorkspace
        session={session}
        summary={{
          projectName: "Leadership septembrie",
          participantFullName: "Ana Participant",
          participantEmail: "ana@example.com",
          companyName: "Michelin",
          pcmBase: "harmonizer",
          pcmPhase: "thinker",
          tasks: [],
        }}
      />,
    );

    expect(screen.getByText("harmonizer")).toBeDefined();
    expect(screen.getByText("thinker")).toBeDefined();
    expect(screen.queryByRole("link", { name: "Actualizează PCM" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Vezi chestionarele" })).toBeNull();
  });

  it("displays 'Necompletată' when PCM base and phase are missing", () => {
    render(
      <AccountWorkspace
        session={session}
        summary={{
          projectName: "Leadership septembrie",
          participantFullName: "Ana Participant",
          participantEmail: "ana@example.com",
          companyName: "Michelin",
          pcmBase: null,
          pcmPhase: null,
          tasks: [],
        }}
      />,
    );

    expect(screen.getAllByText("Necompletată")).toHaveLength(2);
  });
});
