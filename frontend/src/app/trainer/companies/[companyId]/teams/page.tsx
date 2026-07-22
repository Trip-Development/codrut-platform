import { notFound } from "next/navigation";

import { getCompanyDetail, getCompanyTeamMemberships } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { LazyTeamsWorkspace } from "./LazyTeamsWorkspace";

export default async function CompanyTeamsPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const [{ companyId }, requestOptions] = await Promise.all([
    params,
    getServerApiRequestOptions(),
  ]);
  const company = await getCompanyDetail(companyId, requestOptions);

  if (!company) {
    notFound();
  }

  const memberships = await Promise.all(
    company.teams.map(async (team) => [
      team.id,
      await getCompanyTeamMemberships(company.id, team.id, requestOptions),
    ] as const),
  );

  return (
    <LazyTeamsWorkspace
      companyId={company.id}
      initialTeams={company.teams}
      participants={company.participants}
      initialMembershipsByTeam={Object.fromEntries(memberships)}
    />
  );
}
