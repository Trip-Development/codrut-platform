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

  it("links the PCM action to the persisted assignment task when available", () => {
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
          tasks: [
            {
              id: "assignment-1",
              title: "Profil PCM",
              status: "not_started",
              detail: "Completează baza și faza PCM.",
              href: "/participant/questionnaires/pcm_base?assignmentId=assignment-1",
              assignmentId: "assignment-1",
              targetLabel: "Autoevaluare",
              estimatedMinutes: 3,
              questionnaireKey: "pcm_base",
            },
          ],
        }}
      />,
    );

    expect(screen.getByRole("link", { name: "Actualizează PCM" }).getAttribute("href")).toBe(
      "/participant/questionnaires/pcm_base?assignmentId=assignment-1",
    );
  });

  it("falls back to the assigned questionnaire list instead of an unsavable direct PCM route", () => {
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

    expect(screen.getByRole("link", { name: "Vezi chestionarele" }).getAttribute("href")).toBe(
      "/participant/questionnaires",
    );
  });
});
