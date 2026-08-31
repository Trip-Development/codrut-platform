import Link from "next/link";
import { CheckCircleIcon } from "lucide-react";

import { getProjectEvolution } from "@/api/practice";
import { getServerApiRequestOptions } from "@/api/server-request";
import { Card } from "@/components/ui/card";
import { ScaledBar } from "@/components/reports/native-charts";

/**
 * Fila „Evoluție competențe" — portată din aplicația veche
 * (`app/admin/projects/[projectId]/page.tsx` + `ProjectCharts.tsx`).
 *
 * Aceleași blocuri, în aceeași ordine, cu aceleași texte — dar în îmbrăcămintea
 * aplicației noi, ca fila să nu arate ca alt program decât cea de alături.
 *
 * Singurele culori copiate ca atare sunt cele patru ale nivelurilor: sunt limbaj,
 * nu decor. Vin din backend (`color`), din aceeași sursă ca restul aplicației.
 *
 * Coloanele Test IN / Test OUT rămân la locul lor, goale, cu rândul care spune
 * când se completează. Ele vin la plicul 30.
 */
export default async function ProjectEvolutionPage({
  params,
}: {
  params: Promise<{ projectId: string }>;
}) {
  const [{ projectId }, requestOptions] = await Promise.all([
    params,
    getServerApiRequestOptions(),
  ]);
  const data = await getProjectEvolution(projectId, requestOptions);

  // Fila nu are voie sa crape, orice ar fi. `getProjectEvolution` prinde si
  // exceptiile, nu doar raspunsurile ne-OK, si intoarce `null`; aici se arata un
  // ecran care EXPLICA, nu unul cu „Ref:".
  if (!data) {
    return (
      <Card className="p-6">
        <h2 className="text-base font-semibold text-foreground">
          Nu am putut încărca evoluția competențelor
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Datele nu au venit de la server. Proiectul și participanții sunt neatinși —
          e doar afișarea. Încearcă din nou peste un minut; dacă ține, spune-mi și mă uit
          în jurnalul serverului.
        </p>
        <Link
          href={`/trainer/projects/${projectId}/settings`}
          className="mt-4 inline-block text-sm font-medium underline underline-offset-2"
        >
          Mergi la Setările proiectului
        </Link>
      </Card>
    );
  }

  // Proiect care nu e de training: fila n-are ce arata, si se spune de ce.
  if (data.projectType !== "training") {
    return (
      <Card className="p-6">
        <h2 className="text-base font-semibold text-foreground">
          Proiectul acesta nu e de tip training
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          Evoluția competențelor se adună din sesiunile cu Cody, care există doar pe
          proiectele de training. Pentru {"„"}{data.projectName}{"”"} fila
          {" „Rezultate” "}e cea potrivită.
        </p>
        <Link
          href={`/trainer/projects/${projectId}/settings`}
          className="mt-4 inline-block text-sm font-medium underline underline-offset-2"
        >
          Mergi la Setările proiectului
        </Link>
      </Card>
    );
  }

  // Proiect de training fara nicio sesiune: tot gol, nu eroare.
  const faraSesiuni =
    data.weeklyAverage.length === 0 &&
    data.competencies.every((c) => c.scoresCount === 0);

  const maxWeekly = Math.max(100, ...data.weeklyAverage.map((w) => w.average));

  return (
    <div className="flex flex-col gap-5">
      {/* ── butonul „Activează Test OUT", sus, ca în aplicația veche ── */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Evoluție competențe</h2>
          <p className="text-sm text-muted-foreground">
            Nivelul de acum vine din sesiunile cu Cody.
          </p>
        </div>
        <button
          type="button"
          disabled
          title={data.testPendingNote}
          className="rounded-md border px-3 py-2 text-sm font-medium text-muted-foreground opacity-60"
        >
          {data.testOutEnabled ? "Test OUT: Activ" : "Activează Test OUT"}
        </button>
      </div>

      {faraSesiuni ? (
        <Card className="p-5">
          <p className="text-sm text-muted-foreground">
            Încă nicio sesiune de exersare pe proiectul ăsta. Cifrele apar aici după ce
            un participant termină prima conversație cu Cody. Coloanele Test IN și
            Test OUT {data.testPendingNote}.
          </p>
        </Card>
      ) : null}

      {/* ── contoarele ── */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Counter label="Participanți" value={String(data.participantsTotal)} />
        <Counter label="Activi în sesiuni" value={String(data.participantsActive)} />
        <Counter
          label="Test IN completat"
          value={data.testInCompleted === null ? "—" : String(data.testInCompleted)}
          note={data.testInCompleted === null ? data.testPendingNote : undefined}
        />
        <Counter
          label="Test OUT completat"
          value="—"
          note={data.testPendingNote}
        />
      </div>

      {/* ── Evoluție per Competență — Echipă ── */}
      <Card className="p-5">
        <h3 className="text-base font-semibold text-foreground">
          Evoluție per Competență — Echipă
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Media echipei: Test IN (baseline) vs nivel actual din sesiuni.
        </p>
        {data.competencies.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">
            Nicio competență aleasă pe proiect. Alege-le din Setări.
          </p>
        ) : (
          <ul className="mt-4 flex flex-col gap-4">
            {data.competencies.map((c) => (
              <li key={c.name} className="flex flex-col gap-1.5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="text-sm font-medium text-foreground">{c.name}</span>
                  <span className="text-xs text-muted-foreground">
                    <span
                      className="mr-2 inline-block rounded px-1.5 py-0.5 text-[11px] font-medium text-white"
                      style={{ backgroundColor: c.color }}
                    >
                      {c.level}
                    </span>
                    {c.currentAverage === null
                      ? "fără scoruri încă"
                      : `${c.currentAverage}% · ${c.scoresCount} scoruri`}
                  </span>
                </div>
                <ScaledBar value={c.currentAverage ?? 0} max={100} />
                <p className="text-[11px] text-muted-foreground">
                  Test IN: — · Test OUT: — ({data.testPendingNote})
                </p>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* ── Competențe — Ritm de Creștere ── */}
      <Card className="p-5">
        <h3 className="text-base font-semibold text-foreground">
          Competențe — Ritm de Creștere
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Delta față de Test IN. Pozitiv = progres, negativ = regresie.
        </p>
        <p className="mt-4 text-sm text-muted-foreground">
          Fără date suficiente (Test IN necesar) — {data.testPendingNote}.
        </p>
      </Card>

      {/* ── Evoluție Scor Mediu Echipă (Sesiuni Practice) ── */}
      <Card className="p-5">
        <h3 className="text-base font-semibold text-foreground">
          Evoluție Scor Mediu Echipă (Sesiuni Practice)
        </h3>
        {data.weeklyAverage.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">
            Încă nicio sesiune evaluată. Apare aici după prima.
          </p>
        ) : (
          <ul className="mt-4 flex flex-col gap-3">
            {data.weeklyAverage.map((w) => (
              <li key={w.weekStart} className="flex flex-col gap-1">
                <div className="flex items-baseline justify-between text-xs">
                  <span className="text-muted-foreground">
                    Săptămâna din {new Date(w.weekStart).toLocaleDateString("ro-RO")}
                  </span>
                  <span className="font-medium text-foreground">
                    {w.average}% · {w.scoresCount} scoruri
                  </span>
                </div>
                <ScaledBar value={w.average} max={maxWeekly} />
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* ── tabelul cu oamenii: de aici cobori la om ── */}
      <Card className="overflow-hidden">
        <div className="border-b px-5 py-4">
          <h3 className="text-base font-semibold text-foreground">Participanți</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Fila arată echipa; de aici cobori la om.
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-muted/40 text-left text-xs text-muted-foreground">
              <tr>
                <th className="px-5 py-3 font-medium">Nume</th>
                <th className="px-4 py-3 text-center font-medium">Test IN</th>
                <th className="px-4 py-3 text-center font-medium">Test OUT</th>
                <th className="px-4 py-3 text-center font-medium">Nivel actual</th>
                <th className="px-4 py-3 text-center font-medium">Sesiuni</th>
              </tr>
            </thead>
            <tbody>
              {data.participants.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-5 py-6 text-center text-muted-foreground">
                    Niciun participant în proiect.
                  </td>
                </tr>
              ) : (
                data.participants.map((p) => (
                  <tr key={p.participantProfileId} className="border-t">
                    <td className="px-5 py-3">
                      <Link
                        href={`/trainer/projects/${projectId}/evolutie/${p.participantProfileId}`}
                        className="font-medium text-foreground underline-offset-2 hover:underline"
                      >
                        {p.fullName}
                      </Link>
                      <span className="block text-xs text-muted-foreground">{p.email}</span>
                    </td>
                    <td className="px-4 py-3 text-center text-muted-foreground">—</td>
                    <td className="px-4 py-3 text-center text-muted-foreground">—</td>
                    <td className="px-4 py-3 text-center">
                      {p.currentAverage === null ? (
                        <span className="text-muted-foreground">—</span>
                      ) : (
                        <span className="font-medium">{p.currentAverage}%</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-center">
                      {p.closedSessionsCount}/{p.sessionsCount}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
        <p className="border-t px-5 py-3 text-xs text-muted-foreground">
          Coloanele Test IN și Test OUT {data.testPendingNote}.
        </p>
      </Card>
    </div>
  );
}

function Counter({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <CheckCircleIcon className="size-4" aria-hidden />
        {label}
      </div>
      <p className="mt-1 text-2xl font-semibold text-foreground">{value}</p>
      {note ? <p className="mt-1 text-[11px] text-muted-foreground">{note}</p> : null}
    </Card>
  );
}
