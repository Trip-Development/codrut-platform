import { notFound } from "next/navigation";

import { getCompanyDetail, getParticipantViewAudits } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { ParticipantViewAuditsList } from "./ParticipantViewAuditsList";

export default async function CompanyAuditPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const [{ companyId }, requestOptions] = await Promise.all([
    params,
    getServerApiRequestOptions("trainer"),
  ]);

  const [company, audits] = await Promise.all([
    getCompanyDetail(companyId, requestOptions).catch(() => null),
    getParticipantViewAudits(companyId, 200, requestOptions).catch(() => []),
  ]);

  if (!company) {
    notFound();
  }

  return <ParticipantViewAuditsList companyId={companyId} audits={audits} />;
}
