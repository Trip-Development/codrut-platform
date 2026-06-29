import Link from "next/link";

import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";

export default async function ParticipantFinalEvaluationPage() {
  const requestOptions = await getServerApiRequestOptions();
  const summary = await getParticipantWorkspaceSummary(requestOptions);
  const completed = summary.tasks.filter((task) => task.status === "completed").length;
  const total = summary.tasks.length;
  const hasOpenTasks = summary.tasks.some((task) => task.status !== "completed");

  return (
    <AppShell
      audience="participant"
      eyebrow={summary.projectName}
      title={hasOpenTasks ? "Mai ai sarcini de completat" : "Ai finalizat partea ta"}
      description={
        hasOpenTasks
          ? "Rezultatele proiectului sunt gestionate de trainer. Continuă sarcinile active din pagina de chestionare."
          : "Răspunsurile tale au fost salvate. Scorurile calculate sunt disponibile în tabul Rezultate după scorare."
      }
      navItems={participantNavItems}
      activeHref="/participant"
      userLabel={summary.anonymousName ?? "Profil anonim"}
    >
      <section className="surface-panel p-5 md:p-6">
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem] lg:items-start">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-burgundy/75">
              {hasOpenTasks ? "Acțiune necesară" : "Proiect închis pentru tine"}
            </p>
            <h2 className="mt-2 font-display text-2xl font-semibold text-foreground">
              {hasOpenTasks ? "Completează sarcinile rămase" : "Nu mai ai nimic de făcut acum"}
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-foreground/62">
              {hasOpenTasks
                ? "Pentru a închide participarea, finalizează toate chestionarele active. După trimitere, vei reveni la un ecran de finalizare."
                : "Datele tale intră în rezultatele agregate pentru echipe și manageri. În tabul Rezultate vezi scoruri sumarizate, profil PCM și interpretări disponibile; răspunsurile brute rămân private."}
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              {hasOpenTasks ? (
                <Link
                  href="/participant/questionnaires"
                  className="tap-soft inline-flex rounded-full bg-burgundy px-5 py-3 text-sm font-bold text-white shadow-sm hover:bg-burgundy-dark"
                >
                  Mergi la chestionare
                </Link>
              ) : (
                <Link
                  href="/participant"
                  className="tap-soft inline-flex rounded-full border border-[var(--border)] bg-surface px-5 py-3 text-sm font-bold text-foreground hover:border-burgundy/30 hover:text-burgundy"
                >
                  Înapoi la acasă
                </Link>
              )}
            </div>
          </div>

          <aside className="rounded-xl border border-[var(--border)] bg-surface-muted p-5">
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-foreground/45">Completare</p>
            <p className="mt-3 text-3xl font-semibold text-foreground">
              {completed}/{total}
            </p>
            <p className="mt-2 text-sm leading-6 text-foreground/62">
              {total === 0
                ? "Nu există sarcini active pentru acest cont."
                : hasOpenTasks
                  ? "Finalizează sarcinile rămase înainte de termen."
                  : "Toate sarcinile disponibile au fost trimise."}
            </p>
          </aside>
        </div>
      </section>

      <section className="mt-5 grid gap-4 md:grid-cols-3">
        <InfoCard title="Ce se întâmplă cu răspunsurile" text="Trainerul le folosește pentru raportare agregată, progres de proiect și analiză de echipă." />
        <InfoCard title="Ce vezi tu" text="Starea de completare, sarcinile active, profilul PCM și scorurile sumarizate disponibile după scorare." />
        <InfoCard title="Ce nu afișăm" text="Răspunsuri brute sau răspunsurile individuale ale altor persoane." />
      </section>
    </AppShell>
  );
}

function InfoCard({ title, text }: { title: string; text: string }) {
  return (
    <article className="surface-panel p-5">
      <h3 className="text-sm font-bold text-foreground">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-foreground/62">{text}</p>
    </article>
  );
}
