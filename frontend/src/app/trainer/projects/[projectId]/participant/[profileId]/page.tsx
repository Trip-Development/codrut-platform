import Link from "next/link";
import { ArrowLeftIcon, BookOpenIcon } from "lucide-react";

import { getPracticePerson } from "@/api/practice";
import { getServerApiRequestOptions } from "@/api/server-request";
import { Card } from "@/components/ui/card";
import { TrainerNotesPanel } from "./TrainerNotesPanel";

/**
 * Pagina omului — al doilea ecran al camerei de training.
 *
 * Portat din `app/admin/projects/[projectId]/participant/[userId]/page.tsx`
 * (462 rd.), citit întreg înainte. Două secțiuni mari, cu înțelesuri diferite,
 * exact ca în vechi: ce ȘTIE omul (teorie, Test IN ↔ Test OUT) și ce FACE
 * (practică aplicată, evidence acumulat din sesiuni).
 *
 * Butonul „Vezi raport" duce la ecranul 3, care nu e construit încă — de aceea
 * NU e legătură, ci un buton dezactivat care spune de ce. „Nicio legătură nu
 * duce în gol."
 */
export default async function ProjectParticipantPage({
  params,
}: {
  params: Promise<{ projectId: string; profileId: string }>;
}) {
  const [{ projectId, profileId }, requestOptions] = await Promise.all([
    params,
    getServerApiRequestOptions(),
  ]);
  const p = await getPracticePerson(projectId, profileId, requestOptions);
  const basePath = `/trainer/projects/${projectId}`;

  if (!p) {
    return (
      <Card className="p-6">
        <h2 className="text-base font-semibold text-foreground">
          Nu am putut încărca participantul
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Ori nu e în proiectul ăsta, ori datele nu au venit de la server.
        </p>
        <Link href={basePath} className="mt-4 inline-block text-sm underline underline-offset-2">
          Înapoi la proiect
        </Link>
      </Card>
    );
  }

  const areTeorie = p.theory.some((t) => t.testIn !== null || t.testOut !== null);

  return (
    <div className="flex flex-col gap-5">
      {/* ── antet ── */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <Link
            href={basePath}
            className="mt-1 text-muted-foreground hover:text-foreground"
            aria-label="Înapoi la proiect"
          >
            <ArrowLeftIcon className="size-5" />
          </Link>
          <div>
            <h2 className="text-lg font-semibold text-foreground">{p.fullName}</h2>
            <p className="text-sm text-muted-foreground">
              {p.email} · {p.projectName}
            </p>
          </div>
        </div>
        <button
          type="button"
          disabled
          title="Raportul vine în pasul următor al plicului 30."
          className="rounded-md border px-3 py-2 text-sm font-medium text-muted-foreground opacity-60"
        >
          Vezi raport
        </button>
      </div>

      {/* ── cele patru cifre ── */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Cifra eticheta="Test IN" nota="teorie" valoare={p.testInAverage} />
        <Cifra eticheta="Progres acumulat" valoare={p.progressAverage} accent />
        <Cifra eticheta="Test OUT" nota="teorie" valoare={p.testOutAverage} />
        <Cifra eticheta="Sesiuni practice" valoare={p.sessionsCount} brut />
      </div>

      {/* ── Cunoștințe teoretice ── */}
      <Card className="p-5">
        <h3 className="text-base font-semibold text-foreground">
          Cunoștințe teoretice{" "}
          <span className="text-xs font-normal text-muted-foreground">
            — Test IN ↔ Test OUT
          </span>
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Măsoară ce <em>știe</em> participantul în teorie. Test IN = baseline la start,
          Test OUT = la final. Δ pozitiv = a învățat lucruri noi.
        </p>
        {!areTeorie ? (
          <p className="mt-4 text-sm text-muted-foreground">
            Încă niciun test dat. Testul de intrare e primul lucru după ce își face contul.
          </p>
        ) : (
          <ul className="mt-4 flex flex-col gap-2">
            {p.theory.map((t) => (
              <li key={t.name} className="flex items-center gap-3 text-sm">
                <span className="flex-1 text-foreground">{t.name}</span>
                <span className="w-20 text-right text-xs text-muted-foreground">
                  IN: <strong className="text-foreground">{t.testIn !== null ? `${t.testIn}%` : "—"}</strong>
                </span>
                <span className="w-24 text-right text-xs text-muted-foreground">
                  OUT: <strong style={{ color: t.testOut !== null ? "#15803d" : undefined }}>
                    {t.testOut !== null ? `${t.testOut}%` : "—"}
                  </strong>
                </span>
                <span
                  className="w-14 text-right text-xs font-bold"
                  style={{ color: t.delta === null ? undefined : t.delta >= 0 ? "#639922" : "#E24B4A" }}
                >
                  {t.delta === null ? "—" : t.delta >= 0 ? `+${t.delta}` : `${t.delta}`}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* ── Practică aplicată ── */}
      <Card className="p-5">
        <h3 className="text-base font-semibold text-foreground">
          Practică aplicată{" "}
          <span className="text-xs font-normal text-muted-foreground">
            — evidence acumulat din sesiuni cu Codruț
          </span>
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Măsoară comportamentul aplicat, nu cunoștința teoretică. Crește treptat — pentru
          integrare reală e nevoie de practică susținută.
          {p.durationDays !== null ? <> Plafon proiect: <strong>{p.durationDays} zile</strong>.</> : null}
        </p>
        {p.evidence.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">
            Nicio competență definită încă pentru acest proiect.
          </p>
        ) : (
          <ul className="mt-5 flex flex-col gap-5">
            {p.evidence.map((e) => (
              <li key={e.name}>
                <div className="mb-1.5 flex items-end justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold text-foreground">{e.name}</span>
                    <span className="text-[11px] text-muted-foreground">{e.levelDescription}</span>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <span className="text-[11px] text-muted-foreground">
                      {e.sessionsCount} {e.sessionsCount === 1 ? "sesiune" : "sesiuni"}
                    </span>
                    <span
                      className="inline-block rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider text-white"
                      style={{ background: e.color }}
                    >
                      {e.level}
                    </span>
                    <span className="text-lg font-bold" style={{ color: e.color }}>
                      {Math.round(e.averageScore)}%
                    </span>
                  </div>
                </div>
                <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${Math.round(e.averageScore)}%`, backgroundColor: e.color }}
                  />
                </div>
                {e.whyNotHigher && e.scoresCount > 0 ? (
                  <p className="mt-2 text-[11px] italic text-muted-foreground">{e.whyNotHigher}</p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
        {/* legenda nivelurilor — culorile sunt limbaj, nu decor */}
        <div className="mt-6 flex flex-wrap gap-4 border-t pt-5 text-[11px] text-muted-foreground">
          <Legenda culoare="#E24B4A" text="Conștientizare (0–25%)" />
          <Legenda culoare="#BA7517" text="Aplicare (25–50%)" />
          <Legenda culoare="#1A4A7A" text="Consolidare (50–75%)" />
          <Legenda culoare="#639922" text="Integrare (75–100%)" />
        </div>
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        {/* ── Evoluție scor mediu ── */}
        <Card className="p-5">
          <h3 className="text-base font-semibold text-foreground">Evoluție scor mediu</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Media per sesiune de practică (fără teste, fără quiz).
          </p>
          {p.weeklyAverage.length === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">Încă nicio sesiune de practică.</p>
          ) : (
            <ul className="mt-4 flex flex-col gap-3">
              {p.weeklyAverage.map((w) => (
                <li key={w.weekStart}>
                  <div className="flex justify-between text-xs">
                    <span className="text-muted-foreground">
                      Săptămâna din {new Date(w.weekStart).toLocaleDateString("ro-RO")}
                    </span>
                    <span className="font-medium text-foreground">{w.average}%</span>
                  </div>
                  <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div className="h-full rounded-full bg-burgundy" style={{ width: `${w.average}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* ── Top progres pe practică ── */}
        <Card className="p-5">
          <h3 className="text-base font-semibold text-foreground">Top progres pe practică</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Competențele ordonate după evidence acumulat din sesiuni.
          </p>
          {p.topProgress.length === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">Nicio competență.</p>
          ) : (
            <ol className="mt-4 flex flex-col gap-2">
              {p.topProgress.map((e, i) => (
                <li key={e.name} className="flex items-center gap-3 text-sm">
                  <span className="w-5 text-center text-xs font-bold text-muted-foreground">{i + 1}</span>
                  <span className="flex-1 text-foreground">{e.name}</span>
                  <span className="font-bold" style={{ color: e.color }}>
                    {Math.round(e.averageScore)}%
                  </span>
                </li>
              ))}
            </ol>
          )}
        </Card>
      </div>

      {/* ── Ce nu a fost înțeles bine ── */}
      <Card className="p-5">
        <div className="flex items-center gap-2">
          <BookOpenIcon className="size-4 text-burgundy" aria-hidden />
          <h3 className="text-base font-semibold text-foreground">Ce nu a fost înțeles bine</h3>
        </div>
        <p className="mt-1 text-xs text-muted-foreground">
          Competențele cu cel mai slab scor la întrebările de cunoștințe, ordonate de la
          critic la bun.
        </p>
        {p.quizWeakSpots.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">Fără sesiuni de quiz înregistrate.</p>
        ) : (
          <ul className="mt-4 flex flex-col gap-3">
            {p.quizWeakSpots.map((q) => (
              <li key={q.name} className="flex justify-between text-sm">
                <span className="text-foreground">{q.name}</span>
                <span className="font-bold">{q.average}%</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* ── recomandările pentru trainer (notele [TRAINER]) ── */}
      <Card className="p-5">
        <h3 className="text-base font-semibold text-foreground">
          Recomandări pentru tine, din sesiuni
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Scrise de evaluator pentru competențele sub 70. Participantul nu le vede.
        </p>
        {p.trainerRecommendations.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">Nicio recomandare încă.</p>
        ) : (
          <ul className="mt-4 flex flex-col gap-3">
            {p.trainerRecommendations.map((m) => (
              <li key={m.id} className="border-t pt-3 first:border-t-0 first:pt-0">
                <p className="text-sm text-foreground">{m.summary.replace(/^\[TRAINER\]\s*/, "")}</p>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        {/* ── momentele de intuiție ── */}
        <Card className="p-5">
          <h3 className="text-base font-semibold text-foreground">Momente de intuiție</h3>
          {p.insightMoments.length === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">Niciun insight înregistrat încă.</p>
          ) : (
            <ul className="mt-4 flex flex-col gap-3">
              {p.insightMoments.map((m) => (
                <li key={m.id} className="border-t pt-3 first:border-t-0 first:pt-0">
                  <p className="text-sm text-foreground">{m.summary}</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {new Date(m.createdAt).toLocaleDateString("ro-RO")}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Card>

        {/* ── mostrele de conversație ── */}
        <Card className="p-5">
          <h3 className="text-base font-semibold text-foreground">Mostre din conversații</h3>
          {p.sessionSamples.length === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">Nicio interacțiune analizată.</p>
          ) : (
            <ul className="mt-4 flex flex-col gap-4">
              {p.sessionSamples.map((s) => (
                <li key={s.id} className="border-t pt-3 first:border-t-0 first:pt-0">
                  <p className="text-xs font-semibold text-muted-foreground">Așa ai spus</p>
                  <p className="text-sm italic text-foreground">{s.realWeak ?? s.inventedWeak ?? "—"}</p>
                  <p className="mt-2 text-xs font-semibold text-muted-foreground">Așa ar fi sunat</p>
                  <p className="text-sm text-foreground">{s.realImproved ?? s.inventedImproved ?? "—"}</p>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <TrainerNotesPanel
        projectId={projectId}
        profileId={profileId}
        initialNotes={p.trainerNotes}
        canWrite={p.hasAccount}
      />
    </div>
  );
}

function Cifra({
  eticheta,
  valoare,
  nota,
  accent,
  brut,
}: {
  eticheta: string;
  valoare: number | null;
  nota?: string;
  accent?: boolean;
  brut?: boolean;
}) {
  return (
    <Card className="p-4">
      <p className="text-xs font-medium text-muted-foreground">
        {eticheta}
        {nota ? <span className="ml-1 text-muted-foreground/60">· {nota}</span> : null}
      </p>
      <p
        className="mt-1 text-3xl font-bold"
        style={{ color: accent ? "#9B0021" : undefined }}
      >
        {valoare === null ? "—" : brut ? valoare : `${valoare}%`}
      </p>
    </Card>
  );
}

function Legenda({ culoare, text }: { culoare: string; text: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="size-2.5 rounded-full" style={{ backgroundColor: culoare }} />
      {text}
    </span>
  );
}
