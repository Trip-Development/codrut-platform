import { redirect } from "next/navigation";

type TrainerParticipantReportPageProps = {
  params: Promise<{ projectId: string }>;
};

export default async function TrainerParticipantReportPage({ params }: TrainerParticipantReportPageProps) {
  const { projectId } = await params;

  redirect(`/trainer/companies/${projectId}/reports`);
}
