import Link from "next/link";
import { notFound } from "next/navigation";
import { AlertCircleIcon, ArrowLeftIcon } from "lucide-react";

import { CompanyMutationError, getParticipantWorkspacePreview } from "@/api/companies";
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
  } catch (error) {
    if (error instanceof CompanyMutationError && error.code === "http_404") {
      notFound();
    }
    const errorMessage =
      error instanceof Error ? error.message : "Nu am putut deschide vizualizarea pentru acest participant.";
    const exitHref = resolvedSearchParams.projectId
      ? `/trainer/projects/${resolvedSearchParams.projectId}/participants`
      : `/trainer/companies/${companyId}`;

    return (
      <div className="mx-auto max-w-3xl px-4 py-12">
        <Link
          href={exitHref}
          className="inline-flex items-center gap-2 text-sm font-semibold text-muted-foreground hover:text-foreground mb-6"
        >
          <ArrowLeftIcon className="size-4" aria-hidden="true" />
          Înapoi la participanți
        </Link>
        <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-6 text-foreground">
          <div className="flex items-start gap-3">
            <AlertCircleIcon className="size-5 text-destructive shrink-0 mt-0.5" aria-hidden="true" />
            <div>
              <h2 className="text-lg font-semibold text-destructive">Nu am putut deschide vizualizarea ca participant</h2>
              <p className="mt-2 text-sm text-muted-foreground">{errorMessage}</p>
              <p className="mt-3 text-xs text-muted-foreground">
                Se deschide în mod citire și se înregistrează în jurnalul de acces. Dacă problema persistă, verifică dacă participantul aparține acestei companii.
              </p>
            </div>
          </div>
        </div>
      </div>
    );
  }
}

