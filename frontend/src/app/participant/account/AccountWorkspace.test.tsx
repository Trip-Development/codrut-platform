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

  it("shows operational profile data and the participant result visibility rule", () => {
    render(
      <AccountWorkspace
        session={session}
        summary={{
          projectName: "Leadership septembrie",
          participantFullName: "Ana Participant",
          participantEmail: "ana@example.com",
          companyName: "Michelin",
          tasks: [],
        }}
      />,
    );

    expect(screen.getByText("ana@example.com")).toBeDefined();
    expect(screen.getByText("Michelin")).toBeDefined();
    expect(screen.getByText("Scoruri și interpretări sumarizate în tabul Rezultate")).toBeDefined();
    expect(screen.getByText("Răspunsurile brute nu sunt afișate în cont")).toBeDefined();
    expect(screen.getByText("Schimbă parola")).toBeDefined();
    expect(screen.queryByText("Armonizator")).toBeNull();
    expect(screen.queryByText("Gânditor")).toBeNull();
    expect(screen.queryByRole("link", { name: "Actualizează PCM" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Vezi chestionarele" })).toBeNull();
  });

  it("does not show missing PCM placeholders to participants", () => {
    render(
      <AccountWorkspace
        session={session}
        summary={{
          projectName: "Leadership septembrie",
          participantFullName: "Ana Participant",
          participantEmail: "ana@example.com",
          companyName: "Michelin",
          tasks: [],
        }}
      />,
    );

    expect(screen.queryByText("Necompletată")).toBeNull();
    expect(screen.getByText("Rezultate")).toBeDefined();
  });
});
