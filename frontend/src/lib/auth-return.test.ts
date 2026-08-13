import { describe, expect, it } from "vitest";

import {
  participantLoginHref,
  safeParticipantReturnTo,
  safeTrainerReturnTo,
  trainerLoginHref,
} from "./auth-return";

describe("trainer auth return paths", () => {
  it("keeps internal trainer destinations and their query parameters", () => {
    expect(safeTrainerReturnTo("/trainer/projects/project-1?tab=results")).toBe(
      "/trainer/projects/project-1?tab=results",
    );
    expect(trainerLoginHref("/trainer/projects/project-1?tab=results")).toBe(
      "/trainer/login?returnTo=%2Ftrainer%2Fprojects%2Fproject-1%3Ftab%3Dresults",
    );
  });

  it("builds participant login links only for specific safe destinations", () => {
    expect(participantLoginHref("/participant")).toBe("/login");
    expect(participantLoginHref("/participant/questionnaires/q1?assignmentId=a1")).toBe(
      "/login?returnTo=%2Fparticipant%2Fquestionnaires%2Fq1%3FassignmentId%3Da1",
    );
    expect(participantLoginHref("https://evil.example/participant")).toBe("/login");
  });

  it.each([
    null,
    "",
    "/participant",
    "/trainer/login",
    "//example.com/trainer",
    "https://example.com/trainer",
    "javascript:alert(1)",
  ])("falls back to trainer home for unsafe destination %s", (value) => {
    expect(safeTrainerReturnTo(value)).toBe("/trainer");
    expect(trainerLoginHref(value)).toBe("/trainer/login");
  });
});

describe("participant auth return paths", () => {
  it("keeps participant and invite destinations", () => {
    expect(safeParticipantReturnTo("/participant?project=one")).toBe(
      "/participant?project=one",
    );
    expect(safeParticipantReturnTo("/invite/signed-token")).toBe(
      "/invite/signed-token",
    );
  });

  it.each([
    null,
    "",
    "/trainer",
    "/login",
    "//example.com/invite/token",
    "https://example.com/participant",
  ])("falls back for unsafe participant destination %s", (value) => {
    expect(safeParticipantReturnTo(value)).toBe("/participant");
  });
});
