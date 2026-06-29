import Link from "next/link";

import { getQuestionnaireDefinition, getQuestionnaireResponse } from "@/api/questionnaires";
import { getServerApiRequestOptions } from "@/api/server-request";
import { QuestionnaireRunner } from "@/components/questionnaires/questionnaire-runner";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";
import { safeReturnHref } from "./return-href";

type ParticipantQuestionnaireRunPageProps = {
  params: Promise<{ key: string }>;
  searchParams: Promise<{ assignmentId?: string; access?: string; returnTo?: string; target?: string }>;
};

export default async function ParticipantQuestionnaireRunPage({
  params,
  searchParams,
}: ParticipantQuestionnaireRunPageProps) {
  const { key } = await params;
  const { assignmentId, access, returnTo, target } = await searchParams;
  const safeReturnTo = safeReturnHref(returnTo, access === "secure" ? "/" : "/participant/questionnaires", {
    secureInvite: access === "secure",
  });
  const requestOptions = await getServerApiRequestOptions();
  const [definition, responseRecord] = await Promise.all([
    getQuestionnaireDefinition(key, requestOptions),
    assignmentId ? getQuestionnaireResponse(assignmentId, requestOptions) : Promise.resolve(null),
  ]);

  if (access === "secure") {
    return (
      <main className="min-h-screen bg-background px-4 py-8 text-foreground md:px-6">
        <div className="mx-auto max-w-5xl">
          <section className="surface-panel mb-5 p-5">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-burgundy/75">Chestionar securizat</p>
            <h1 className="mt-2 text-2xl font-semibold text-foreground">{definition?.title ?? "Chestionar indisponibil"}</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/62">
              Completezi formularul prin link securizat. Nu ai nevoie de meniul complet de participant pentru această sarcină.
            </p>
          </section>
          {definition ? (
            <QuestionnaireRunner
              definition={definition}
              assignmentId={assignmentId}
              initialAnswers={responseRecord?.answers}
              initialStatus={responseRecord?.status}
              returnHref={safeReturnTo}
              returnLabel="Înapoi la invitație"
              targetLabel={target}
            />
          ) : (
            <section className="rounded-xl border border-[var(--border)] bg-surface p-6 text-center shadow-sm">
              <h2 className="text-xl font-bold text-foreground">Chestionarul nu este disponibil</h2>
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
      eyebrow="Chestionar"
      title={definition?.title ?? "Chestionar indisponibil"}
      description="Completează răspunsurile în ritmul tău. Draftul și trimiterea folosesc sarcina din link când este disponibilă."
      navItems={participantNavItems}
      activeHref="/participant/questionnaires"
    >
      {definition ? (
        <QuestionnaireRunner
          definition={definition}
          assignmentId={assignmentId}
          initialAnswers={responseRecord?.answers}
          initialStatus={responseRecord?.status}
          returnHref={safeReturnTo}
          returnLabel="Înapoi la chestionare"
          targetLabel={target}
        />
      ) : (
        <section className="rounded-xl border border-[var(--border)] bg-surface p-6 shadow-sm max-w-lg mx-auto text-center space-y-4 my-8">
          <h2 className="text-xl font-bold text-foreground">Chestionarul nu este disponibil</h2>
          <p className="text-sm leading-relaxed text-foreground/70">
            Formularul solicitat nu a putut fi încărcat. Este posibil ca linkul să fie incorect sau chestionarul să nu mai fie activ.
          </p>
          <div className="pt-2">
            <Link
              href="/participant/questionnaires"
              className="tap-soft inline-flex items-center justify-center rounded-full bg-burgundy px-5 py-3 text-sm font-bold text-white hover:bg-burgundy/90 transition"
            >
              Înapoi la chestionare
            </Link>
          </div>
        </section>
      )}
    </AppShell>
  );
}
