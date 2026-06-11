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
      title="Formele asignate ție"
      description="Alege formularul primit prin linkul securizat. Layout-ul este gândit pentru completare rapidă, fără zgomot vizual."
      navItems={participantNavItems}
      activeHref="/participant/questionnaires"
    >
      <div className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
        {activeDefinitions.map((definition) => (
          <article
            key={definition.id}
            className="grid gap-4 border-b border-[var(--border)] px-5 py-4 last:border-b-0 md:grid-cols-[1fr_auto] md:items-center"
          >
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-base font-semibold text-foreground">{definition.name}</h2>
                <span className="rounded-full bg-surface-muted px-2.5 py-1 text-xs font-semibold text-foreground/55">
                  v{definition.version}
                </span>
              </div>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/62">{definition.description}</p>
              <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs font-semibold text-foreground/45">
                <span>{definition.audience}</span>
                <span>{definition.estimatedItems} {definition.estimatedItems === 1 ? "întrebare" : "întrebări"}</span>
                <span>{definition.status}</span>
              </div>
            </div>
            <Link
              href={`/participant/questionnaires/${definition.id}`}
              className="tap-soft inline-flex justify-center rounded-xl bg-foreground px-4 py-2.5 text-sm font-semibold text-background hover:bg-burgundy hover:text-white"
            >
              Deschide
            </Link>
          </article>
        ))}
      </div>
    </AppShell>
  );
}
