import Link from "next/link";
import {
  AlertTriangleIcon,
  BookOpenIcon,
  CalendarIcon,
  CheckCircleIcon,
  ChevronRightIcon,
  TrendingUpIcon,
  UsersIcon,
  XCircleIcon,
  ZapIcon,
} from "lucide-react";

import type { TrainingRoom as TrainingRoomData } from "@/api/practice";
import { Card } from "@/components/ui/card";

/**
 * Camera de training — ecranul proiectului.
 *
 * Portat din `app/admin/projects/[projectId]/page.tsx` (411 rd.) al aplicației
 * vechi, citit întreg înainte. Secțiunile, ordinea lor și textele sunt ale ei;
 * îmbrăcămintea e a aplicației noi, ca să nu pară alt program.
 *
 * Andrei: „E ca și cum ai intra în altă cameră."
 *
 * Ce n-are date azi rămâne pe ecran, gol, cu textul lui de gol — nu se scoate
 * secțiunea. Camera trebuie văzută întreagă, chiar dacă unele rafturi sunt goale.
 */

// Cele patru culori ale nivelurilor se copiază ca atare: sunt limbaj, nu decor.
const NIVEL_BUN = "#639922";
const NIVEL_MIJLOC = "#BA7517";
const NIVEL_SLAB = "#E24B4A";

function culoareScor(scor: number): string {
  if (scor >= 70) return NIVEL_BUN;
  if (scor >= 36) return NIVEL_MIJLOC;
  return NIVEL_SLAB;
}

function dataRo(iso: string | null): string {
  if (!iso) return "Niciodată";
  return new Date(iso).toLocaleDateString("ro-RO");
}

export function TrainingRoom({
  room,
  basePath,
}: {
  room: TrainingRoomData;
  basePath: string;
}) {
  return (
    <div className="flex flex-col gap-5">
      {/* ── antet: tema · Activează Test OUT · Editează ── */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-lg font-semibold text-foreground">{room.projectName}</h2>
          <p className="text-sm text-muted-foreground">
            {room.themeName ?? "Fără Temă Setată"}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            disabled
            title="Testul de ieșire vine în pasul următor al plicului 30."
            className="rounded-md border px-3 py-2 text-sm font-medium text-muted-foreground opacity-60"
          >
            {room.testOutActive ? "Test OUT: Activ" : "Activează Test OUT"}
          </button>
          <Link
            href={`${basePath}/settings`}
            className="rounded-md border px-3 py-2 text-sm font-medium text-foreground"
          >
            Editează
          </Link>
        </div>
      </div>

      {room.practiceConfigured ? null : (
        <Card className="p-5">
          <p className="text-sm text-muted-foreground">
            Exersarea nu e configurată încă pe proiectul ăsta. Alege tema și
            competențele din{" "}
            <Link href={`${basePath}/settings`} className="underline underline-offset-2">
              Setări
            </Link>
            , ca participanții să poată începe.
          </p>
        </Card>
      )}

      {/* ── patru contoare ── */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Contor
          eticheta="Participanți"
          valoare={room.participantsTotal}
          icon={<UsersIcon className="size-5" aria-hidden />}
        />
        <Contor
          eticheta="Scor mediu"
          valoare={room.averageScore}
          icon={<TrendingUpIcon className="size-5" aria-hidden />}
          culoare={room.participantsTotal > 0 ? culoareScor(room.averageScore) : undefined}
        />
        <Contor
          eticheta="Sesiuni totale"
          valoare={room.sessionsTotal}
          icon={<CalendarIcon className="size-5" aria-hidden />}
        />
        <Contor
          eticheta="Inactivi"
          valoare={room.inactiveCount}
          icon={<AlertTriangleIcon className="size-5" aria-hidden />}
          culoare={room.inactiveCount > 0 ? NIVEL_SLAB : undefined}
        />
      </div>

      {/* ── Timeline Proiect ── */}
      <Card className="p-5">
        <h3 className="text-base font-semibold text-foreground">Timeline Proiect</h3>
        {room.timelinePercent === null ? (
          <p className="mt-3 text-sm text-muted-foreground">
            Proiectul nu are date de început și de sfârșit. Le poți pune din Setări.
          </p>
        ) : (
          <>
            <div className="mt-3 flex justify-between text-sm font-medium text-muted-foreground">
              <span>{dataRo(room.startsAt)} (Start)</span>
              <span className="text-foreground">
                Astăzi ({Math.round(room.timelinePercent)}%)
              </span>
              <span>{dataRo(room.dueAt)} (End)</span>
            </div>
            <div className="mt-2 h-4 w-full overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-burgundy"
                style={{ width: `${room.timelinePercent}%` }}
              />
            </div>
          </>
        )}
      </Card>

      {/* ── Participare & Engagement ── */}
      <Card className="p-5">
        <h3 className="text-base font-semibold text-foreground">Participare &amp; Engagement</h3>
        <div className="mt-5 grid grid-cols-2 gap-6 lg:grid-cols-4">
          <Bara
            eticheta="Test IN completat"
            numar={room.testInCompleted}
            total={room.participantsTotal}
            culoare="#9B0021"
            icon={<CheckCircleIcon className="size-4" aria-hidden />}
          />
          <Bara
            eticheta="Test OUT completat"
            numar={room.testOutCompleted}
            total={room.participantsTotal}
            culoare="#15803d"
            icon={<CheckCircleIcon className="size-4" aria-hidden />}
          />
          <Bara
            eticheta="Activi (7 zile)"
            numar={room.activeCount}
            total={room.participantsTotal}
            culoare="#2563eb"
            icon={<ZapIcon className="size-4" aria-hidden />}
          />
          <Bara
            eticheta="Recurenți (3+ sesiuni)"
            numar={room.recurrentCount}
            total={room.participantsTotal}
            culoare="#7c3aed"
            icon={<CalendarIcon className="size-4" aria-hidden />}
          />
        </div>
      </Card>

      {/* ── Evoluție per Competență — Echipă ── */}
      <Card className="p-5">
        <h3 className="text-base font-semibold text-foreground">
          Evoluție per Competență — Echipă
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Media echipei: Test IN (baseline) vs nivel actual din sesiuni
          {room.testOutCompleted > 0 ? " vs Test OUT (final)" : ""}.
        </p>
        {room.competencies.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">
            Nicio competență definită încă pentru acest proiect.
          </p>
        ) : (
          <ul className="mt-4 flex flex-col gap-4">
            {room.competencies.map((c) => (
              <li key={c.name} className="flex flex-col gap-1.5">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="text-sm font-medium text-foreground">{c.name}</span>
                  <span className="text-xs text-muted-foreground">
                    IN: {c.testIn}% → <span className="font-semibold text-foreground">Acum: {c.acum}%</span>
                    {c.testOut !== null ? ` → OUT: ${c.testOut}%` : ""}
                  </span>
                </div>
                <div className="flex gap-1">
                  <Coloana valoare={c.testIn} culoare="#94a3b8" titlu="Test IN (baseline)" />
                  <Coloana valoare={c.acum} culoare={culoareScor(c.acum)} titlu="Nivel actual" />
                  {c.testOut !== null ? (
                    <Coloana valoare={c.testOut} culoare="#15803d" titlu="Test OUT" />
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <div className="grid gap-5 lg:grid-cols-2">
        {/* ── Competențe — Ritm de Creștere ── */}
        <Card className="p-5">
          <h3 className="text-base font-semibold text-foreground">
            Competențe — Ritm de Creștere
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Delta față de Test IN. Pozitiv = progres, negativ = regresie.
          </p>
          {room.growthRanking.length === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">
              Fără date suficiente (Test IN necesar).
            </p>
          ) : (
            <ul className="mt-4 flex flex-col gap-3">
              {room.growthRanking.map((c, i) => {
                const delta = c.delta ?? 0;
                const sus = i < Math.ceil(room.growthRanking.length / 2);
                const culoare = delta > 0 ? "#15803d" : delta < 0 ? "#dc2626" : "#94a3b8";
                return (
                  <li key={c.name} className="flex items-center gap-3">
                    <span
                      className="w-5 text-center text-xs font-bold"
                      style={{ color: sus ? "#15803d" : "#dc2626" }}
                      aria-hidden
                    >
                      {sus ? "▲" : "▼"}
                    </span>
                    <div className="flex-1">
                      <div className="flex justify-between text-sm">
                        <span className="font-medium text-foreground">{c.name}</span>
                        <span className="font-bold" style={{ color: culoare }}>
                          {delta > 0 ? "+" : ""}
                          {delta}%
                        </span>
                      </div>
                      <div className="flex items-center gap-2 text-xs text-muted-foreground">
                        <span>IN: {c.testIn}%</span>
                        <span aria-hidden>→</span>
                        <span className="font-semibold text-foreground">Acum: {c.acum}%</span>
                        {c.testOut !== null ? (
                          <>
                            <span aria-hidden>→</span>
                            <span style={{ color: "#15803d" }}>OUT: {c.testOut}%</span>
                          </>
                        ) : null}
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>

        {/* ── Ce nu a fost înțeles bine ── */}
        <Card className="p-5">
          <div className="flex items-center gap-2">
            <BookOpenIcon className="size-4 text-burgundy" aria-hidden />
            <h3 className="text-base font-semibold text-foreground">
              Ce nu a fost înțeles bine
            </h3>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Scoruri medii din sesiunile de quiz, per competență. Sub 50% = zonă de risc.
          </p>
          {room.quizWeakSpots.length === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">
              Fără sesiuni de quiz înregistrate.
            </p>
          ) : (
            <ul className="mt-4 flex flex-col gap-4">
              {room.quizWeakSpots.map((q) => (
                <li key={q.name}>
                  <div className="flex justify-between text-sm">
                    <span className="font-medium text-foreground">{q.name}</span>
                    <span className="font-bold" style={{ color: culoareScor(q.average) }}>
                      {q.average}%
                    </span>
                  </div>
                  <div className="mt-1 h-2.5 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${q.average}%`, backgroundColor: culoareScor(q.average) }}
                    />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      {/* ── Evoluție Scor Mediu Echipă (Sesiuni Practice) ── */}
      <Card className="p-5">
        <h3 className="text-base font-semibold text-foreground">
          Evoluție Scor Mediu Echipă (Sesiuni Practice)
        </h3>
        {room.weeklyAverage.length === 0 ? (
          <p className="mt-4 text-sm text-muted-foreground">
            Încă nicio sesiune de practică evaluată.
          </p>
        ) : (
          <ul className="mt-4 flex flex-col gap-3">
            {room.weeklyAverage.map((w) => (
              <li key={w.weekStart} className="flex flex-col gap-1">
                <div className="flex items-baseline justify-between text-xs">
                  <span className="text-muted-foreground">
                    Săptămâna din {dataRo(w.weekStart)}
                  </span>
                  <span className="font-medium text-foreground">
                    {w.average}% · {w.scoresCount} scoruri
                  </span>
                </div>
                <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${w.average}%`, backgroundColor: culoareScor(w.average) }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </Card>

      {/* ── Listă Participanți ── */}
      <Card className="overflow-hidden">
        <div className="border-b px-5 py-4">
          <h3 className="text-base font-semibold text-foreground">
            Listă Participanți ({room.participants.length})
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-left text-sm">
            <thead className="bg-muted/40 text-xs uppercase tracking-wider text-muted-foreground">
              <tr>
                <th className="p-4 font-medium">Participant</th>
                <th className="p-4 font-medium">Status</th>
                <th className="p-4 text-center font-medium">Test IN</th>
                <th className="p-4 text-center font-medium">Test OUT</th>
                <th className="p-4 font-medium">Scor Curent</th>
                <th className="p-4 font-medium">Sesiuni</th>
                <th className="p-4 font-medium">Ultima activitate</th>
                <th className="p-4 text-right font-medium">Acțiuni</th>
              </tr>
            </thead>
            <tbody>
              {room.participants.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-muted-foreground">
                    Niciun participant înscris în acest proiect.
                  </td>
                </tr>
              ) : (
                room.participants.map((p) => (
                  <tr key={p.participantProfileId} className="border-t">
                    <td className="p-4">
                      <div className="flex items-center gap-3">
                        <span className="flex size-9 items-center justify-center rounded-full bg-muted text-sm font-bold text-foreground">
                          {(p.fullName || "??").slice(0, 2).toUpperCase()}
                        </span>
                        <span className="font-medium text-foreground">{p.fullName}</span>
                      </div>
                    </td>
                    <td className="p-4">
                      <span
                        className="inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium"
                        style={{
                          color: p.inactive ? "#991b1b" : "#166534",
                          backgroundColor: p.inactive ? "#fee2e2" : "#dcfce7",
                        }}
                      >
                        <span
                          className="size-1.5 rounded-full"
                          style={{ backgroundColor: p.inactive ? "#ef4444" : "#22c55e" }}
                        />
                        {p.inactive ? "Inactiv" : "Activ"}
                      </span>
                    </td>
                    <td className="p-4 text-center">
                      {p.hasTestIn ? (
                        <CheckCircleIcon className="mx-auto size-4" style={{ color: "#9B0021" }} aria-label="da" />
                      ) : (
                        <XCircleIcon className="mx-auto size-4 text-muted-foreground/40" aria-label="nu" />
                      )}
                    </td>
                    <td className="p-4 text-center">
                      {p.hasTestOut ? (
                        <CheckCircleIcon className="mx-auto size-4" style={{ color: "#15803d" }} aria-label="da" />
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="p-4">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-bold">{p.averageScore}</span>
                        <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${p.averageScore}%`,
                              backgroundColor: culoareScor(p.averageScore),
                            }}
                          />
                        </div>
                      </div>
                    </td>
                    <td className="p-4 text-muted-foreground">{p.sessionsCount}</td>
                    <td className="p-4 text-muted-foreground">{dataRo(p.lastActivity)}</td>
                    <td className="p-4 text-right">
                      <Link
                        href={`${basePath}/participant/${p.participantProfileId}`}
                        className="inline-flex items-center gap-1 rounded-lg px-3 py-1.5 text-sm font-medium text-burgundy hover:underline"
                      >
                        Diagnostic <ChevronRightIcon className="size-4" aria-hidden />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

function Contor({
  eticheta,
  valoare,
  icon,
  culoare,
}: {
  eticheta: string;
  valoare: number;
  icon: React.ReactNode;
  culoare?: string;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center gap-2 text-xs text-muted-foreground" style={{ color: culoare }}>
        {icon}
        {eticheta}
      </div>
      <p className="mt-1 text-2xl font-semibold text-foreground">{valoare}</p>
    </Card>
  );
}

function Bara({
  eticheta,
  numar,
  total,
  culoare,
  icon,
}: {
  eticheta: string;
  numar: number;
  total: number;
  culoare: string;
  icon: React.ReactNode;
}) {
  const procent = total > 0 ? Math.round((numar / total) * 100) : 0;
  return (
    <div>
      <div className="mb-2 flex items-center gap-2" style={{ color: culoare }}>
        {icon}
        <span className="text-sm font-semibold">{eticheta}</span>
      </div>
      <div className="mb-2 flex items-end gap-2">
        <span className="text-3xl font-bold text-foreground">{numar}</span>
        <span className="mb-1 text-sm text-muted-foreground">/ {total}</span>
        <span className="mb-1 text-sm font-bold" style={{ color: culoare }}>
          {procent}%
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full"
          style={{ width: `${procent}%`, backgroundColor: culoare }}
        />
      </div>
    </div>
  );
}

function Coloana({
  valoare,
  culoare,
  titlu,
}: {
  valoare: number;
  culoare: string;
  titlu: string;
}) {
  return (
    <div className="flex-1" title={`${titlu}: ${valoare}%`}>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full"
          style={{ width: `${valoare}%`, backgroundColor: culoare }}
        />
      </div>
    </div>
  );
}
