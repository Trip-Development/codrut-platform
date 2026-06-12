import { getParticipantWorkspaceSummary } from "@/api/participants";
import { getServerApiRequestOptions } from "@/api/server-request";
import { getScoringResult, type ScoringResultRecord } from "@/api/trainer";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";

const distressLabels: Record<string, string> = {
  be_strong: "Fii puternic",
  be_perfect: "Fii perfect",
  try_hard: "Străduiește-te",
  hurry_up: "Grăbește-te",
  please_people: "Mulțumește-i pe alții",
};

const distressGuidance: Record<string, { stressors: string; behaviour: string; allowers: string[] }> = {
  be_strong: {
    stressors: "Vulnerabilitatea, cererea de ajutor și situațiile în care trebuie exprimate emoții pot crește presiunea.",
    behaviour: "Sub stres poate apărea retragere, autocritică și tendința de a ascunde dificultatea.",
    allowers: ["Este în regulă să exprim ce simt.", "Este în regulă să cer ajutor.", "Nu trebuie să știu toate răspunsurile."],
  },
  be_perfect: {
    stressors: "Standardele scăzute, comportamentele ilogice, riscul de a greși sau ratarea obiectivelor pot deveni stresori.",
    behaviour: "Sub presiune poate apărea control crescut, focalizare rigidă pe obiectiv și dificultate în a delega.",
    allowers: ["Suficient de bine poate fi potrivit scopului.", "Este în regulă să greșesc.", "Nu trebuie să fie perfect din prima."],
  },
  try_hard: {
    stressors: "Critica, acuzația că nu depui efort, rutina și percepția de iresponsabilitate pot activa driverul.",
    behaviour: "Sub stres crește efortul, dar rezultatul poate rămâne neclar sau blocat.",
    allowers: ["Pot lăsa lucrurile să se întâmple.", "Pot finaliza.", "Efortul nu este același lucru cu rezultatul."],
  },
  hurry_up: {
    stressors: "Așteptarea, tăcerea, lipsa stimulilor sau timpul de gândire pot fi resimțite ca presiune.",
    behaviour: "Sub stres poate apărea grabă, agitație, trecere rapidă de la un eveniment la altul și erori făcute în viteză.",
    allowers: ["Este în regulă să mă relaxez.", "Este în regulă să iau timp pentru gândire.", "Pot încetini înainte să decid."],
  },
  please_people: {
    stressors: "Ignorarea, critica, conflictul și teama de a supăra pe cineva pot împinge propriile priorități în plan secund.",
    behaviour: "Sub stres poate apărea dificultatea de a spune nu, încărcare excesivă și impulsul de a salva pe toată lumea.",
    allowers: ["Este în regulă să spun nu.", "Este în regulă să spun ce am nevoie.", "Pot clarifica limitele fără să rup relația."],
  },
};

export default async function ParticipantFinalEvaluationPage() {
  const requestOptions = await getServerApiRequestOptions();
  const summary = await getParticipantWorkspaceSummary(requestOptions);
  const completed = summary.tasks.filter((task) => task.status === "completed").length;
  const total = summary.tasks.length;
  const distressTasks = summary.tasks.filter(
    (task) => task.questionnaireKey === "distress_drivers" && task.status === "completed",
  );
  const distressResults = (
    await Promise.all(
      distressTasks.map(async (task) => ({
        task,
        result: await getScoringResult(task.assignmentId, requestOptions),
      })),
    )
  ).filter((item): item is { task: (typeof distressTasks)[number]; result: ScoringResultRecord } => Boolean(item.result));

  return (
    <AppShell
      audience="participant"
      eyebrow="Rezultate"
      title="Rezultatele tale"
      description="Rezultatele personale apar aici după ce un chestionar cu feedback individual este completat și calculat."
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

      <section className="mt-5 rounded-[1.75rem] border border-[var(--border)] bg-surface p-5 shadow-sm md:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-burgundy/75">Driveri de distress</p>
            <h2 className="mt-1 text-xl font-semibold text-foreground">Profilul tău de presiune</h2>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/62">
              Scorurile sunt calculate din materialul trainerului. Un scor mai mare indică un driver mai prezent în situații de presiune.
            </p>
          </div>
          <span className="rounded-full border border-green-200 bg-green-50 px-3 py-1 text-xs font-bold text-green-800">
            {distressResults.length > 0 ? "Calculat" : "În așteptare"}
          </span>
        </div>

        {distressResults.length === 0 ? (
          <div className="mt-5 rounded-2xl border border-dashed border-[var(--border)] bg-background/70 p-5 text-sm leading-6 text-foreground/58">
            Nu există încă un rezultat Distress Drivers finalizat pentru profilul tău.
          </div>
        ) : (
          <div className="mt-5 grid gap-4 lg:grid-cols-2">
            {distressResults.map(({ task, result }) => (
              <DistressResultCard key={task.assignmentId} result={result} />
            ))}
          </div>
        )}
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

function DistressResultCard({ result }: { result: ScoringResultRecord }) {
  const rows = Object.entries(result.scores)
    .map(([key, value]) => ({ key, value: Number(value) || 0 }))
    .sort((a, b) => b.value - a.value);
  const top = rows[0];

  return (
    <article className="rounded-2xl border border-[var(--border)] bg-background p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.12em] text-foreground/45">Driver principal</p>
          <h3 className="mt-1 text-lg font-semibold text-foreground">
            {top ? distressLabels[top.key] ?? top.key : "Indisponibil"}
          </h3>
        </div>
        <span className="rounded-full bg-burgundy/10 px-3 py-1 text-sm font-bold text-burgundy">
          {top?.value ?? 0}
        </span>
      </div>
      {top && distressGuidance[top.key] ? (
        <div className="mt-3 space-y-3 text-sm leading-6 text-foreground/62">
          <p>
            <strong className="font-bold text-foreground/75">Stresori probabili: </strong>
            {distressGuidance[top.key].stressors}
          </p>
          <p>
            <strong className="font-bold text-foreground/75">Comportament sub stres: </strong>
            {distressGuidance[top.key].behaviour}
          </p>
          <div>
            <p className="font-bold text-foreground/75">Permisiuni utile:</p>
            <ul className="mt-1 list-disc space-y-1 pl-5">
              {distressGuidance[top.key].allowers.map((allower) => (
                <li key={allower}>{allower}</li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
      <div className="mt-4 space-y-2">
        {rows.map((row) => (
          <div key={row.key}>
            <div className="flex items-center justify-between gap-3 text-xs font-semibold text-foreground/58">
              <span>{distressLabels[row.key] ?? row.key}</span>
              <span>{row.value}</span>
            </div>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-surface-muted">
              <div className="h-full rounded-full bg-burgundy" style={{ width: `${Math.min(row.value, 100)}%` }} />
            </div>
          </div>
        ))}
      </div>
    </article>
  );
}
