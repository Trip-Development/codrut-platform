import Link from "next/link";

import { listQuestionnaireDefinitionStubs } from "@/api/questionnaires";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";

export default async function ParticipantQuestionnairesPage() {
  const activeDefinitions = (await listQuestionnaireDefinitionStubs()).filter(
    (definition) => definition.status === "active",
  );

  return (
    <AppShell
      audience="participant"
      eyebrow="Chestionare"
      title="Formele asignate tie"
      description="Flow-ul real va folosi definitii versionate si submit server-validat. Acum pastram suprafata vizuala."
      navItems={participantNavItems}
      activeHref="/participant/questionnaires"
    >
      <div className="grid gap-4 lg:grid-cols-2">
        {activeDefinitions.map((definition) => (
          <article key={definition.id} className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-burgundy/80">
                  {definition.audience}
                </p>
                <h2 className="mt-2 text-lg font-bold text-foreground">{definition.name}</h2>
              </div>
              <span className="rounded-full bg-burgundy px-3 py-1 text-xs font-bold text-white">
                v{definition.version}
              </span>
            </div>
            <p className="mt-3 text-sm leading-6 text-foreground/65">{definition.description}</p>
            <div className="mt-4 rounded-xl border border-[var(--border)] bg-surface-muted px-3 py-2 text-sm font-semibold text-foreground/70">
              {definition.estimatedItems} items · runner disponibil
            </div>
            <Link
              href={`/participant/questionnaires/${definition.id}`}
              className="tap-soft mt-4 inline-flex rounded-xl bg-burgundy px-4 py-3 text-sm font-bold text-white"
            >
              Deschide
            </Link>
          </article>
        ))}
      </div>
    </AppShell>
  );
}
