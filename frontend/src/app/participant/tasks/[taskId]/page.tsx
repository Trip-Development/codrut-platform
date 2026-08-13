import Link from "next/link";
import { redirect } from "next/navigation";

import {
  getQuestionnaireResponse,
  isQuestionnaireSessionError,
  QuestionnaireRequestError,
} from "@/api/questionnaires";
import { getServerApiRequestOptions } from "@/api/server-request";
import { EmptyState } from "@/components/presentation/empty-state";
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
    getServerApiRequestOptions("participant"),
  ]);
  const secureInvite = access === "secure";
  const safeReturnTo = safeReturnHref(returnTo, secureInvite ? "/" : "/participant/questionnaires", {
    secureInvite,
  });

  let responseRecord;
  try {
    responseRecord = await getQuestionnaireResponse(taskId, requestOptions);
  } catch (error) {
    return (
      <TaskLoadFailure
        error={error}
        retryHref={taskRetryHref(taskId, { access, returnTo, target })}
        returnHref={safeReturnTo}
      />
    );
  }

  if (responseRecord) {
    redirect(questionnaireHref(responseRecord.questionnaire_key, taskId, { access, returnTo, target }));
  }

  if (secureInvite) {
    return (
      <main className="min-h-[100dvh] bg-background px-4 py-8 text-foreground md:px-6">
        <div className="mx-auto max-w-6xl">
          <h1 className="sr-only">Sarcină indisponibilă</h1>
          <EmptyState
            title="Sarcina nu este disponibilă"
            description="Nu am putut găsi chestionarul asociat acestei sarcini."
            action={(
              <Link href={safeReturnTo} className={serverLinkButtonClassName()}>Înapoi la invitație</Link>
            )}
          />
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-[100dvh] bg-background px-4 py-6 text-foreground md:px-6 lg:py-8">
      <div className="mx-auto max-w-6xl">
        <h1 className="sr-only">Sarcină indisponibilă</h1>
        <EmptyState
          className="mx-auto my-8 max-w-lg"
          title="Sarcina nu este disponibilă"
          description="Nu am putut găsi chestionarul asociat acestei sarcini. Verifică dacă linkul este corect sau contactează trainerul."
          action={(
            <Link href="/participant/questionnaires" className={serverLinkButtonClassName()}>Înapoi la chestionare</Link>
          )}
        />
      </div>
    </main>
  );
}

function TaskLoadFailure({
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
    <main className="min-h-[100dvh] bg-background px-4 py-6 text-foreground md:px-6 lg:py-8">
      <h1 className="sr-only">Sarcină indisponibilă</h1>
      <EmptyState
        className="mx-auto my-8 max-w-lg"
        title={sessionError ? "Sesiunea trebuie reînnoită" : "Chestionarul nu s-a încărcat"}
        description={description}
        action={(
          <Link
            href={sessionError ? returnHref : retryHref}
            className={serverLinkButtonClassName()}
          >
            {sessionError ? "Înapoi la invitație" : "Încearcă din nou"}
          </Link>
        )}
      />
    </main>
  );
}

function questionnaireHref(
  key: string,
  taskId: string,
  params: { access?: string; returnTo?: string; target?: string },
): string {
  const query = taskQuery({ assignmentId: taskId, ...params });
  return `/participant/questionnaires/${encodeURIComponent(key)}?${query}`;
}

function taskRetryHref(
  taskId: string,
  params: { access?: string; returnTo?: string; target?: string },
): string {
  const query = taskQuery(params);
  return `/participant/tasks/${encodeURIComponent(taskId)}${query ? `?${query}` : ""}`;
}

function taskQuery(params: {
  assignmentId?: string;
  access?: string;
  returnTo?: string;
  target?: string;
}): string {
  const query = new URLSearchParams();
  if (params.assignmentId) query.set("assignmentId", params.assignmentId);
  if (params.access) query.set("access", params.access);
  if (params.returnTo) query.set("returnTo", params.returnTo);
  if (params.target) query.set("target", params.target);
  return query.toString();
}
