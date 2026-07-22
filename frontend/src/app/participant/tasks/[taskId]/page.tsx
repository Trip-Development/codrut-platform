import Link from "next/link";

import { getAssignedQuestionnaireDefinition, getQuestionnaireResponse } from "@/api/questionnaires";
import { getServerApiRequestOptions } from "@/api/server-request";
import { EmptyState } from "@/components/presentation/empty-state";
import { LazyQuestionnaireRunner } from "@/components/questionnaires/lazy-questionnaire-runner";
import { serverLinkButtonClassName } from "@/components/ui/server-link-button";
import { safeReturnHref } from "@/app/participant/questionnaires/[key]/return-href";

type TaskRunnerPageProps = {
  params: Promise<{ taskId: string }>;
  searchParams: Promise<{ access?: string; returnTo?: string; target?: string }>;
};

export default async function TaskRunnerPage({ params, searchParams }: TaskRunnerPageProps) {
  const [{ taskId }, { access, returnTo, target }, requestOptions] = await Promise.all([
    params,
    searchParams,
    getServerApiRequestOptions(),
  ]);
  const secureInvite = access === "secure";
  const safeReturnTo = safeReturnHref(returnTo, secureInvite ? "/" : "/participant/questionnaires", {
    secureInvite,
  });

  const responseRecord = await getQuestionnaireResponse(taskId, requestOptions);

  const definition = responseRecord
    ? await getAssignedQuestionnaireDefinition(taskId, requestOptions)
    : null;

  if (secureInvite) {
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
            />
          ) : (
            <EmptyState
              title="Sarcina nu este disponibilă"
              description="Nu am putut găsi chestionarul asociat acestei sarcini."
              action={(
                <Link href={safeReturnTo} className={serverLinkButtonClassName()}>Înapoi la invitație</Link>
              )}
            />
          )}
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-[100dvh] bg-background px-4 py-6 text-foreground md:px-6 lg:py-8">
      <div className="mx-auto max-w-6xl">
        <h1 className="sr-only">{definition?.title ?? "Sarcină indisponibilă"}</h1>
        {definition ? (
          <LazyQuestionnaireRunner
            definition={definition}
            assignmentId={taskId}
            initialAnswers={responseRecord?.answers}
            initialStatus={responseRecord?.status}
            returnHref={safeReturnTo}
            returnLabel="Înapoi la chestionare"
            targetLabel={target}
          />
        ) : (
          <EmptyState
            className="mx-auto my-8 max-w-lg"
            title="Sarcina nu este disponibilă"
            description="Nu am putut găsi chestionarul asociat acestei sarcini. Verifică dacă linkul este corect sau contactează trainerul."
            action={(
              <Link href="/participant/questionnaires" className={serverLinkButtonClassName()}>Înapoi la chestionare</Link>
            )}
          />
        )}
      </div>
    </main>
  );
}
