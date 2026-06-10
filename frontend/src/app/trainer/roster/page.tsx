import { redirect } from "next/navigation";

export default async function TrainerRosterRedirectPage({
  searchParams,
}: {
  searchParams: Promise<{ companyId?: string }>;
}) {
  const { companyId } = await searchParams;
  redirect(companyId ? `/trainer/companies/${companyId}/participants` : "/trainer/companies");
}
