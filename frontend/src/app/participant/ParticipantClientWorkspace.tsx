"use client";

import Link from "next/link";
import { useId, useState } from "react";

import type { SessionState } from "@/api/auth";
import { inviteTaskHref, type InviteTask } from "@/api/invites";
import { formatPcmLabel, getPcmProfile } from "@/api/pcm";
import type { ParticipantWorkspaceResult } from "@/api/participants";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";

type ParticipantClientWorkspaceProps = {
  session: SessionState;
  summaryData: {
    projectName: string;
    companyName?: string;
    participantFullName?: string;
    anonymousName?: string | null;
    participantEmail: string;
    deadlineLabel: string;
    tasks: InviteTask[];
    pcmBase?: string | null;
    pcmPhase?: string | null;
    results: ParticipantWorkspaceResult[];
  };
};

const driverLabels: Record<string, string> = {
  be_strong: "Fii Puternic",
  be_perfect: "Fii Perfect",
  try_hard: "Străduiește-te",
  hurry_up: "Grăbește-te",
  please_people: "Mulțumește-i pe alții",
};

const driverExplanations: Record<string, string> = {
  be_strong:
    "Feedback: sub presiune poți simți că trebuie să rămâi tare, autonom și să nu arăți cât te costă efortul. Punctul util de lucru este să ceri sprijin mai devreme, să spui explicit ce resurse îți lipsesc și să nu transformi rezistența într-o obligație permanentă.",
  be_perfect:
    "Feedback: standardele înalte ajută calitatea, dar peste prag pot duce la control excesiv, verificări repetate și dificultatea de a considera ceva suficient de bun. Punctul util de lucru este să definești dinainte nivelul acceptabil și să separi lucrurile critice de cele unde 80% este suficient.",
  try_hard:
    "Feedback: energia de a încerca poate fi valoroasă, dar peste prag poate arăta mult efort consumat fără finalizare proporțională. Punctul util de lucru este să alegi mai puține direcții, să clarifici ce înseamnă terminat și să urmărești rezultatul, nu doar intensitatea efortului.",
  hurry_up:
    "Feedback: viteza poate crea ritm, dar peste prag poate aduce urgență constantă, multitasking și decizii luate înainte ca informația importantă să fie clară. Punctul util de lucru este să introduci pauze scurte de prioritizare și să alegi explicit ce nu faci acum.",
  please_people:
    "Feedback: atenția la ceilalți susține colaborarea, dar peste prag poate duce la evitare de conflict, acord rapid și limite personale neclare. Punctul util de lucru este să exprimi dezacordul mai devreme, să verifici cererea reală și să spui ce poți face fără să preiei tot.",
};

const lencioniLabels: Record<string, string> = {
  absence_of_trust: "Absența încrederii",
  fear_of_conflict: "Teama de conflict",
  lack_of_commitment: "Lipsa angajamentului",
  avoidance_of_accountability: "Evitarea responsabilității",
  inattention_to_results: "Neatenția la rezultate",
};

const icareLabels: Record<string, string> = {
  icare_01_dezvolta_oamenii: "Dezvoltă oamenii",
  icare_02_conduce_prin_puterea_exemplului: "Conduce prin exemplu",
  icare_03_creeaza_un_mediu_care_stimuleaza_implicarea: "Creează implicare",
  icare_04_promotor_al_colaborarii: "Promotor al colaborării",
  icare_05_ancorat_in_realitate: "Ancorat în realitate",
  icare_06_aduce_claritate: "Aduce claritate",
  icare_07_modestie: "Modestie",
  icare_08_inteligenta_emotionala_si_situationala: "Inteligență emoțională și situațională",
  icare_09_deschis_catre_lume: "Deschis către lume",
  icare_10_ambitios_pentru_companie: "Ambițios pentru companie",
  icare_11_grija_egala_pentru_angajati_si_clienti: "Grijă pentru angajați și clienți",
  icare_12_agilitate_antreprenoriala: "Agilitate antreprenorială",
  icare_13_decizii_cat_mai_aproape_de_teren: "Decizii aproape de teren",
  icare_14_cultiva_inteligenta_colectiva: "Cultivă inteligența colectivă",
  icare_15_ajuta_echipa: "Ajută echipa",
};

const statusCopy: Record<InviteTask["status"], { label: string; helper: string }> = {
  not_started: {
    label: "De început",
    helper: "Alege un moment liniștit pentru completare.",
  },
  in_progress: {
    label: "În lucru",
    helper: "Continuă de unde ai rămas.",
  },
  completed: {
    label: "Finalizat",
    helper: "Răspunsurile au fost salvate.",
  },
};

export function ParticipantClientWorkspace({ session, summaryData }: ParticipantClientWorkspaceProps) {
  const realIdentity = summaryData.participantFullName || session.user.name || summaryData.participantEmail;
  const anonymousIdentity = summaryData.anonymousName || "Profil anonim";
  const displayIdentity = `${anonymousIdentity}${realIdentity ? ` (${realIdentity})` : ""}`;
  const pendingTasks = summaryData.tasks.filter((task) => task.status !== "completed");
  const completedTasksCount = summaryData.tasks.length - pendingTasks.length;
  const tasksProgressPct =
    summaryData.tasks.length > 0 ? Math.round((completedTasksCount / summaryData.tasks.length) * 100) : 100;
  const nextTask = pendingTasks[0];
  const hasAnyTasks = summaryData.tasks.length > 0;
  const isComplete = hasAnyTasks && pendingTasks.length === 0;
  const resultCount = summaryData.results.length;

  return (
    <AppShell
      audience="participant"
      eyebrow={summaryData.projectName}
      title={`Bună, ${anonymousIdentity}`}
      description="Lucrezi sub identitate anonimă. Completează chestionarele active, iar progresul se actualizează din baza de date."
      navItems={participantNavItems}
      activeHref="/participant"
      userLabel={anonymousIdentity}
    >
      <div className="space-y-7">
        <section className="surface-panel p-5 md:p-6">
          <div className="grid gap-6 xl:grid-cols-[1.35fr_0.85fr]">
            <div className="min-w-0">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-burgundy/80">
                    Prioritatea ta acum
                  </p>
                  <h2 className="mt-2 font-display text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
                    {pendingTasks.length > 0 ? "Chestionare active" : isComplete ? "Ai finalizat partea ta" : "Ești la zi"}
                  </h2>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/62">
                    {isComplete ? (
                      "Nu mai ai nimic de făcut acum. Rezultatele calculate sunt în tabul dedicat."
                    ) : (
                      <>
                        Fiecare sarcină vine din invitațiile pregătite de trainer. Identitatea afișată pentru acest proiect este{" "}
                        <strong className="text-foreground">{displayIdentity}</strong>.
                      </>
                    )}
                  </p>
                </div>
                <div className="w-fit rounded-xl bg-burgundy px-4 py-3 text-white shadow-sm">
                  <span className="block text-2xl font-semibold leading-none">{pendingTasks.length}</span>
                  <span className="mt-1 block text-xs font-semibold text-white/78">
                    {pendingTasks.length === 1 ? "sarcină activă" : "sarcini active"}
                  </span>
                </div>
              </div>

              {pendingTasks.length > 0 ? (
                <div className="mt-6 grid gap-3">
                  {pendingTasks.map((task) => (
                    <TaskCard key={task.assignmentId ?? task.id} task={task} />
                  ))}
                </div>
              ) : (
                <div className="mt-6 rounded-xl border border-success/24 bg-surface-muted p-5">
                  <h3 className="text-base font-semibold text-foreground">
                    {isComplete ? "Participarea ta este completă" : "Nu ai sarcini active"}
                  </h3>
                  <p className="mt-1 text-sm leading-6 text-foreground/62">
                    {isComplete
                      ? "Rezultatele tale sunt disponibile în tabul Rezultate pentru chestionarele care au scor calculat."
                      : "Când trainerul îți trimite o invitație nouă, o vei vedea aici și în pagina de chestionare."}
                  </p>
                </div>
              )}
            </div>

            <aside className="rounded-xl border border-[var(--border)] bg-surface-muted p-5">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.16em] text-foreground/48">Următorul pas</p>
                  <h3 className="mt-2 text-xl font-semibold text-foreground">
                    {nextTask ? nextTask.title : "Așteaptă următoarea invitație"}
                  </h3>
                </div>
                <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-success/20 text-success-ink">
                  <CheckIcon />
                </span>
              </div>
              <p className="mt-4 text-sm leading-6 text-foreground/62">
                {nextTask
                  ? "Deschide chestionarul, completează răspunsurile și revino aici pentru restul pașilor."
                  : isComplete
                    ? "Ai terminat sarcinile disponibile. Poți consulta scorurile în Rezultate."
                    : "Progresul tău rămâne salvat. Când apare o sarcină nouă, o vei vedea aici."}
              </p>
              <div className="mt-6 rounded-xl border border-[var(--border)] bg-surface p-4">
                <div className="mb-2 flex items-center justify-between text-xs font-bold text-foreground/55">
                  <span>Completare proiect</span>
                  <span>{tasksProgressPct}%</span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-burgundy/10">
                  <div className="h-full rounded-full bg-burgundy transition-all duration-200" style={{ width: `${tasksProgressPct}%` }} />
                </div>
              </div>
              <div className="mt-4 grid gap-3 text-sm">
                <ContextRow label="Companie" value={summaryData.companyName || "Companie neasociată"} />
                <ContextRow label="Identitate anonimă" value={displayIdentity} />
                <ContextRow label="Email" value={summaryData.participantEmail || "Email indisponibil"} />
              </div>
            </aside>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          <StatusCard label="Progres" value={`${tasksProgressPct}%`} detail={`${completedTasksCount}/${summaryData.tasks.length} sarcini finalizate`} tone="burgundy" />
          <StatusCard label="Rezultate" value={`${resultCount}`} detail="Chestionare finalizate cu scor disponibil." tone="green" />
          <StatusCard label="Proiect" value={summaryData.projectName} detail="Programul activ pentru invitațiile tale." tone="gray" />
        </section>

        <section className="surface-panel flex flex-col gap-4 p-5 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.16em] text-burgundy/75">Rezultate</p>
            <h2 className="mt-1 text-lg font-semibold text-foreground">Scorurile sunt într-un tab separat</h2>
            <p className="mt-1 text-sm leading-6 text-foreground/58">
              Acasă rămâne pentru progres și sarcini. Deschide rezultatele când vrei detaliile pe chestionar.
            </p>
          </div>
          <Link
            href="/participant/results"
            className="tap-soft inline-flex justify-center rounded-full bg-burgundy px-5 py-3 text-sm font-bold text-white shadow-sm hover:bg-burgundy-dark"
          >
            Vezi rezultatele
          </Link>
        </section>
      </div>
    </AppShell>
  );
}

function TaskCard({ task }: { task: InviteTask }) {
  const copy = statusCopy[task.status];

  return (
    <article className="group/task rounded-xl border border-[var(--border)] bg-surface p-4 shadow-sm transition hover:border-burgundy/24">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-full bg-burgundy/10 px-2.5 py-1 text-[11px] font-bold uppercase tracking-[0.12em] text-burgundy">
              {copy.label}
            </span>
            <span className="text-xs font-semibold text-foreground/45">{task.estimatedMinutes} min</span>
          </div>
          <h3 className="mt-3 text-lg font-semibold tracking-tight text-foreground">{task.title}</h3>
          <p className="mt-1.5 max-w-2xl text-sm leading-6 text-foreground/62">{task.detail}</p>
          <div className="mt-3 flex flex-wrap gap-2 text-xs font-semibold text-foreground/48">
            <span>{task.targetLabel}</span>
            <span aria-hidden="true">·</span>
            <span>{copy.helper}</span>
          </div>
        </div>
        {task.status === "completed" ? (
          <span className="status-pill border-success/25 bg-surface-muted px-5 py-3 text-sm text-success-ink">
            Finalizat
          </span>
        ) : (
          <Link
            href={inviteTaskHref(task, { returnTo: "/participant/questionnaires" })}
            className="tap-soft inline-flex items-center justify-center gap-2 rounded-full bg-burgundy px-5 py-3 text-sm font-bold text-white shadow-sm hover:bg-burgundy-dark"
          >
            Continuă
            <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.4" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14m-6-6 6 6-6 6" />
            </svg>
          </Link>
        )}
      </div>
    </article>
  );
}

function StatusCard({
  label,
  value,
  detail,
  tone,
}: {
  label: string;
  value: string;
  detail: string;
  tone: "burgundy" | "green" | "gray";
}) {
  return (
    <div className="surface-panel p-5">
      <p className="text-xs font-bold uppercase tracking-[0.16em] text-foreground/45">{label}</p>
      <p
        className={[
          "mt-2 line-clamp-2 text-2xl font-semibold tracking-tight",
          tone === "green" ? "text-success-ink" : tone === "burgundy" ? "text-burgundy" : "text-foreground",
        ].join(" ")}
      >
        {value}
      </p>
      <p className="mt-2 text-sm leading-6 text-foreground/58">{detail}</p>
    </div>
  );
}

function ContextRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-surface px-4 py-3">
      <span className="block text-xs font-semibold text-foreground/45">{label}</span>
      <span className="mt-1 block break-words text-sm font-bold text-foreground">{value}</span>
    </div>
  );
}

export function ParticipantResultsPanel({
  results,
  pcmBase,
  pcmPhase,
}: {
  results: ParticipantWorkspaceResult[];
  pcmBase?: string | null;
  pcmPhase?: string | null;
}) {
  return (
    <section className="space-y-4">
      <div className="surface-panel flex flex-col gap-4 p-5 md:flex-row md:items-start md:justify-between md:p-6">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-burgundy/75">Rezultatele tale</p>
          <h2 className="mt-2 font-display text-2xl font-semibold text-foreground">Scoruri și profil</h2>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-foreground/62">
            Vezi scorurile calculate din chestionarele finalizate. La driverii de stres sunt explicate doar scorurile peste 50, conform pragului folosit în materialul chestionarului.
            Pentru Lencioni și iCARE, explicațiile folosesc intervalele de scor salvate în definițiile chestionarelor.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <PcmResultChip label="Bază PCM" value={pcmBase} />
            <PcmResultChip label="Fază PCM" value={pcmPhase} />
          </div>
        </div>
        <Link
          href="/participant/questionnaires"
          className="tap-soft inline-flex justify-center rounded-full border border-burgundy/20 bg-surface px-4 py-3 text-sm font-bold text-burgundy hover:bg-burgundy hover:text-white"
        >
          Vezi chestionarele
        </Link>
      </div>

      {results.length > 0 ? (
        <div className="grid gap-4 xl:grid-cols-2">
          {results.map((result) => (
            <ResultCard key={result.assignmentId} result={result} />
          ))}
        </div>
      ) : (
        <div className="surface-panel p-5">
          <h3 className="text-base font-semibold text-foreground">Nu există scoruri calculate încă</h3>
          <p className="mt-1 text-sm leading-6 text-foreground/62">
            După ce finalizezi chestionarele cu scor, sumarul apare aici automat.
          </p>
        </div>
      )}
    </section>
  );
}

function PcmResultChip({ label, value }: { label: string; value?: string | null }) {
  const profile = getPcmProfile(value);
  const color = profile?.color ?? "var(--border)";
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-[var(--border)] bg-surface-muted px-3 py-2 text-xs font-bold text-foreground/70">
      <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
      {label}: <span className="text-foreground">{formatPcmLabel(value)}</span>
    </span>
  );
}

function ResultCard({ result }: { result: ParticipantWorkspaceResult }) {
  const kind = resultKind(result.questionnaireKey);
  const items = scoreItemsForResult(result, kind);
  const max = maxScoreForKind(kind);
  const average = averageScore(items);

  return (
    <article className="surface-panel p-4 md:p-5">
      <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-burgundy/75">{resultKindLabel(kind)}</p>
          <h3 className="mt-1 text-base font-semibold leading-6 text-foreground" title={result.title}>{result.title}</h3>
          <p className="mt-1 text-sm text-foreground/55">{result.targetLabel}</p>
          <p className="mt-2 text-xs font-semibold uppercase tracking-wider text-foreground/42">
            {items.length} dimensiuni · scor mediu {average === null ? "N/A" : formatScore(average)} · scală 0-{max}
          </p>
        </div>
        {result.primaryResult ? (
          <span className="w-fit rounded-full border border-[var(--border)] bg-surface-muted px-3 py-1.5 text-xs font-bold text-foreground/65">
            Principal: {labelForScore(result.primaryResult, kind)}
          </span>
        ) : null}
      </div>
      <div className="mt-4 grid gap-3">
        {items.map((item) => (
          <ScoreRow key={item.id} item={item} max={max} showExplanation={kind === "drivers" && item.score > 50} />
        ))}
      </div>
    </article>
  );
}

function ScoreRow({
  item,
  max,
  showExplanation,
}: {
  item: ScoreItem;
  max: number;
  showExplanation: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const feedbackId = useId();
  const width = Math.max(0, Math.min(100, (item.score / max) * 100));
  const tone = showExplanation ? "bg-burgundy" : "bg-success";
  const canExpand = showExplanation && Boolean(item.explanation);
  const content = (
    <>
      <span className="flex items-center justify-between gap-4">
        <span className="min-w-0">
          <span className="block text-sm font-bold leading-5 text-foreground">{item.label}</span>
          {item.interpretation ? (
            <span className="mt-1 block text-xs leading-5 text-foreground/56">{item.interpretation}</span>
          ) : null}
        </span>
        <span className="flex shrink-0 items-center gap-2">
          {canExpand ? (
            <span className="rounded-full bg-burgundy/10 px-2 py-1 text-[11px] font-bold text-burgundy">
              {expanded ? "Ascunde" : "Feedback"}
            </span>
          ) : null}
          <span className="text-base font-semibold text-foreground">{formatScore(item.score)}</span>
        </span>
      </span>
      <span className="mt-2 block h-2 overflow-hidden rounded-full bg-surface-muted">
        <span className={`block h-full rounded-full ${tone}`} style={{ width: `${width}%` }} />
      </span>
    </>
  );

  return (
    <div>
      {canExpand ? (
        <button
          type="button"
          className="tap-soft block w-full rounded-xl p-2 text-left transition hover:bg-burgundy/5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-burgundy"
          aria-expanded={expanded}
          aria-controls={feedbackId}
          onClick={() => setExpanded((current) => !current)}
        >
          {content}
        </button>
      ) : (
        <div className="p-2">{content}</div>
      )}
      {canExpand && expanded ? (
        <p id={feedbackId} className="mt-1 rounded-xl bg-surface-muted px-3 py-2 text-xs leading-5 text-foreground/68">
          {item.explanation}
        </p>
      ) : null}
    </div>
  );
}

type ResultKind = "drivers" | "lencioni" | "icare" | "other";

type ScoreItem = {
  id: string;
  label: string;
  score: number;
  interpretation?: string | null;
  explanation?: string;
};

function resultKind(questionnaireKey: string): ResultKind {
  if (questionnaireKey === "distress_drivers" || questionnaireKey === "distress_drivers_en") return "drivers";
  if (questionnaireKey === "lencioni" || questionnaireKey === "lencioni_en") return "lencioni";
  if (questionnaireKey === "boss_360" || questionnaireKey === "boss_360_en" || questionnaireKey === "icare") return "icare";
  return "other";
}

function resultKindLabel(kind: ResultKind): string {
  if (kind === "drivers") return "Driveri de stres";
  if (kind === "lencioni") return "Lencioni";
  if (kind === "icare") return "iCARE 360";
  return "Chestionar";
}

function maxScoreForKind(kind: ResultKind): number {
  if (kind === "lencioni") return 10;
  return 100;
}

function scoreItemsForResult(result: ParticipantWorkspaceResult, kind: ResultKind): ScoreItem[] {
  const items: ScoreItem[] = [];
  for (const [id, value] of Object.entries(result.scores)) {
    if (kind === "icare" && !Object.prototype.hasOwnProperty.call(icareLabels, id)) continue;
    const score = extractScore(value);
    if (score === null) continue;
    items.push({
      id,
      label: labelForScore(id, kind),
      score,
      interpretation: extractInterpretation(value) ?? fallbackInterpretationForScore(kind, score),
      explanation: kind === "drivers" ? driverExplanations[id] : undefined,
    });
  }
  return items.sort((first, second) => second.score - first.score);
}

function averageScore(items: ScoreItem[]): number | null {
  if (items.length === 0) return null;
  const total = items.reduce((sum, item) => sum + item.score, 0);
  return Math.round((total / items.length) * 10) / 10;
}

function labelForScore(id: string, kind: ResultKind): string {
  if (kind === "drivers") return driverLabels[id] ?? prettifyScoreKey(id);
  if (kind === "lencioni") return lencioniLabels[id] ?? prettifyScoreKey(id);
  if (kind === "icare") return icareLabels[id] ?? prettifyScoreKey(id);
  return prettifyScoreKey(id);
}

function extractScore(value: unknown): number | null {
  const raw = typeof value === "object" && value !== null && "score" in value ? (value as { score?: unknown }).score : value;
  if (typeof raw === "number" && Number.isFinite(raw)) return raw;
  if (typeof raw === "string" && raw.trim() !== "") {
    const parsed = Number(raw);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function fallbackInterpretationForScore(kind: ResultKind, score: number): string | null {
  if (kind === "lencioni") {
    if (score >= 8 && score <= 9) return "Disfuncția probabil nu este o problemă.";
    if (score >= 6 && score < 8) return "Disfuncția poate fi o problemă.";
    if (score >= 3 && score < 6) return "Disfuncția trebuie probabil abordată.";
    if (score < 3) return "Scor sub intervalul de referință Lencioni.";
    return "Scor peste intervalul de referință Lencioni.";
  }

  if (kind === "icare") {
    if (score >= 75) return "Comportamentul este observat frecvent sau constant pe scala iCARE.";
    if (score >= 50) return "Comportamentul este observat uneori; zona merită clarificată în feedback.";
    return "Comportamentul apare rar în evaluare; poate fi o zonă de dezvoltare.";
  }

  return null;
}

function extractInterpretation(value: unknown): string | null {
  if (typeof value !== "object" || value === null || !("interpretation" in value)) return null;
  const interpretation = (value as { interpretation?: unknown }).interpretation;
  return typeof interpretation === "string" && interpretation.trim() ? interpretation : null;
}

function prettifyScoreKey(value: string): string {
  return value
    .replace(/^icare_\d+_/, "")
    .replace(/_/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toLocaleUpperCase("ro-RO") + part.slice(1))
    .join(" ");
}

function formatScore(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function CheckIcon() {
  return (
    <svg className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2.4" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="m5 13 4 4L19 7" />
    </svg>
  );
}
