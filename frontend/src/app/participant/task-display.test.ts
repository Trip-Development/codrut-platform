import { describe, expect, it } from "vitest";

import type { InviteTask, InviteTaskStatus } from "@/api/invites";
import { groupParticipantTasks, nextPendingReviewTask } from "./task-display";

function reviewTask(id: string, status: InviteTaskStatus): InviteTask {
  return {
    id,
    assignmentId: id,
    title: "Review 360",
    status,
    detail: "Feedback confidențial",
    href: `/participant/tasks/${id}`,
    targetLabel: `Persoana ${id}`,
    estimatedMinutes: 10,
    questionnaireKey: "boss_360",
    projectId: "project-1",
    projectName: "Pilot",
    assignmentRoundId: "round-1",
  };
}

describe("nextPendingReviewTask", () => {
  it("ignores assignments that are not part of a 360 review group", () => {
    const task = {
      ...reviewTask("single", "not_started"),
      questionnaireKey: "lencioni",
    };

    expect(nextPendingReviewTask([task], task.assignmentId)).toBeUndefined();
  });

  it("wraps to an earlier pending review after the last assignment", () => {
    const earlier = reviewTask("earlier", "not_started");
    const current = reviewTask("current", "completed");

    expect(nextPendingReviewTask([earlier, current], current.assignmentId)).toBe(earlier);
  });

  it("returns no continuation when every other review is complete", () => {
    const current = reviewTask("current", "completed");
    const other = reviewTask("other", "completed");

    expect(nextPendingReviewTask([current, other], current.assignmentId)).toBeUndefined();
  });

  it("keeps iCARE variants and pinned definitions in separate groups", () => {
    const boss = {
      ...reviewTask("boss", "not_started"),
      questionnaireKey: "boss_360",
      questionnaireDefinitionId: "definition-boss",
    };
    const icare = {
      ...reviewTask("icare", "not_started"),
      questionnaireKey: "icare",
      questionnaireDefinitionId: "definition-icare",
    };
    const newerBossDefinition = {
      ...reviewTask("boss-new", "not_started"),
      questionnaireKey: "boss_360",
      questionnaireDefinitionId: "definition-boss-v2",
    };

    expect(groupParticipantTasks([boss, icare, newerBossDefinition])).toHaveLength(3);
  });
});
