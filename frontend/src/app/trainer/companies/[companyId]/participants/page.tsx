import { notFound } from "next/navigation";

import { getCompanyDetail } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { CompanyParticipantsTable } from "../CompanyParticipantsTable";

export default async function CompanyParticipantsPage({
  params,
}: {
  params: Promise<{ companyId: string }>;
}) {
  const [{ companyId }, requestOptions] = await Promise.all([
    params,
    getServerApiRequestOptions(),
  ]);
  const company = await getCompanyDetail(companyId, requestOptions);

  if (!company) notFound();

  const participants = [...company.participants].sort((first, second) =>
    first.full_name.localeCompare(second.full_name, "ro"),
  );

  return (
    <div className="flex flex-col gap-5">
      {company.dataErrors?.map((error) => (
        <InlineFeedback key={error} tone="danger">{error}</InlineFeedback>
      ))}
      <CompanyParticipantsTable participants={participants} />
    </div>
  );
}
