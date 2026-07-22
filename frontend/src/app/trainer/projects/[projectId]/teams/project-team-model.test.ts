import { describe, expect, it } from "vitest";

import type { CompanyParticipant, CompanyTeam, CompanyTeamMembership } from "@/api/companies";
import { buildProjectTeamRows } from "./project-team-model";

describe("buildProjectTeamRows", () => {
  it("keeps only project participants and lists leaders first", () => {
    const team: CompanyTeam = {
      id: "team-1",
      company_id: "company-1",
      name: "Leadership",
      type: "leadership",
    };
    const participants: CompanyParticipant[] = [
      participant("member", "Ana Membru"),
      participant("leader", "Zoe Lider"),
    ];
    const memberships: CompanyTeamMembership[] = [
      membership("outside", "outside", "member"),
      membership("member", "member", "member"),
      membership("leader", "leader", "leader"),
    ];

    const [row] = buildProjectTeamRows(
      [team],
      { [team.id]: memberships },
      participants,
    );

    expect(row.members.map((entry) => entry.participant.id)).toEqual(["leader", "member"]);
  });
});

function participant(id: string, name: string): CompanyParticipant {
  return {
    id,
    full_name: name,
    email: `${id}@example.test`,
    reports_to_name: null,
    position: null,
    location: null,
    role_group: null,
    pcm_profile: null,
    user_id: null,
  };
}

function membership(
  id: string,
  participantProfileId: string,
  role: CompanyTeamMembership["role"],
): CompanyTeamMembership {
  return {
    id,
    team_id: "team-1",
    participant_profile_id: participantProfileId,
    role,
  };
}
