import { redirect } from "next/navigation";

type Props = {
  params: Promise<{ projectId: string }>;
};

/**
 * Legacy redirect: /trainer/projects/[id] → /trainer/companies/[id]
 * Project detail views are now company detail views.
 */
export default async function TrainerProjectDetailRedirectPage({ params }: Props) {
  const { projectId } = await params;
  redirect(`/trainer/companies/${projectId}`);
}
