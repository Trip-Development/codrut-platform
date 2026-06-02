import Link from "next/link";

import { getQuestionnaireDefinition } from "@/api/questionnaires";
import { QuestionnaireRunner } from "@/components/questionnaires/questionnaire-runner";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";

type ParticipantQuestionnaireRunPageProps = {
  params: Promise<{ key: string }>;
};

export default async function ParticipantQuestionnaireRunPage({
  params,
}: ParticipantQuestionnaireRunPageProps) {
  const { key } = await params;
  const definition = await getQuestionnaireDefinition(key);

  return (
    <AppShell
      audience="participant"
      eyebrow="Chestionar"
      title={definition?.title ?? "Chestionar indisponibil"}
      description="Runner generic pentru definitii versionate. Submit-ul si drafturile vor fi conectate in task-ul urmator."
      navItems={participantNavItems}
      activeHref="/participant/questionnaires"
    >
      {definition ? (
        <QuestionnaireRunner definition={definition} />
      ) : (
        <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
          <h2 className="text-lg font-bold text-foreground">Definitia nu este disponibila</h2>
          <p className="mt-2 text-sm leading-6 text-foreground/65">
            Verifica daca backendul ruleaza si daca formularul este in catalogul aprobat.
          </p>
          <Link
            href="/participant/questionnaires"
            className="tap-soft mt-4 inline-flex rounded-xl bg-burgundy px-4 py-3 text-sm font-bold text-white"
          >
            Inapoi la chestionare
          </Link>
        </section>
      )}
    </AppShell>
  );
}
