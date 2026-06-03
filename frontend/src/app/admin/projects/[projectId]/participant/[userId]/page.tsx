import TrainerParticipantReportPage from "../../../../../trainer/projects/[projectId]/participants/[participantId]/page";

type AdminParticipantAliasPageProps = {
  params: Promise<{ projectId: string; userId: string }>;
};

export default async function AdminParticipantAliasPage({ params }: AdminParticipantAliasPageProps) {
  const { projectId, userId } = await params;

  return (
    <TrainerParticipantReportPage
      params={Promise.resolve({
        projectId,
        participantId: userId,
      })}
    />
  );
}
