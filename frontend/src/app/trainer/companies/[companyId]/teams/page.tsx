import {
  getCompanyParticipants,
  getCompanyTeamMemberships,
  getCompanyTeams,
} from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { TeamsWorkspace } from "./TeamsWorkspace";

export default async function CompanyTeamsPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const { companyId } = await params;
  const requestOptions = await getServerApiRequestOptions();
  const [teams, participants] = await Promise.all([
    getCompanyTeams(companyId, requestOptions),
    getCompanyParticipants(companyId, requestOptions),
  ]);

  const membershipEntries = await Promise.all(
    teams.map(async (team) => [
      team.id,
      await getCompanyTeamMemberships(companyId, team.id, requestOptions),
    ] as const),
  );

  return (
    <TeamsWorkspace
      companyId={companyId}
      initialTeams={teams}
      participants={participants}
      initialMembershipsByTeam={Object.fromEntries(membershipEntries)}
    />
  );
}
