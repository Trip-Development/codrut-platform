import Link from "next/link";
import type { ReactNode } from "react";

import {
  getAssignedQuestionnaireDefinition,
  getQuestionnaireResponse,
  isQuestionnaireSessionError,
  QuestionnaireRequestError,
  type QuestionnaireDefinition,
  type QuestionnaireResponseRecord,
} from "@/api/questionnaires";
import { getServerApiRequestOptions } from "@/api/server-request";
import { EmptyState } from "@/components/presentation/empty-state";
import { LazyQuestionnaireRunner } from "@/components/questionnaires/lazy-questionnaire-runner";
import { serverLinkButtonClassName } from "@/components/ui/server-link-button";
import { safeReturnHref } from "./return-href";

type ParticipantQuestionnaireRunPageProps = {
  params: Promise<{ key: string }>;
  searchParams: Promise<{ assignmentId?: string; access?: string; returnTo?: string; target?: string }>;
};

export default async function ParticipantQuestionnaireRunPage({
  params,
  searchParams,
}: ParticipantQuestionnaireRunPageProps) {
  const [{ key }, { assignmentId, access, returnTo, target }, requestOptions] = await Promise.all([
    params,
    searchParams,
    getServerApiRequestOptions("participant"),
  ]);
  const safeReturnTo = safeReturnHref(returnTo, access === "secure" ? "/" : "/participant/questionnaires", {
    secureInvite: access === "secure",
  });
  let responseRecord: QuestionnaireResponseRecord | null = null;
  let definition: QuestionnaireDefinition | null = null;
  let loadError: unknown = null;
  if (assignmentId) {
    try {
      [responseRecord, definition] = await Promise.all([
        getQuestionnaireResponse(assignmentId, requestOptions),
        getAssignedQuestionnaireDefinition(assignmentId, requestOptions),
      ]);
    } catch (error) {
      loadError = error;
    }
  }
  const retryHref = questionnaireRetryHref(key, { assignmentId, access, returnTo, target });

  if (access === "secure") {
    return (
      <main className="min-h-[100dvh] bg-background px-4 py-8 text-foreground md:px-6">
        <div className="mx-auto max-w-6xl">
          <h1 className="sr-only">{definition?.title ?? "Chestionar indisponibil"}</h1>
          {loadError ? (
            <QuestionnaireLoadFailure error={loadError} retryHref={retryHref} returnHref={safeReturnTo} />
          ) : definition ? (
            <LazyQuestionnaireRunner
              definition={definition}
              assignmentId={assignmentId}
              initialAnswers={responseRecord?.answers}
              initialStatus={responseRecord?.status}
              returnHref={safeReturnTo}
              returnLabel="Înapoi la invitație"
              targetLabel={target}
            />
          ) : (
            <EmptyState
              title="Chestionarul nu este disponibil"
              description="Formularul asociat linkului securizat nu a putut fi încărcat."
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
    <QuestionnaireFocusShell title={definition?.title ?? "Chestionar indisponibil"}>
      {loadError ? (
        <QuestionnaireLoadFailure error={loadError} retryHref={retryHref} returnHref={safeReturnTo} />
      ) : definition ? (
        <LazyQuestionnaireRunner
          definition={definition}
          assignmentId={assignmentId}
          initialAnswers={responseRecord?.answers}
          initialStatus={responseRecord?.status}
          returnHref={safeReturnTo}
          returnLabel="Înapoi la chestionare"
          targetLabel={target}
        />
      ) : (
        <EmptyState
          className="mx-auto my-8 max-w-lg"
          title="Chestionarul nu este disponibil"
          description="Formularul solicitat nu a putut fi încărcat. Este posibil ca linkul să fie incorect sau chestionarul să nu mai fie activ."
          action={(
            <Link href="/participant/questionnaires" className={serverLinkButtonClassName()}>Înapoi la chestionare</Link>
          )}
        />
      )}
    </QuestionnaireFocusShell>
  );
}

function QuestionnaireLoadFailure({
  error,
  retryHref,
  returnHref,
}: {
  error: unknown;
  retryHref: string;
  returnHref: string;
}) {
  const sessionError = isQuestionnaireSessionError(error);
  const description = sessionError
    ? "Sesiunea a expirat sau nu mai are acces la această sarcină. Autentifică-te din nou din invitația primită."
    : error instanceof QuestionnaireRequestError && error.status >= 500
      ? "Serverul nu a putut încărca sarcina. Răspunsurile existente nu au fost modificate."
      : "Nu am putut încărca sarcina. Verifică conexiunea și încearcă din nou.";

  return (
    <EmptyState
      className="mx-auto my-8 max-w-lg"
      title={sessionError ? "Sesiunea trebuie reînnoită" : "Chestionarul nu s-a încărcat"}
      description={description}
      action={(
        <div className="flex flex-wrap justify-center gap-3">
          <Link href={sessionError ? returnHref : retryHref} className={serverLinkButtonClassName()}>
            {sessionError ? "Înapoi la invitație" : "Încearcă din nou"}
          </Link>
        </div>
      )}
    />
  );
}

function questionnaireRetryHref(
  key: string,
  params: { assignmentId?: string; access?: string; returnTo?: string; target?: string },
): string {
  const query = new URLSearchParams();
  if (params.assignmentId) query.set("assignmentId", params.assignmentId);
  if (params.access) query.set("access", params.access);
  if (params.returnTo) query.set("returnTo", params.returnTo);
  if (params.target) query.set("target", params.target);
  const suffix = query.toString();
  return `/participant/questionnaires/${encodeURIComponent(key)}${suffix ? `?${suffix}` : ""}`;
}

function QuestionnaireFocusShell({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <main className="min-h-[100dvh] bg-background px-4 py-6 text-foreground md:px-6 lg:py-8">
      <div className="mx-auto max-w-6xl">
        <h1 className="sr-only">{title}</h1>
        {children}
      </div>
    </main>
  );
}
