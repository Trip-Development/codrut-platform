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

  return (
    <div className="space-y-6 py-2">
      {/* Top Banner: XP, Streak, Badges */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Daily XP */}
        <Card className="border-border bg-surface shadow-xs">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Puncte Azi (XP)
              </CardTitle>
              <SparklesIcon className="size-4 text-amber-500" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-foreground">{data.xpToday}</span>
              <span className="text-xs text-muted-foreground">/ {data.xpDailyCap} XP</span>
            </div>
            {/* Progress bar */}
            <div className="w-full bg-muted rounded-full h-1.5 mt-2 overflow-hidden">
              <div
                className="bg-amber-500 h-1.5 rounded-full transition-all"
                style={{ width: `${Math.min(100, (data.xpToday / data.xpDailyCap) * 100)}%` }}
              />
            </div>
            <p className="text-[11px] text-muted-foreground mt-1.5">
              Plafon zilnic: maxim 100 XP / zi.
            </p>
          </CardContent>
        </Card>

        {/* Card 2: Streak */}
        <Card className="border-border bg-surface shadow-xs">
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Serie de Zile (Streak)
              </CardTitle>
              <FlameIcon className="size-4 text-orange-500" />
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-2">
              <span className="text-2xl font-bold text-orange-500">{data.streakDays}</span>
              <span className="text-xs font-semibold text-foreground">
                {data.streakDays === 1 ? "zi activă" : "zile consecutive"}
              </span>
            </div>
            <div className="mt-2">
              {data.streakBonusPct > 0 ? (
                <Badge className="bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-200 text-xs font-semibold">
                  +{data.streakBonusPct}% Bonus XP
                </Badge>
              ) : (
                <span className="text-[11px] text-muted-foreground">
                  Serie sub 3 zile (fără bonus)
                </span>
              )}
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
            <div className="text-2xl font-bold text-foreground">{data.xpTotal} XP</div>
            <p className="text-[11px] text-muted-foreground mt-2">
              Prag dovezi proiect: {data.evidenceCeiling}
            </p>
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
              <span className="flex items-center gap-1">
                <span className="size-2 rounded-full bg-[#639922]" /> Integrare
              </span>
              <span className="flex items-center gap-1">
                <span className="size-2 rounded-full bg-[#1A4A7A]" /> Consolidare
              </span>
              <span className="flex items-center gap-1">
                <span className="size-2 rounded-full bg-[#BA7517]" /> Aplicare
              </span>
              <span className="flex items-center gap-1">
                <span className="size-2 rounded-full bg-[#E24B4A]" /> Conștientizare
              </span>
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
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-rose-500">
                          Așa a fost:
                        </span>
                        <p className="text-muted-foreground italic pl-2 border-l-2 border-rose-400">
                          „{weakText}”
                        </p>
                      </div>
                    )}
                    {impText && (
                      <div className="space-y-0.5">
                        <span className="text-[10px] font-semibold uppercase tracking-wider text-emerald-600">
                          Așa ar fi sunat mai bine:
                        </span>
                        <p className="text-foreground font-medium pl-2 border-l-2 border-emerald-500">
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

function CompetencyCard({ item }: { item: CompetencyDashboardItem }) {
  return (
    <div className="p-4 rounded-lg border bg-surface shadow-2xs space-y-3">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <div className="space-y-1">
          <h4 className="text-sm font-bold text-foreground">{item.name}</h4>
          <p className="text-xs text-muted-foreground">{item.levelDescription}</p>
        </div>

        <div>
          <span
            className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-bold text-white shadow-xs"
            style={{ backgroundColor: item.color }}
          >
            {item.level}
          </span>
        </div>
      </div>

      {/* Metrics Row */}
      <div className="flex flex-wrap items-center gap-2 text-[11px] pt-1">
        <Badge variant="outline" className="text-[11px] font-normal">
          {item.totalRoleplays} simulări în rol
        </Badge>
        <Badge variant="outline" className="text-[11px] font-normal">
          {item.scores70Count} scoruri ≥ 70%
        </Badge>
        <Badge variant="outline" className="text-[11px] font-normal">
          {item.distinctDays70} zile diferite
        </Badge>
        {item.daysSpan70 > 0 && (
          <Badge variant="outline" className="text-[11px] font-normal">
            {item.daysSpan70} zile interval
          </Badge>
        )}
        <Badge variant="outline" className="text-[11px] font-normal">
          Medie: {item.averageScore}%
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
        fill="#1A4A7A"
        fillOpacity="0.35"
        stroke="#1A4A7A"
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
              fill={c.color || "#1A4A7A"}
              stroke="#ffffff"
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
