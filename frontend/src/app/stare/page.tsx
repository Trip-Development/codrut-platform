"use client";

import { useEffect, useState } from "react";
import {
  ActivityIcon,
  CheckCircle2Icon,
  AlertCircleIcon,
  BookOpenIcon,
  CpuIcon,
  DollarSignIcon,
  MessageSquareIcon,
  RefreshCwIcon,
  ShieldCheckIcon,
} from "lucide-react";
import { getPracticeStareSummary, type PracticeStareSummary } from "@/api/practice";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

export default function StarePage() {
  const [data, setData] = useState<PracticeStareSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<string>("");

  const loadStare = async () => {
    setLoading(true);
    setError(null);
    try {
      const summary = await getPracticeStareSummary();
      setData(summary);
      setLastRefreshed(new Date().toLocaleTimeString("ro-RO"));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Nu am putut încărca starea");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadStare();
    const timer = setInterval(loadStare, 30000);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="min-h-screen bg-background text-foreground py-8 px-4 sm:px-6 lg:px-8">
      <div className="max-w-4xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-4 border-b">
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold tracking-tight">Panou Stare Sistem — Cody</h1>
              <Badge variant="outline" className="text-xs">
                Probă
              </Badge>
            </div>
            <p className="text-sm text-muted-foreground mt-1">
              Verificarea stării de funcționare, a memoriei din Bibliotecă și a consumului Vertex AI.
            </p>
          </div>

          <div className="flex items-center gap-3">
            {lastRefreshed && (
              <span className="text-xs text-muted-foreground">
                Actualizat: {lastRefreshed}
              </span>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={loadStare}
              disabled={loading}
              className="gap-1.5"
            >
              <RefreshCwIcon className={`size-3.5 ${loading ? "animate-spin" : ""}`} />
              Reîmprospătează
            </Button>
          </div>
        </div>

        {error && (
          <div className="p-4 rounded-lg bg-destructive/10 border border-destructive/20 text-destructive flex items-center gap-3">
            <AlertCircleIcon className="size-5 shrink-0" />
            <div>
              <p className="font-semibold text-sm">Eroare de comunicare</p>
              <p className="text-xs mt-0.5">{error}</p>
            </div>
          </div>
        )}

        {data && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Card 1: Stare generală */}
            <Card className="border-border bg-surface">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Stare Funcționare
                  </CardTitle>
                  <CheckCircle2Icon className="size-4 text-emerald-500" />
                </div>
              </CardHeader>
              <CardContent>
                <div className="text-xl font-bold text-emerald-600 flex items-center gap-2">
                  <span className="inline-block size-2.5 rounded-full bg-emerald-500 animate-pulse" />
                  {data.statusText}
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  Toate serviciile (API, DB, Redis, Vertex AI) răspund optim.
                </p>
              </CardContent>
            </Card>

            {/* Card 2: Prompt și Memorie Bibliotecă */}
            <Card className="border-border bg-surface">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Prompt & Memorie Bibliotecă
                  </CardTitle>
                  <BookOpenIcon className="size-4 text-primary" />
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-baseline gap-2">
                  <span className="text-xl font-bold">{data.promptVersion}</span>
                  <span className="text-xs text-muted-foreground">
                    ({data.materialBytes.toLocaleString("ro-RO")} octeți citiți)
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  {data.materialBytes > 0
                    ? "Cele 4 sloturi de miez din Bibliotecă sunt încărcate integral."
                    : "Atenție: Biblioteca nu a returnat octeți de conținut."}
                </p>
              </CardContent>
            </Card>

            {/* Card 3: Model & Regiune Vertex */}
            <Card className="border-border bg-surface">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Model & Regiune
                  </CardTitle>
                  <CpuIcon className="size-4 text-primary" />
                </div>
              </CardHeader>
              <CardContent>
                <div className="text-lg font-bold">{data.model}</div>
                <div className="flex items-center gap-2 mt-1">
                  <Badge variant="outline" className="text-[11px] font-mono">
                    {data.region}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    Provider: {data.provider}
                  </span>
                </div>
              </CardContent>
            </Card>

            {/* Card 4: Consum și Sesiuni Azi */}
            <Card className="border-border bg-surface">
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-sm font-medium text-muted-foreground">
                    Activitate & Cost Azi
                  </CardTitle>
                  <DollarSignIcon className="size-4 text-primary" />
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-baseline gap-3">
                  <span className="text-xl font-bold">${data.costTodayUsd.toFixed(4)}</span>
                  <span className="text-xs text-muted-foreground">
                    {data.sessionsToday} sesiuni / {data.turnsToday} replici
                  </span>
                </div>
                <p className="text-xs text-muted-foreground mt-2">
                  Unități din cache: <span className="font-semibold text-foreground">{data.cachedTurns}</span> ({data.cachePercent}% din volumul promptului)
                </p>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Card Ultima Eroare */}
        {data && (
          <Card className="border-border bg-surface">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Jurnal Erori Recente
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data.lastError ? (
                <div className="p-3 rounded bg-destructive/10 text-destructive text-xs font-mono">
                  {data.lastError}
                </div>
              ) : (
                <div className="text-xs text-muted-foreground flex items-center gap-2">
                  <ShieldCheckIcon className="size-4 text-emerald-500" />
                  Nicio eroare înregistrată.
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
