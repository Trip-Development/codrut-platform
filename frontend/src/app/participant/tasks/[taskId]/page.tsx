import Link from "next/link";

import { getQuestionnaireDefinition, getQuestionnaireResponse } from "@/api/questionnaires";
import { getServerApiRequestOptions } from "@/api/server-request";
import { QuestionnaireRunner } from "@/components/questionnaires/questionnaire-runner";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";
import { safeReturnHref } from "@/app/participant/questionnaires/[key]/return-href";

type TaskRunnerPageProps = {
  params: Promise<{ taskId: string }>;
  searchParams: Promise<{ access?: string; returnTo?: string; target?: string }>;
};

export default async function TaskRunnerPage({ params, searchParams }: TaskRunnerPageProps) {
  const { taskId } = await params;
  const { access, returnTo, target } = await searchParams;
  const secureInvite = access === "secure";
  const safeReturnTo = safeReturnHref(returnTo, secureInvite ? "/" : "/participant/questionnaires", {
    secureInvite,
  });
  const requestOptions = await getServerApiRequestOptions();

  // 1. Fetch the response for this assignment to find the questionnaire key and version
  const responseRecord = await getQuestionnaireResponse(taskId, requestOptions);

  // 2. Fetch the corresponding questionnaire definition based on the key
  const definition = responseRecord
    ? await getQuestionnaireDefinition(
        `${responseRecord.questionnaire_key}@${responseRecord.questionnaire_version}`,
        requestOptions,
      )
    : null;

  if (secureInvite) {
    return (
      <main className="min-h-screen bg-background px-4 py-8 text-foreground md:px-6">
        <div className="mx-auto max-w-5xl">
          <section className="surface-panel mb-5 p-5">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-burgundy/75">Chestionar securizat</p>
            <h1 className="mt-2 text-2xl font-semibold text-foreground">{definition?.title ?? "Sarcină indisponibilă"}</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/62">
              Completezi formularul prin link securizat. Nu ai nevoie de meniul complet de participant pentru această sarcină.
            </p>
          </section>
          {definition ? (
            <QuestionnaireRunner
              definition={definition}
              assignmentId={taskId}
              initialAnswers={responseRecord?.answers}
              initialStatus={responseRecord?.status}
              returnHref={safeReturnTo}
              returnLabel="Înapoi la invitație"
              targetLabel={target}
            />
          ) : (
            <section className="surface-panel p-6 text-center">
              <h2 className="text-xl font-bold text-foreground">Sarcina nu este disponibilă</h2>
              <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-foreground/62">
                Nu am putut găsi chestionarul asociat acestei sarcini.
              </p>
              <Link
                href={safeReturnTo}
                className="tap-soft mt-4 inline-flex rounded-full bg-burgundy px-4 py-3 text-sm font-bold text-white"
              >
                Înapoi la invitație
              </Link>
            </section>
          )}
        </div>
      </main>
    );
  }

  return (
    <AppShell
      audience="participant"
      eyebrow="Sarcină"
      title={definition?.title ?? "Sarcină indisponibilă"}
      description="Completează răspunsurile în ritmul tău. Draftul se salvează automat pe măsură ce selectezi opțiunile."
      navItems={participantNavItems}
      activeHref="/participant/questionnaires"
    >
      {definition ? (
        <QuestionnaireRunner
          definition={definition}
          assignmentId={taskId}
          initialAnswers={responseRecord?.answers}
          initialStatus={responseRecord?.status}
          returnHref={safeReturnTo}
          returnLabel="Înapoi la chestionare"
          targetLabel={target}
        />
      ) : (
        <section className="rounded-xl border border-[var(--border)] bg-surface p-5 shadow-sm">
          <h2 className="text-lg font-bold text-foreground">Sarcina nu este disponibilă</h2>
          <p className="mt-2 text-sm leading-6 text-foreground/65">
            Nu am putut găsi chestionarul asociat acestei sarcini. Verifică dacă linkul este corect sau contactează trainerul.
          </p>
          <Link
            href="/participant/questionnaires"
            className="tap-soft mt-4 inline-flex rounded-full bg-burgundy px-4 py-3 text-sm font-bold text-white"
          >
            Înapoi la chestionare
          </Link>
        </section>
      )}
    </AppShell>
  );
}
