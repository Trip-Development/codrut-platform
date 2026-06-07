"use client";

import Link from "next/link";
import type { FormEvent } from "react";
import { useEffect, useMemo, useState } from "react";

import type { SessionState } from "@/api/auth";
import type { InviteTask } from "@/api/invites";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";

type ParticipantClientWorkspaceProps = {
  session: SessionState;
  summaryData: {
    projectName: string;
    participantEmail: string;
    deadlineLabel: string;
    tasks: InviteTask[];
  };
};

const destructiveButtonClass =
  "tap-soft rounded-lg border border-[#890505]/35 bg-transparent px-3 py-1.5 text-xs font-bold text-[#890505] shadow-none transition hover:bg-[#890505]/10 dark:border-[#e35f5f]/45 dark:text-[#e35f5f] dark:hover:bg-[#890505]/22";

type CompetencyKey = "listening" | "feedback" | "assertiveness" | "clarity" | "adaptability";

type Competency = {
  key: CompetencyKey;
  label: string;
  shortLabel: string;
  score: number;
  detail: string;
};

const defaultScores: Record<CompetencyKey, number> = {
  listening: 75,
  feedback: 80,
  assertiveness: 70,
  clarity: 60,
  adaptability: 65,
};

const defaultReflections = [
  "Pentru următoarea discuție vreau să ascult mai mult înainte să propun o soluție.",
  "Când primesc feedback dificil, îmi este util să cer un exemplu concret și să notez următorul pas.",
];

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
  const firstName = session.user.name?.split(" ")[0] || "bun venit";
  const [scores, setScores] = useState(defaultScores);
  const [reflections, setReflections] = useState(defaultReflections);
  const [newReflectionText, setNewReflectionText] = useState("");
  const [isAddingReflection, setIsAddingReflection] = useState(false);
  const [hoveredComp, setHoveredComp] = useState<CompetencyKey | null>(null);
  const [radarScale, setRadarScale] = useState(0.1);

  useEffect(() => {
    const timer = window.setTimeout(() => setRadarScale(1), 120);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    const storedScores = window.localStorage.getItem("codrut_participant_scores");
    const storedReflections = window.localStorage.getItem("codrut_participant_reflections");

    if (storedScores) {
      try {
        setScores({ ...defaultScores, ...JSON.parse(storedScores) });
      } catch {}
    }

    if (storedReflections) {
      try {
        setReflections(JSON.parse(storedReflections));
      } catch {}
    }
  }, []);

  const pendingTasks = summaryData.tasks.filter((task) => task.status !== "completed");
  const completedTasksCount = summaryData.tasks.length - pendingTasks.length;
  const tasksProgressPct =
    summaryData.tasks.length > 0 ? Math.round((completedTasksCount / summaryData.tasks.length) * 100) : 100;
  const nextTask = pendingTasks[0];

  const competencies = useMemo<Competency[]>(
    () => [
      {
        key: "listening",
        label: "Ascultare activă",
        shortLabel: "Ascultare",
        score: scores.listening,
        detail: "Rămâi prezent și verifici înțelegerea înainte de răspuns.",
      },
      {
        key: "feedback",
        label: "Feedback constructiv",
        shortLabel: "Feedback",
        score: scores.feedback,
        detail: "Formulezi observații specifice, cu impact și pas următor.",
      },
      {
        key: "assertiveness",
        label: "Comunicare asertivă",
        shortLabel: "Asertivitate",
        score: scores.assertiveness,
        detail: "Spui clar ce ai nevoie, păstrând respectul în conversație.",
      },
      {
        key: "clarity",
        label: "Claritate",
        shortLabel: "Claritate",
        score: scores.clarity,
        detail: "Structurezi mesajul astfel încât ceilalți să știe ce urmează.",
      },
      {
        key: "adaptability",
        label: "Adaptare PCM",
        shortLabel: "Adaptare",
        score: scores.adaptability,
        detail: "Ajustezi tonul și canalul la profilul interlocutorului.",
      },
    ],
    [scores],
  );

  const averageScore = Math.round(
    competencies.reduce((total, competency) => total + competency.score, 0) / competencies.length,
  );

  const handleAddReflection = (event: FormEvent) => {
    event.preventDefault();
    const nextReflection = newReflectionText.trim();
    if (!nextReflection) return;

    const updated = [nextReflection, ...reflections];
    setReflections(updated);
    window.localStorage.setItem("codrut_participant_reflections", JSON.stringify(updated));
    setNewReflectionText("");
    setIsAddingReflection(false);
  };

  const handleRemoveReflection = (index: number) => {
    const updated = reflections.filter((_, reflectionIndex) => reflectionIndex !== index);
    setReflections(updated);
    window.localStorage.setItem("codrut_participant_reflections", JSON.stringify(updated));
  };

  return (
    <AppShell
      audience="participant"
      eyebrow={summaryData.projectName}
      title={`Bună, ${firstName}`}
      description="Ai aici pașii de completat, progresul proiectului și notițele tale. Începe cu sarcinile active, apoi revino oricând pentru următorul pas."
      navItems={participantNavItems}
      activeHref="/participant"
      userLabel={firstName}
    >
      <div className="space-y-7">
        <section className="animate-fade-up rounded-[1.75rem] border border-burgundy/16 bg-surface/92 p-5 shadow-[0_22px_60px_rgba(137,5,5,0.10)] backdrop-blur md:p-7">
          <div className="grid gap-6 xl:grid-cols-[1.45fr_0.9fr]">
            <div className="min-w-0">
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.18em] text-burgundy/82">
                    Prioritatea ta acum
                  </p>
                  <h2 className="mt-2 font-display text-3xl font-semibold tracking-tight text-foreground md:text-4xl">
                    Sarcini active în așteptare
                  </h2>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/62">
                    Completează pașii de mai jos când ai un moment liniștit. Fiecare răspuns este salvat pentru proiectul curent.
                  </p>
                </div>
                <div className="w-fit rounded-2xl bg-burgundy px-4 py-3 text-white shadow-brand">
                  <span className="block text-2xl font-semibold leading-none">{pendingTasks.length}</span>
                  <span className="mt-1 block text-xs font-semibold text-white/78">
                    {pendingTasks.length === 1 ? "sarcină activă" : "sarcini active"}
                  </span>
                </div>
              </div>

              {pendingTasks.length > 0 ? (
                <div className="mt-6 grid gap-3">
                  {pendingTasks.map((task, index) => (
                    <TaskCard key={task.id} task={task} index={index} />
                  ))}
                </div>
              ) : (
                <div className="mt-6 rounded-2xl border border-success/24 bg-success/10 p-5">
                  <h3 className="text-base font-semibold text-foreground">Toate sarcinile sunt finalizate</h3>
                  <p className="mt-1 text-sm leading-6 text-foreground/62">
                    Ești la zi. Când apare un pas nou, îl vei vedea aici primul.
                  </p>
                </div>
              )}
            </div>

            <aside className="rounded-2xl border border-[var(--border)] bg-surface-muted/55 p-5">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.16em] text-foreground/48">Următorul pas</p>
                  <h3 className="mt-2 text-xl font-semibold text-foreground">
                    {nextTask ? nextTask.title : "Pauză până la următoarea invitație"}
                  </h3>
                </div>
                <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-success/20 text-success-ink">
                  <CheckIcon />
                </span>
              </div>
              <p className="mt-4 text-sm leading-6 text-foreground/62">
                {nextTask
                  ? "Deschide task-ul, completează răspunsurile și revino aici pentru restul pașilor."
                  : "Nu trebuie să faci nimic acum. Progresul tău rămâne salvat."}
              </p>
              <div className="mt-6 rounded-2xl bg-surface p-4 shadow-sm">
                <div className="mb-2 flex items-center justify-between text-xs font-bold text-foreground/55">
                  <span>Completare proiect</span>
                  <span>{tasksProgressPct}%</span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-burgundy/10">
                  <div className="h-full rounded-full bg-burgundy transition-all duration-700" style={{ width: `${tasksProgressPct}%` }} />
                </div>
              </div>
              <div className="mt-4 grid gap-3 text-sm">
                <ContextRow label="Email" value={summaryData.participantEmail} />
                <ContextRow label="Termen" value={summaryData.deadlineLabel} />
              </div>
            </aside>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          <StatusCard label="Progres" value={`${tasksProgressPct}%`} detail={`${completedTasksCount}/${summaryData.tasks.length} sarcini finalizate`} tone="burgundy" />
          <StatusCard label="Proiect" value={summaryData.projectName} detail="Programul activ pentru care ai primit invitația." tone="gray" />
          <StatusCard label="Confidențial" value="Da" detail="Răspunsurile individuale nu sunt afișate managerilor evaluați." tone="green" />
        </section>

        <div className="grid gap-7 xl:grid-cols-[1.12fr_0.88fr]">
          <section className="rounded-[1.75rem] border border-[var(--border)] bg-surface/90 p-5 shadow-sm backdrop-blur md:p-6">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-xs font-bold uppercase tracking-[0.16em] text-burgundy/75">Profil de progres</p>
                <h2 className="mt-2 font-display text-2xl font-semibold text-foreground">Harta competențelor</h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-foreground/62">
                  O privire rapidă asupra ariilor urmărite în program. Scorurile se actualizează pe măsură ce completezi sarcinile.
                </p>
              </div>
              <div className="rounded-2xl bg-surface-muted px-4 py-3 text-right">
                <span className="block text-xs font-bold uppercase tracking-[0.12em] text-foreground/45">Medie</span>
                <span className="mt-1 block text-2xl font-semibold text-burgundy">{averageScore}%</span>
              </div>
            </div>

            <div className="mt-7 grid gap-8 lg:grid-cols-[0.88fr_1.12fr] lg:items-center">
              <RadarChart
                competencies={competencies}
                hoveredComp={hoveredComp}
                radarScale={radarScale}
                onHover={setHoveredComp}
              />
              <CompetencyList competencies={competencies} hoveredComp={hoveredComp} onHover={setHoveredComp} />
            </div>
          </section>

          <div className="space-y-7">
            <RhythmPanel />

            <section className="rounded-[1.75rem] border border-[var(--border)] bg-surface/90 p-5 shadow-sm backdrop-blur md:p-6">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[0.16em] text-burgundy/75">Jurnal</p>
                  <h2 className="mt-2 font-display text-2xl font-semibold text-foreground">Reflecții</h2>
                </div>
                <button
                  onClick={() => setIsAddingReflection(!isAddingReflection)}
                  className="tap-soft rounded-2xl border border-burgundy/20 bg-burgundy/8 px-4 py-2.5 text-sm font-bold text-burgundy hover:bg-burgundy hover:text-white"
                >
                  {isAddingReflection ? "Închide" : "Adaugă"}
                </button>
              </div>

              {isAddingReflection && (
                <form onSubmit={handleAddReflection} className="mt-5 space-y-3 rounded-2xl border border-[var(--border)] bg-surface-muted/45 p-4 animate-fade-up">
                  <textarea
                    placeholder="Notează o idee utilă din sesiune..."
                    value={newReflectionText}
                    onChange={(event) => setNewReflectionText(event.target.value)}
                    rows={3}
                    className="w-full resize-none rounded-2xl border border-[var(--border)] bg-surface px-4 py-3 text-sm leading-6 text-foreground outline-none transition focus:border-burgundy/45"
                  />
                  <div className="flex justify-end gap-2">
                    <button
                      type="button"
                      onClick={() => setIsAddingReflection(false)}
                      className="rounded-xl px-3 py-2 text-xs font-bold text-foreground/58 hover:bg-surface"
                    >
                      Anulează
                    </button>
                    <button type="submit" className="rounded-xl bg-burgundy px-3 py-2 text-xs font-bold text-white">
                      Salvează
                    </button>
                  </div>
                </form>
              )}

              <div className="mt-5 space-y-3">
                {reflections.slice(0, 2).map((reflection, index) => (
                  <article key={index} className="group/ref rounded-2xl bg-surface-muted/55 p-4">
                    <p className="text-sm leading-6 text-foreground/72">„{reflection}”</p>
                    <div className="mt-3 flex items-center justify-between gap-3">
                      <span className="text-xs font-semibold text-foreground/42">
                        {new Date().toLocaleDateString("ro-RO", { month: "long", year: "numeric" })}
                      </span>
                      <button
                        onClick={() => handleRemoveReflection(index)}
                        className={`${destructiveButtonClass} opacity-0 group-hover/ref:opacity-100`}
                      >
                        Șterge reflecția
                      </button>
                    </div>
                  </article>
                ))}
                {reflections.length === 0 && (
                  <p className="rounded-2xl bg-surface-muted/55 p-4 text-sm leading-6 text-foreground/58">
                    Nu ai notițe încă. Adaugă o idee după ce finalizezi prima sarcină.
                  </p>
                )}
              </div>
            </section>
          </div>
        </div>
      </div>
    </AppShell>
  );
}

function TaskCard({ task, index }: { task: InviteTask; index: number }) {
  const copy = statusCopy[task.status];

  return (
    <article
      className="group/task animate-fade-up rounded-2xl border border-burgundy/12 bg-gradient-to-br from-white to-[rgba(137,5,5,0.035)] p-4 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:border-burgundy/24 hover:shadow-[0_16px_36px_rgba(137,5,5,0.11)] dark:from-[rgba(255,255,255,0.035)] dark:to-[rgba(227,95,95,0.09)]"
      style={{ animationDelay: `${index * 70}ms` }}
    >
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
        <Link
          href={task.href}
          className="tap-soft inline-flex items-center justify-center gap-2 rounded-2xl bg-burgundy px-5 py-3 text-sm font-bold text-white shadow-md shadow-burgundy/15 hover:bg-burgundy-dark"
        >
          Continuă
          <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2.4" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" d="M5 12h14m-6-6 6 6-6 6" />
          </svg>
        </Link>
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
    <div className="animate-fade-up rounded-2xl border border-[var(--border)] bg-surface/86 p-5 shadow-sm backdrop-blur">
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
    <div className="rounded-2xl bg-surface px-4 py-3">
      <span className="block text-xs font-semibold text-foreground/45">{label}</span>
      <span className="mt-1 block truncate font-semibold text-foreground">{value}</span>
    </div>
  );
}

function RhythmPanel() {
  const activeDays = 3;

  return (
    <section className="rounded-[1.75rem] border border-[var(--border)] bg-surface/90 p-5 shadow-sm backdrop-blur md:p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-burgundy/75">Ritm de lucru</p>
          <h2 className="mt-2 font-display text-2xl font-semibold text-foreground">Mic progres, constant</h2>
        </div>
        <div className="rounded-2xl bg-success/18 px-4 py-3 text-success-ink">
          <span className="block text-2xl font-semibold leading-none">{activeDays}</span>
          <span className="mt-1 block text-xs font-bold">zile active</span>
        </div>
      </div>
      <div className="mt-6 grid grid-cols-7 gap-1.5">
        {[...Array(7)].map((_, index) => (
          <div
            key={index}
            className={[
              "h-10 rounded-xl border transition duration-300",
              index < activeDays ? "border-success/30 bg-success/35 shadow-sm" : "border-[var(--border)] bg-surface-muted/55",
            ].join(" ")}
            aria-label={index < activeDays ? "Zi activă" : "Zi necompletată"}
          />
        ))}
      </div>
      <p className="mt-4 text-sm leading-6 text-foreground/58">
        Nu contează să faci totul dintr-o dată. Un task completat clar este mai valoros decât o sesiune grăbită.
      </p>
    </section>
  );
}

function CompetencyList({
  competencies,
  hoveredComp,
  onHover,
}: {
  competencies: Competency[];
  hoveredComp: CompetencyKey | null;
  onHover: (key: CompetencyKey | null) => void;
}) {
  return (
    <div className="space-y-3">
      {competencies.map((competency) => {
        const color = getScoreColor(competency.score);
        const isHovered = hoveredComp === competency.key;

        return (
          <button
            key={competency.key}
            type="button"
            onMouseEnter={() => onHover(competency.key)}
            onMouseLeave={() => onHover(null)}
            className={[
              "w-full rounded-2xl border bg-surface-muted/58 p-3 text-left transition duration-200",
              isHovered ? "border-burgundy/22 bg-surface shadow-sm" : "border-transparent hover:border-burgundy/18 hover:bg-surface",
            ].join(" ")}
          >
            <div className="flex items-center justify-between gap-4">
              <span className="text-sm font-semibold text-foreground">{competency.label}</span>
              <span className="text-sm font-bold" style={{ color }}>
                {competency.score}%
              </span>
            </div>
            <p className="mt-1 text-xs leading-5 text-foreground/52">{competency.detail}</p>
            <div className="mt-2 h-2 overflow-hidden rounded-full bg-foreground/8">
              <div className="h-full rounded-full transition-all duration-700" style={{ width: `${competency.score}%`, backgroundColor: color }} />
            </div>
          </button>
        );
      })}
    </div>
  );
}

function RadarChart({
  competencies,
  hoveredComp,
  radarScale,
  onHover,
}: {
  competencies: Competency[];
  hoveredComp: CompetencyKey | null;
  radarScale: number;
  onHover: (key: CompetencyKey | null) => void;
}) {
  const cx = 200;
  const cy = 200;
  const radius = 134;
  const pointString = competencies
    .map((competency, index) => {
      const angle = (index * 2 * Math.PI) / competencies.length - Math.PI / 2;
      const value = (competency.score * radarScale) / 100;
      const x = cx + radius * value * Math.cos(angle);
      const y = cy + radius * value * Math.sin(angle);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <div className="mx-auto flex w-full max-w-[300px] items-center justify-center">
      <svg width="100%" height="100%" viewBox="0 0 400 400" preserveAspectRatio="xMidYMid meet" className="overflow-visible select-none">
        <defs>
          <radialGradient id="dashboard-radar-glow" cx="50%" cy="50%" r="50%">
            <stop offset="0%" stopColor="var(--burgundy)" stopOpacity="0.03" />
            <stop offset="100%" stopColor="var(--burgundy)" stopOpacity="0.18" />
          </radialGradient>
        </defs>
        {[1, 0.8, 0.6, 0.4, 0.2].map((scale) => {
          const points = competencies
            .map((_, index) => {
              const angle = (index * 2 * Math.PI) / competencies.length - Math.PI / 2;
              const x = cx + radius * scale * Math.cos(angle);
              const y = cy + radius * scale * Math.sin(angle);
              return `${x},${y}`;
            })
            .join(" ");
          return <polygon key={scale} points={points} fill="none" stroke="currentColor" strokeWidth="1.1" className="text-foreground/12" />;
        })}
        {competencies.map((_, index) => {
          const angle = (index * 2 * Math.PI) / competencies.length - Math.PI / 2;
          return (
            <line
              key={index}
              x1={cx}
              y1={cy}
              x2={cx + radius * Math.cos(angle)}
              y2={cy + radius * Math.sin(angle)}
              stroke="currentColor"
              strokeWidth="1"
              className="text-foreground/10"
            />
          );
        })}
        <polygon
          points={pointString}
          fill="url(#dashboard-radar-glow)"
          stroke="var(--burgundy)"
          strokeWidth="3"
          className="transition-all duration-700 ease-out"
        />
        {competencies.map((competency, index) => {
          const angle = (index * 2 * Math.PI) / competencies.length - Math.PI / 2;
          const value = competency.score / 100;
          const x = cx + radius * value * radarScale * Math.cos(angle);
          const y = cy + radius * value * radarScale * Math.sin(angle);

          return (
            <circle
              key={competency.key}
              cx={x}
              cy={y}
              r={hoveredComp === competency.key ? 8 : 5}
              fill={getScoreColor(competency.score)}
              stroke="var(--surface)"
              strokeWidth="2.5"
              className="cursor-pointer transition-all duration-200"
              onMouseEnter={() => onHover(competency.key)}
              onMouseLeave={() => onHover(null)}
            />
          );
        })}
        {competencies.map((competency, index) => {
          const angle = (index * 2 * Math.PI) / competencies.length - Math.PI / 2;
          const x = cx + (radius + 24) * Math.cos(angle);
          const y = cy + (radius + 24) * Math.sin(angle);
          const anchor = index === 0 ? "middle" : index < 3 ? "start" : "end";

          return (
            <text
              key={competency.key}
              x={x}
              y={y}
              textAnchor={anchor}
              className="fill-current text-[12px] font-semibold text-foreground/62"
            >
              {competency.shortLabel}
            </text>
          );
        })}
      </svg>
    </div>
  );
}

function CheckIcon() {
  return (
    <svg className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2.2" viewBox="0 0 24 24" aria-hidden="true">
      <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.5 11.5 15 16 9m5 3a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
    </svg>
  );
}

function getScoreColor(score: number) {
  if (score >= 75) return "var(--bloom-green)";
  if (score >= 55) return "var(--bloom-blue)";
  if (score >= 35) return "var(--bloom-gold)";
  return "var(--bloom-red)";
}
