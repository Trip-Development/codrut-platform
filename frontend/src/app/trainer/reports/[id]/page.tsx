import Link from "next/link";

import { getTrainerSession } from "@/api/auth";
import { getScoringResult, getTrainerReports, type ScoringResultRecord } from "@/api/trainer";
import { AppShell } from "@/components/shell/app-shell";
import { trainerNavItems } from "@/components/shell/nav";

type TrainerReportDetailPageProps = {
  params: Promise<{ id: string }>;
};

type ScoreRow = {
  id: string;
  label: string;
  score: number | string;
  detail: string;
};

export default async function TrainerReportDetailPage({ params }: TrainerReportDetailPageProps) {
  const { id } = await params;
  const [trainer, reports, result] = await Promise.all([
    getTrainerSession(),
    getTrainerReports(),
    getScoringResult(id),
  ]);
  const report = reports.find((item) => item.assignmentId === id);
  const rows = result ? scoringRows(result) : [];

  return (
    <AppShell
      audience="trainer"
      eyebrow="Raport"
      title={report ? `Raport ${report.questionnaireKey.replaceAll("_", " ")}` : "Raport evaluare"}
      description="Breakdown calculat progresiv pe masura ce raspunsurile sunt trimise. Vizibilitatea catre manageri ramane separata de accesul trainerului."
      navItems={trainerNavItems}
      activeHref="/trainer/reports"
      userLabel={trainer.user.name}
      session={trainer}
    >
      <div className="mb-5">
        <Link href="/trainer/reports" className="text-sm font-bold text-burgundy hover:text-burgundy-700">
          Inapoi la rapoarte
        </Link>
      </div>

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_20rem]">
        <section className="overflow-hidden rounded-2xl border border-[var(--border)] bg-surface shadow-sm">
          <div className="border-b border-[var(--border)] bg-surface-muted/30 px-5 py-4">
            <h2 className="text-lg font-semibold text-foreground">Matrice scoruri</h2>
            <p className="mt-1 text-xs leading-5 text-foreground/55">
              Scorurile sunt calculate din definitia versionata a chestionarului si raspunsurile trimise.
            </p>
          </div>

          {rows.length === 0 ? (
            <div className="p-8 text-center">
              <p className="text-sm font-semibold text-foreground/60">
                Scorul nu este disponibil inca pentru aceasta asignare.
              </p>
            </div>
          ) : (
            <div className="divide-y divide-[var(--border)]">
              {rows.map((row) => (
                <article key={row.id} className="grid gap-3 px-5 py-4 md:grid-cols-[minmax(0,1fr)_9rem] md:items-center">
                  <div className="min-w-0">
                    <h3 className="font-semibold capitalize text-foreground">{row.label}</h3>
                    {row.detail ? (
                      <p className="mt-1 text-sm leading-6 text-foreground/58">{row.detail}</p>
                    ) : null}
                  </div>
                  <div className="rounded-2xl bg-surface-muted px-4 py-3 text-center">
                    <p className="text-xs font-bold uppercase tracking-[0.12em] text-foreground/45">Scor</p>
                    <p className="mt-1 font-display text-3xl font-semibold text-burgundy">{row.score}</p>
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>

        <aside className="space-y-4">
          <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-burgundy/75">Context</p>
            <div className="mt-4 space-y-3 text-sm">
              <ContextLine label="Participant" value={report?.participantName ?? "Necunoscut"} />
              <ContextLine label="Email" value={report?.participantEmail ?? "Indisponibil"} />
              <ContextLine label="Proiect" value={report?.projectName ?? "Indisponibil"} />
              <ContextLine label="Status" value={report?.primaryResult ? "calculat" : report?.status ?? "necunoscut"} />
              <ContextLine
                label="Rezultat principal"
                value={result?.primary_result?.replaceAll("_", " ") ?? "in asteptare"}
              />
            </div>
          </section>

          <section className="rounded-2xl border border-[var(--border)] bg-surface p-5 shadow-sm">
            <p className="text-xs font-bold uppercase tracking-[0.12em] text-burgundy/75">Vizibilitate</p>
            <p className="mt-3 text-sm leading-6 text-foreground/62">
              Trainerul poate inspecta rezultatul calculat. Persoanele evaluate nu primesc raspunsuri individuale;
              publicarea catre manageri trebuie controlata separat prin politica de raportare.
            </p>
          </section>
        </aside>
      </div>
    </AppShell>
  );
}

function scoringRows(result: ScoringResultRecord): ScoreRow[] {
  return Object.entries(result.scores).map(([id, value]) => {
    if (typeof value === "number" || typeof value === "string") {
      return {
        id,
        label: id.replaceAll("_", " "),
        score: value,
        detail: "",
      };
    }

    if (value && typeof value === "object") {
      const scoreObject = value as { score?: number | string; interpretation?: string };
      return {
        id,
        label: id.replaceAll("_", " "),
        score: scoreObject.score ?? "-",
        detail: scoreObject.interpretation ?? "",
      };
    }

    return {
      id,
      label: id.replaceAll("_", " "),
      score: "-",
      detail: "",
    };
  });
}

function ContextLine({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl bg-surface-muted px-3 py-2">
      <p className="text-xs font-semibold text-foreground/45">{label}</p>
      <p className="mt-1 break-words font-semibold text-foreground/75">{value}</p>
    </div>
  );
}
