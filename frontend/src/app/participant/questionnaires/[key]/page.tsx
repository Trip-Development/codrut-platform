import Link from "next/link";

import { getQuestionnaireDefinition } from "@/api/questionnaires";
import { QuestionnaireRunner } from "@/components/questionnaires/questionnaire-runner";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";

type ParticipantQuestionnaireRunPageProps = {
  params: Promise<{ key: string }>;
  searchParams: Promise<{ assignmentId?: string }>;
};

export default async function ParticipantQuestionnaireRunPage({
  params,
  searchParams,
}: ParticipantQuestionnaireRunPageProps) {
  const { key } = await params;
  const { assignmentId } = await searchParams;
  const definition = await getQuestionnaireDefinition(key);

  return (
    <AppShell
      audience="participant"
      eyebrow="Chestionar"
      title={definition?.title ?? "Chestionar indisponibil"}
      description="Completeaza raspunsurile in ritmul tau. Draftul si trimiterea folosesc assignment-ul din link cand este disponibil."
      navItems={participantNavItems}
      activeHref="/participant/questionnaires"
    >
      {definition ? (
        <QuestionnaireRunner definition={definition} assignmentId={assignmentId} />
      ) : (
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-6 shadow-sm max-w-lg mx-auto text-center space-y-4 my-8">
          <h2 className="text-xl font-bold text-foreground">Chestionarul nu este disponibil</h2>
          <p className="text-sm leading-relaxed text-foreground/70">
            Formularul solicitat nu a putut fi încărcat. Este posibil ca linkul să fie incorect sau chestionarul să nu mai fie activ.
          </p>
          <div className="pt-2">
            <Link
              href="/participant/questionnaires"
              className="tap-soft inline-flex items-center justify-center rounded-xl bg-burgundy px-5 py-3 text-sm font-bold text-white hover:bg-burgundy/90 transition"
            >
              Înapoi la chestionare
            </Link>
          </div>
        </section>
      )}
    </AppShell>
  );
}
