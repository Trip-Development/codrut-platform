import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";

export default async function ParticipantFinalEvaluationPage() {
  const requestOptions = await getServerApiRequestOptions();
  const summary = await getParticipantWorkspaceSummary(requestOptions);
  const completed = summary.tasks.filter((task) => task.status === "completed").length;
  const total = summary.tasks.length;

  return (
    <AppShell
      audience="participant"
      eyebrow="Rezultate"
      title="Rezultatele tale"
      description="Preview pentru zona de rezultate participant. Rapoartele finale vor apărea aici după validarea trainerului."
      navItems={participantNavItems}
      activeHref="/participant/final-evaluation"
      userLabel={summary.anonymousName ?? "Profil anonim"}
    >
      <section className="rounded-[1.75rem] border border-[var(--border)] bg-surface p-5 shadow-sm md:p-6">
        <div className="grid gap-4 md:grid-cols-3">
          <ResultTile label="Progres chestionare" value={`${completed}/${total}`} detail="Sarcini finalizate în proiectul curent." />
          <ResultTile label="Profil anonim" value={summary.anonymousName ?? "Nealocat"} detail="Identitatea folosită în experiența ta." />
          <ResultTile label="Raport final" value="În pregătire" detail="Disponibil după agregare și validare." />
        </div>
      </section>
    </AppShell>
  );
}

function ResultTile({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <article className="rounded-2xl border border-[var(--border)] bg-background p-4 transition hover:border-burgundy/24 hover:bg-surface-muted/45">
      <p className="text-xs font-bold uppercase tracking-[0.14em] text-foreground/45">{label}</p>
      <p className="mt-3 text-xl font-semibold text-foreground">{value}</p>
      <p className="mt-2 text-sm leading-6 text-foreground/58">{detail}</p>
    </article>
  );
}
