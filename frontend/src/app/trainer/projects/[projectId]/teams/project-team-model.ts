import type {
  CompanyParticipant,
  CompanyTeam,
  CompanyTeamMembership,
} from "@/api/companies";

export type ProjectTeamRow = {
  team: CompanyTeam;
  members: Array<{
    membership: CompanyTeamMembership;
    participant: CompanyParticipant;
  }>;
};

export function buildProjectTeamRows(
  teams: CompanyTeam[],
  membershipsByTeam: Record<string, CompanyTeamMembership[]>,
  participants: CompanyParticipant[],
): ProjectTeamRow[] {
  const participantById = new Map(
    participants.map((participant) => [participant.id, participant]),
  );

  return teams.map((team) => ({
    team,
    members: (membershipsByTeam[team.id] ?? [])
      .flatMap((membership) => {
        const participant = participantById.get(membership.participant_profile_id);
        return participant ? [{ membership, participant }] : [];
      })
      .sort((first, second) => {
        if (first.membership.role !== second.membership.role) {
          return first.membership.role === "leader" ? -1 : 1;
        }
        return first.participant.full_name.localeCompare(second.participant.full_name, "ro-RO");
      }),
  }));
}
