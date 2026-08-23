import { notFound } from "next/navigation";

import { getParticipantWorkspacePreview } from "@/api/companies";
import { getServerApiRequestOptions } from "@/api/server-request";
import { ParticipantPreviewView } from "./ParticipantPreviewView";

type PreviewPageSearchParams = {
  projectId?: string;
  cycleId?: string;
};

export default async function ParticipantPreviewPage({
  params,
  searchParams,
}: {
  params: Promise<{ companyId: string; participantId: string }>;
  searchParams?: Promise<PreviewPageSearchParams>;
}) {
  const [{ companyId, participantId }, resolvedSearchParams, requestOptions] = await Promise.all([
    params,
    searchParams ? searchParams : Promise.resolve<PreviewPageSearchParams>({}),
    getServerApiRequestOptions("trainer"),
  ]);

  try {
    const summary = await getParticipantWorkspacePreview(
      companyId,
      participantId,
      {
        projectId: resolvedSearchParams.projectId,
        cycleId: resolvedSearchParams.cycleId,
      },
      requestOptions,
    );

    return (
      <ParticipantPreviewView
        companyId={companyId}
        projectId={resolvedSearchParams.projectId}
        summaryData={summary}
      />
    );
  } catch {
    notFound();
  }
}
