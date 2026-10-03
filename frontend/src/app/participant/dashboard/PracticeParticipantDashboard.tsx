"use client";

import React, { useEffect, useState } from "react";
import {
  getPracticeDashboard,
  type PracticeDashboardData,
  type CompetencyDashboardItem,
} from "@/api/practice";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  FlameIcon,
  SparklesIcon,
  AwardIcon,
  ArrowRightIcon,
  RefreshCwIcon,
  AlertCircleIcon,
  CheckCircle2Icon,
  HelpCircleIcon,
} from "lucide-react";
import Link from "next/link";
import { CULOARE_NIVEL, culoareNivel, type Nivel } from "@/lib/culori-nivel";
import { NOTA_MINIMA, procentPanaLaPragulUrmator } from "@/lib/praguri-puncte";
import { PRAG_AFISARE_IMPINGERE, textImpingere } from "../texte-177";

interface PracticeParticipantDashboardProps {
  projectId?: string | null;
}

export function PracticeParticipantDashboard({ projectId }: PracticeParticipantDashboardProps) {
  const [data, setData] = useState<PracticeDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getPracticeDashboard(projectId || undefined);
      setData(res);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Nu am putut încărca tabloul");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [projectId]);

  if (loading) {
    return (
      <div className="py-12 flex flex-col items-center justify-center gap-3">
        <RefreshCwIcon className="size-6 animate-spin text-primary" />
        <p className="text-sm text-muted-foreground">Se încarcă tabloul de bord...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive flex items-center justify-between">
        <div className="flex items-center gap-3">
          <AlertCircleIcon className="size-5 shrink-0" />
          <p className="text-sm font-medium">{error || "Nu există date disponibile"}</p>
        </div>
        <Button size="sm" variant="outline" onClick={loadData}>
          Reîncearcă
        </Button>
      </div>
    );
  }

  // Omul fara nicio nota afla de ce e gol tabloul — plicul 98. Textele sunt ale lui Andrei si
  // vin de la server; aici nu se scrie niciunul. Cine e inscris pastreaza butonul de exersare.
  if (data.emptyState) {
    return (
      <Card className="border-border bg-surface shadow-xs">
        <CardHeader>
          <CardTitle className="text-base">{data.emptyState.title}</CardTitle>
          <CardDescription>{data.emptyState.description}</CardDescription>
        </CardHeader>
        {data.emptyState.kind === "neexersat" && (
          <CardContent className="pt-0">
            <Link href="/participant/practice">
              <Button size="sm" className="gap-1.5 text-xs">
                <span>Exersează acum</span>
                <ArrowRightIcon className="size-3.5" />
              </Button>
            </Link>
          </CardContent>
        )}
      </Card>
    );
  }

  return (
    <div className="space-y-6 py-2">
      {/* Codul cu care Cody îl știe pe om — plicul 138. Text provizoriu, al lui Andrei de hotărât. */}
      {data.codyAlias && (
        <p className="text-sm text-muted-foreground">
          Codul tău la Cody: <span className="font-semibold text-foreground">{data.codyAlias}</span>
        </p>
      )}
      {/* Top Banner: XP, Streak, Badges */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Daily XP */}
        <Card className="border-border bg-surface shadow-xs">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Puncte azi
              </CardTitle>
              <SparklesIcon className="size-4 text-gold" />
            </div>
          </CardHeader>
          <CardContent>
            {/* Punctajul nou — plicul 165: fără plafon zilnic */}
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-foreground">{data.pointsToday}</span>
              <span className="text-xs text-muted-foreground">puncte</span>
            </div>
          </CardContent>
        </Card>

        {/* Card 2: Streak */}
        <Card className="border-border bg-surface shadow-xs">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Serie de zile
              </CardTitle>
              <FlameIcon className="size-4 text-gold" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-foreground">{data.streakDays}</span>
              <span className="text-xs font-semibold text-foreground">
                {data.streakDays === 1 ? "zi activă" : "zile consecutive"}
              </span>
            </div>
          </CardContent>
        </Card>

        {/* Card 3: Total XP */}
        <Card className="border-border bg-surface shadow-xs">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Total Acumulat
              </CardTitle>
              <AwardIcon className="size-4 text-primary" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">{data.pointsTotal} puncte</div>
          </CardContent>
        </Card>

        {/* Card 4: Quick Action */}
        <Card className="border-primary/20 bg-primary/5 shadow-xs flex flex-col justify-between">
          <CardHeader className="pb-2">
            <CardTitle className="text-xs font-semibold uppercase tracking-wider text-primary">
              Antrenament Live
            </CardTitle>
            <CardDescription className="text-xs text-muted-foreground">
              Continuă dialogul cu Cody
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
            <Link href="/participant/practice">
              <Button size="sm" className="w-full gap-1.5 text-xs">
                <span>Exersează acum</span>
                <ArrowRightIcon className="size-3.5" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      </div>

      {/* Main Section: Spider / Radar Chart & Competencies */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Radar / Spider Chart */}
        <Card className="border-border bg-surface shadow-xs lg:col-span-1">
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">Harta Competențelor</CardTitle>
            <CardDescription className="text-xs">
              Echilibrul deprinderilor dobândite în simulări
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col items-center justify-center pt-2">
            <RadarChartSVG competencies={data.competencies} />
            <div className="flex flex-wrap items-center justify-center gap-3 mt-4 text-[11px] text-muted-foreground">
              {LEGENDA.map(([nivel, eticheta]) => (
                <span key={nivel} className="flex items-center gap-1">
                  <span className="size-2 rounded-full" style={{ backgroundColor: CULOARE_NIVEL[nivel].punct }} /> {eticheta}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Competency Level Cards List */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-foreground">
              Nivelul pe fiecare competență
            </h3>
            <span className="text-xs text-muted-foreground">
              {data.competencies.length} competențe evaluate
            </span>
          </div>

          <div className="space-y-3">
            {data.competencies.map((comp) => (
              <CompetencyCard key={comp.name} item={comp} />
            ))}
          </div>
        </div>
      </div>

      {/* Bottom Section: Insight Moments & Session Samples */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pt-2">
        {/* Insight Moments */}
        <Card className="border-border bg-surface shadow-xs">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <span className="text-base">💡</span>
              <CardTitle className="text-base font-semibold">Momente de Intuiție</CardTitle>
            </div>
            <CardDescription className="text-xs">
              Conștientizări și descoperiri-cheie desprinse din conversațiile tale
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.insightMoments.length === 0 ? (
              <p className="text-xs text-muted-foreground py-4 text-center">
                Niciun moment extras încă. Exersează o simulare cu Cody!
              </p>
            ) : (
              data.insightMoments.slice(0, 5).map((m) => (
                <div
                  key={m.id}
                  className="p-3 rounded-md bg-muted/40 border text-xs space-y-1.5"
                >
                  <div className="flex items-center justify-between text-[11px] text-muted-foreground">
                    <span className="font-semibold text-primary">
                      {m.competencyName || "Observație generală"}
                    </span>
                    <span>{new Date(m.createdAt).toLocaleDateString("ro-RO")}</span>
                  </div>
                  <p className="text-foreground leading-relaxed">{m.summary}</p>
                </div>
              ))
            )}
          </CardContent>
        </Card>

        {/* Session Samples */}
        <Card className="border-border bg-surface shadow-xs">
          <CardHeader className="pb-3">
            <div className="flex items-center gap-2">
              <span className="text-base">🎯</span>
              <CardTitle className="text-base font-semibold">
                Mostre din Conversații
              </CardTitle>
            </div>
            <CardDescription className="text-xs">
              Cum a sunat replica ta vs. cum ar fi sunat mai articulat
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {data.sessionSamples.length === 0 ? (
              <p className="text-xs text-muted-foreground py-4 text-center">
                Nu există mostre comparative salvate încă.
              </p>
            ) : (
              data.sessionSamples.slice(0, 4).map((s) => {
                const weakText = s.realWeak || s.inventedWeak;
                const impText = s.realImproved || s.inventedImproved;
                return (
                  <div
                    key={s.id}
                    className="p-3 rounded-md bg-muted/40 border text-xs space-y-2"
                  >
                    {weakText && (
                      <div className="space-y-0.5">
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-destructive">
                          Așa a fost:
                        </span>
                        <p className="text-muted-foreground italic pl-2 border-l-2 border-destructive">
                          „{weakText}”
                        </p>
                      </div>
                    )}
                    {impText && (
                      <div className="space-y-0.5">
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-success-ink">
                          Așa ar fi sunat mai bine:
                        </span>
                        <p className="text-foreground font-medium pl-2 border-l-2 border-success-ink">
                          „{impText}”
                        </p>
                      </div>
                    )}
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// Legenda radarului, în ordinea de azi; culorile vin din paleta A (plicul 175).
const LEGENDA: Array<[Nivel, string]> = [
  ["INTEGRARE", "Integrare"],
  ["CONSOLIDARE", "Consolidare"],
  ["APLICARE", "Aplicare"],
  ["CONȘTIENTIZARE", "Conștientizare"],
];

function CompetencyCard({ item }: { item: CompetencyDashboardItem }) {
  const culoare = culoareNivel(item.level);
  return (
    <div className="p-4 rounded-lg border bg-surface shadow-2xs space-y-3">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="space-y-1">
          <h4 className="text-sm font-bold text-foreground">{item.name}</h4>
          <p className="text-xs text-muted-foreground">{item.levelDescription}</p>
        </div>

        <div>
          <span
            className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold shadow-xs ${culoare.fond} ${culoare.text}`}
          >
            {item.level}
          </span>
        </div>
      </div>

      {/* Bara spre pragul următor — plicul 175; textul rămâne „N puncte” și „De ce nu e mai sus?” */}
      <div className="h-2 w-full overflow-hidden rounded-full bg-track" aria-hidden="true">
        <div
          data-bara-puncte={item.name}
          className="h-full rounded-full bg-[linear-gradient(90deg,var(--gold),var(--burgundy))]"
          style={{ width: `${procentPanaLaPragulUrmator(item.points, item.level)}%` }}
        />
      </div>

      <MesajulNoteiDeAzi item={item} />

      {/* Metrics Row */}
      <div className="flex flex-wrap items-center gap-2 text-[11px] pt-1">
        {/* Punctajul nou — plicul 165 */}
        <Badge variant="outline" className="text-[11px] font-semibold">
          {item.points} puncte
        </Badge>
        <Badge variant="outline" className="text-[11px] font-normal">
          {item.totalRoleplays} simulări în rol
        </Badge>
        <Badge variant="outline" className="text-[11px] font-normal">
          Medie: {item.averageScore}%
        </Badge>
        <Badge variant="outline" className="text-[11px] font-normal">
          {item.interlocutorTypes} {item.interlocutorTypes === 1 ? "tip" : "tipuri"} de interlocutor
        </Badge>
      </div>

      {/* Why not higher explanation */}
      {item.whyNotHigher && (
        <div className="p-2.5 rounded bg-muted/50 text-xs flex items-start gap-2 text-muted-foreground border border-border/50">
          <HelpCircleIcon className="size-3.5 shrink-0 mt-0.5 text-primary" />
          <div>
            <span className="font-semibold text-foreground">De ce nu e mai sus? </span>
            <span>{item.whyNotHigher}</span>
          </div>
        </div>
      )}
    </div>
  );
}

/**
 * Mesajul (a) — plicul 177, text propus (Andrei îl vede pe probă). Numai când nota de azi e între 50 și
 * 59 și competența n-are încă niciun punct: „până la primele puncte” ar minți la cine are deja puncte.
 */
function MesajulNoteiDeAzi({ item }: { item: CompetencyDashboardItem }) {
  const nota = item.bestScoreToday;
  if (nota === null || nota < PRAG_AFISARE_IMPINGERE || nota >= NOTA_MINIMA || item.points > 0) {
    return null;
  }
  const text = textImpingere(item.name, nota);
  const bucata = `nota ${nota}`;
  const i = text.indexOf(bucata);
  return (
    <p role="status" className="rounded-[14px] bg-gold-soft px-[13px] py-[11px] text-[0.8rem] text-nudge-ink">
      {text.slice(0, i)}
      <strong>{bucata}</strong>
      {text.slice(i + bucata.length)}
    </p>
  );
}

function RadarChartSVG({ competencies }: { competencies: CompetencyDashboardItem[] }) {
  if (competencies.length === 0) {
    return <div className="text-xs text-muted-foreground">Fără date pentru grafic.</div>;
  }

  const size = 260;
  const center = size / 2;
  const radius = center - 35;
  const count = competencies.length;

  const levelValues: Record<string, number> = {
    CONȘTIENTIZARE: 0.25,
    APLICARE: 0.5,
    CONSOLIDARE: 0.75,
    INTEGRARE: 1.0,
  };

  const getCoordinates = (index: number, valueFactor: number) => {
    const angle = (Math.PI * 2 / count) * index - Math.PI / 2;
    const r = radius * valueFactor;
    return {
      x: center + r * Math.cos(angle),
      y: center + r * Math.sin(angle),
    };
  };

  const polygonPoints = competencies
    .map((c, i) => {
      const val = levelValues[c.level] || (c.averageScore / 100) || 0.25;
      const { x, y } = getCoordinates(i, val);
      return `${x},${y}`;
    })
    .join(" ");

  return (
    <svg width={size} height={size} className="overflow-visible">
      {/* Background concentric webs */}
      {[0.25, 0.5, 0.75, 1.0].map((level, lvlIdx) => {
        const ringPoints = Array.from({ length: count })
          .map((_, i) => {
            const { x, y } = getCoordinates(i, level);
            return `${x},${y}`;
          })
          .join(" ");
        return (
          <polygon
            key={lvlIdx}
            points={ringPoints}
            fill="none"
            stroke="currentColor"
            className="text-muted/40"
            strokeWidth="1"
            strokeDasharray={lvlIdx < 3 ? "3 3" : undefined}
          />
        );
      })}

      {/* Axis lines */}
      {Array.from({ length: count }).map((_, i) => {
        const { x, y } = getCoordinates(i, 1.0);
        return (
          <line
            key={i}
            x1={center}
            y1={center}
            x2={x}
            y2={y}
            stroke="currentColor"
            className="text-muted/50"
            strokeWidth="1"
          />
        );
      })}

      {/* Data Polygon */}
      <polygon
        points={polygonPoints}
        fill="var(--burgundy)"
        fillOpacity="0.15"
        stroke="var(--burgundy)"
        strokeWidth="2.5"
      />

      {/* Data Points and Labels */}
      {competencies.map((c, i) => {
        const val = levelValues[c.level] || (c.averageScore / 100) || 0.25;
        const { x, y } = getCoordinates(i, val);
        const labelCoord = getCoordinates(i, 1.22);
        return (
          <g key={i}>
            <circle
              cx={x}
              cy={y}
              r="4.5"
              fill={culoareNivel(c.level).punct}
              stroke="var(--surface)"
              strokeWidth="1.5"
            />
            <text
              x={labelCoord.x}
              y={labelCoord.y}
              textAnchor="middle"
              dominantBaseline="central"
              className="text-[9px] font-semibold fill-foreground"
            >
              {c.name.length > 14 ? `${c.name.slice(0, 12)}...` : c.name}
            </text>
          </g>
        );
      })}
    </svg>
  );
}
