"use client";

import { useEffect, useState } from "react";
import { getObiectiveleProiectului, getObiectivulMeu, type ObiectivulMeu } from "@/api/obiective";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { saptamanaDin8 } from "./saptamana";
import { TEXTE } from "./texte";

/**
 * Cartonașul obiectivului de pe Exersează — plicul 232 (L1-P2).
 *
 * Proiectul fără listă de obiective, lista goală sau orice eroare = nimic pe ecran:
 * proiectele de azi arată exact ca înainte, iar o eroare nu strică pagina.
 */
export function ObiectivulCurent({
  projectId,
  obiectivHref,
  onExerseaza,
  blocat,
}: {
  projectId: string;
  obiectivHref: string;
  onExerseaza: () => void;
  blocat: boolean;
}) {
  const [stare, setStare] = useState<ObiectivulMeu | null>(null);

  useEffect(() => {
    let activ = true;
    setStare(null);
    (async () => {
      try {
        const lista = await getObiectiveleProiectului(projectId);
        if (!lista.catalog || lista.obiective.length === 0) return;
        const meu = await getObiectivulMeu(projectId);
        if (activ) setStare(meu);
      } catch {
        // o eroare nu strică ecranul: cartonașul nu apare
      }
    })();
    return () => {
      activ = false;
    };
  }, [projectId]);

  if (!stare) return null;

  if (!stare.curent) {
    return (
      <Card className="border-2 border-primary/30 bg-primary/5">
        <CardHeader className="pb-2">
          <CardTitle className="text-base font-semibold">{TEXTE.T1}</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col items-start gap-3 text-sm text-foreground">
          <p>{TEXTE.T2}</p>
          <Button asChild size="sm">
            <a href={obiectivHref}>{TEXTE.T3}</a>
          </Button>
        </CardContent>
      </Card>
    );
  }

  const { obiectiv } = stare.curent;
  const saptamana = stare.primaAlegereLa ? saptamanaDin8(stare.primaAlegereLa, new Date()) : 1;

  return (
    <Card className="border-2 border-primary/30 bg-primary/5">
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <Badge variant="outline" className="text-xs">
            {TEXTE.T4}
          </Badge>
          <span className="text-xs text-muted-foreground">
            {saptamana === null ? TEXTE.T6 : TEXTE.T5(saptamana)}
          </span>
        </div>
        <CardTitle className="mt-2 text-base font-semibold">{obiectiv.titlu}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-2 text-sm text-foreground">
        {obiectiv.situatie.trim() ? <p>{TEXTE.T7(obiectiv.situatie)}</p> : null}
        <p className="text-muted-foreground">{TEXTE.T8(obiectiv.semnDeReusita)}</p>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <Button size="sm" disabled={blocat} onClick={onExerseaza}>
            {TEXTE.T9}
          </Button>
          <a href={obiectivHref} className="text-sm font-medium text-primary underline-offset-4 hover:underline">
            {TEXTE.T10}
          </a>
        </div>
        {blocat ? <p className="text-xs text-muted-foreground">{TEXTE.T11}</p> : null}
      </CardContent>
    </Card>
  );
}
