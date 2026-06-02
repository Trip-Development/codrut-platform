import { listQuestionnaireDefinitionStubs } from "@/api/questionnaires";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";
import { PlaceholderCard } from "@/components/shell/placeholder-card";

const statusLabel = {
  active: "Activ",
  draft: "Draft",
  planned: "Planificat",
};

export default async function TrainerQuestionnairesPage() {
  const definitions = await listQuestionnaireDefinitionStubs();

  return (
    <AppShell
      audience="trainer"
      eyebrow="Chestionare"
      title="Assignment si completare"
      description="Coordonarea formelor Codrut-native: definitii versionate, persoane asignate, drafturi si submit-uri."
      navItems={trainerNavItems}
      activeHref="/trainer/questionnaires"
    >
      <div className="grid gap-4 md:grid-cols-3">
        <PlaceholderCard title="Definitii" description="Lencioni si distress drivers sunt convertite; PCM, Phase si 360 asteapta surse." />
        <PlaceholderCard title="Asignari" description="Task-uri pe persoana, rol/grup si context organizational." />
        <PlaceholderCard title="Completare" description="Pornit, draft, trimis, validat si scorabil." />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {definitions.map((definition) => (
          <article key={definition.id} className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-burgundy/80">
                  {definition.audience}
                </p>
                <h2 className="mt-2 text-lg font-bold text-foreground">{definition.name}</h2>
              </div>
              <span className="rounded-full border border-[var(--border)] bg-surface-muted px-3 py-1 text-xs font-bold text-foreground/70">
                {statusLabel[definition.status]}
                {definition.version ? ` v${definition.version}` : ""}
              </span>
            </div>
            <p className="mt-3 text-sm leading-6 text-foreground/65">{definition.description}</p>
            <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-2">
              <div className="rounded-xl border border-[var(--border)] bg-surface-muted px-3 py-2">
                <dt className="text-xs font-bold uppercase tracking-[0.12em] text-foreground/45">Items</dt>
                <dd className="mt-1 font-semibold text-foreground">{definition.estimatedItems ?? "TBD"}</dd>
              </div>
              <div className="rounded-xl border border-[var(--border)] bg-surface-muted px-3 py-2">
                <dt className="text-xs font-bold uppercase tracking-[0.12em] text-foreground/45">Source</dt>
                <dd className="mt-1 truncate font-semibold text-foreground">{definition.source ?? "Pending"}</dd>
              </div>
            </dl>
          </article>
        ))}
      </div>
    </AppShell>
  );
}
