"use client";

import { useEffect, useState } from "react";
import { getReplicaZilei, type StareaZilei } from "@/api/replicaZilei";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { TEXTE } from "./texte";

/**
 * Cartonașul replicii zilei de pe Exersează — plicul 251 (L2-P2).
 *
 * Se arată numai când serverul dă situația de azi. Fără situație, fără acord sau la orice
 * eroare: nimic pe ecran, iar pagina rămâne exact ca înainte. Fără notă, serie sau puncte.
 */
export function CartonasulReplicaZilei({ projectId, href }: { projectId: string; href: string }) {
  const [stare, setStare] = useState<StareaZilei | null>(null);

  useEffect(() => {
    let activ = true;
    setStare(null);
    getReplicaZilei(projectId)
      .then((s) => activ && setStare(s))
      .catch(() => {
        // o eroare nu strică pagina: cartonașul nu apare
      });
    return () => {
      activ = false;
    };
  }, [projectId]);

  if (!stare?.situatie) return null;
  const facuta = stare.azi !== null;

  return (
    <Card className="border-2 border-primary/30 bg-primary/5">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">{TEXTE.T4}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col items-start gap-3 text-sm text-foreground">
        <p>{facuta ? TEXTE.T7 : TEXTE.T5}</p>
        <Button asChild className="min-h-11">
          <a href={href}>{facuta ? TEXTE.T8 : TEXTE.T6}</a>
        </Button>
      </CardContent>
    </Card>
  );
}
