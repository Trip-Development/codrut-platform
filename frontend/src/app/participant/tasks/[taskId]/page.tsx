import Link from "next/link";

import { getQuestionnaireDefinition, getQuestionnaireResponse } from "@/api/questionnaires";
import { QuestionnaireRunner } from "@/components/questionnaires/questionnaire-runner";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";

type TaskRunnerPageProps = {
  params: Promise<{ taskId: string }>;
};

export default async function TaskRunnerPage({ params }: TaskRunnerPageProps) {
  const { taskId } = await params;

  // 1. Fetch the response for this assignment to find the questionnaire key and version
  const responseRecord = await getQuestionnaireResponse(taskId);

  // 2. Fetch the corresponding questionnaire definition based on the key
  const definition = responseRecord
    ? await getQuestionnaireDefinition(responseRecord.questionnaire_key)
    : null;

  return (
    <AppShell
      audience="participant"
      eyebrow="Sarcina"
      title={definition?.title ?? "Sarcină indisponibilă"}
      description="Completează răspunsurile în ritmul tău. Draftul se salvează automat pe măsură ce selectezi opțiunile."
      navItems={participantNavItems}
      activeHref="/participant"
    >
      {definition ? (
        <QuestionnaireRunner
          definition={definition}
          assignmentId={taskId}
          initialAnswers={responseRecord?.answers}
        />
      ) : (
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
          <h2 className="text-lg font-bold text-foreground">Sarcina nu este disponibilă</h2>
          <p className="mt-2 text-sm leading-6 text-foreground/65">
            Nu am putut găsi chestionarul asociat acestei sarcini. Verifică dacă linkul este corect sau contactează trainerul.
          </p>
          <Link
            href="/participant"
            className="tap-soft mt-4 inline-flex rounded-xl bg-burgundy px-4 py-3 text-sm font-bold text-white"
          >
            Înapoi acasă
          </Link>
        </section>
      )}
    </AppShell>
  );
}
