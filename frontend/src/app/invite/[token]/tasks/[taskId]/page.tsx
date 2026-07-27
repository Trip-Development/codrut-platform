import Link from "next/link";

import { safeReturnHref } from "@/app/participant/questionnaires/[key]/return-href";
import {
  nextPendingReviewTask,
  safeReviewTargetLabel,
} from "@/app/participant/task-display";
import { inviteTaskHref, resolveInviteBundle } from "@/api/invites";
import {
  getSecureQuestionnaireDefinition,
  getSecureQuestionnaireResponse,
} from "@/api/questionnaires";
import { getServerApiRequestOptions } from "@/api/server-request";
import { EmptyState } from "@/components/presentation/empty-state";
import { LazyQuestionnaireRunner } from "@/components/questionnaires/lazy-questionnaire-runner";
import { serverLinkButtonClassName } from "@/components/ui/server-link-button";

type SecureTaskRunnerPageProps = {
  params: Promise<{ token: string; taskId: string }>;
  searchParams: Promise<{ returnTo?: string; target?: string }>;
};

export default async function SecureTaskRunnerPage({
  params,
  searchParams,
}: SecureTaskRunnerPageProps) {
  const [{ token, taskId }, { returnTo, target }, requestOptions] = await Promise.all([
    params,
    searchParams,
    getServerApiRequestOptions("participant"),
  ]);
  const defaultReturnTo = `/invite/${encodeURIComponent(token)}`;
  const safeReturnTo = safeReturnHref(returnTo, defaultReturnTo, { secureInvite: true });

  const [responseRecord, definition, inviteBundle] = await Promise.all([
    getSecureQuestionnaireResponse(token, taskId, requestOptions),
    getSecureQuestionnaireDefinition(token, taskId, requestOptions),
    resolveInviteBundle(token),
  ]);
  const nextTask =
    inviteBundle.state === "valid"
      ? nextPendingReviewTask(inviteBundle.tasks, taskId)
      : undefined;
  const nextTaskHref = nextTask
    ? inviteTaskHref(
        {
          ...nextTask,
          targetLabel: safeReviewTargetLabel(nextTask.targetLabel),
        },
        { returnTo: safeReturnTo, inviteToken: token },
      )
    : undefined;

  return (
    <main className="min-h-[100dvh] bg-background px-4 py-8 text-foreground md:px-6">
      <div className="mx-auto max-w-6xl">
        <h1 className="sr-only">{definition?.title ?? "Sarcină indisponibilă"}</h1>
        {definition ? (
          <LazyQuestionnaireRunner
            definition={definition}
            assignmentId={taskId}
            initialAnswers={responseRecord?.answers}
            initialStatus={responseRecord?.status}
            returnHref={safeReturnTo}
            returnLabel="Înapoi la invitație"
            targetLabel={target}
            secureInviteToken={token}
            nextTaskHref={nextTaskHref}
          />
        ) : (
          <EmptyState
            title="Sarcina nu este disponibilă"
            description="Nu am putut valida această sarcină pentru invitația curentă."
            action={(
              <Link href={safeReturnTo} className={serverLinkButtonClassName()}>Înapoi la invitație</Link>
            )}
          />
        )}
      </div>
    </main>
  );
}
