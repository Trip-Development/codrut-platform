"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  alegeObiectivul,
  getObiectiveleProiectului,
  getObiectivulMeu,
  type Obiectiv,
} from "@/api/obiective";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { TEXTE } from "./texte";

type Stare =
  | { tip: "incarca" }
  | { tip: "eroare" }
  | { tip: "gol" }
  | { tip: "lista"; obiective: Obiectiv[]; alesId: string | null };

/** Ecranul de alegere a obiectivului — plicul 232 (L1-P2). */
export function AlegereaObiectivului({ projectId, inapoiHref }: { projectId: string; inapoiHref: string }) {
  const router = useRouter();
  const [stare, setStare] = useState<Stare>(projectId ? { tip: "incarca" } : { tip: "gol" });
  const [salveaza, setSalveaza] = useState(false);
  const [eroareSalvare, setEroareSalvare] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    let activ = true;
    (async () => {
      try {
        const lista = await getObiectiveleProiectului(projectId);
        if (!lista.catalog || lista.obiective.length === 0) {
          if (activ) setStare({ tip: "gol" });
          return;
        }
        const meu = await getObiectivulMeu(projectId);
        if (activ) {
          setStare({
            tip: "lista",
            obiective: [...lista.obiective].sort((a, b) => a.nr - b.nr),
            alesId: meu.curent?.obiectiv.id ?? null,
          });
        }
      } catch {
        if (activ) setStare({ tip: "eroare" });
      }
    })();
    return () => {
      activ = false;
    };
  }, [projectId]);

  const alege = async (obiectivId: string) => {
    if (salveaza) return;
    setSalveaza(true);
    setEroareSalvare(false);
    try {
      await alegeObiectivul(projectId, obiectivId);
      router.push(inapoiHref);
    } catch {
      setEroareSalvare(true);
      setSalveaza(false);
    }
  };

  const inapoi = (
    <a href={inapoiHref} className="text-sm font-medium text-primary underline-offset-4 hover:underline">
      {TEXTE.T19}
    </a>
  );

  if (stare.tip === "incarca") {
    return <p className="text-sm text-muted-foreground">{TEXTE.T20}</p>;
  }
  if (stare.tip === "gol" || stare.tip === "eroare") {
    return (
      <div className="flex flex-col items-start gap-3">
        <p className="text-sm text-foreground">{stare.tip === "gol" ? TEXTE.T18 : TEXTE.T17}</p>
        {inapoi}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      {eroareSalvare ? (
        <div className="rounded-md border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
          {TEXTE.T16}
        </div>
      ) : null}
      <ul className="flex flex-col gap-3">
        {stare.obiective.map((obiectiv) => {
          const esteAles = obiectiv.id === stare.alesId;
          return (
            <li key={obiectiv.id}>
              <Card className={esteAles ? "border-2 border-primary bg-primary/5" : "border-2 border-border"}>
                <CardHeader className="pb-2">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <CardTitle className="text-base font-semibold">{obiectiv.titlu}</CardTitle>
                    {esteAles ? <Badge className="text-xs">{TEXTE.T14}</Badge> : null}
                  </div>
                </CardHeader>
                <CardContent className="flex flex-col gap-2 text-sm text-foreground">
                  {obiectiv.situatie.trim() ? <p>{TEXTE.T7(obiectiv.situatie)}</p> : null}
                  <p className="text-muted-foreground">{TEXTE.T8(obiectiv.semnDeReusita)}</p>
                  {esteAles ? null : (
                    <div>
                      <Button size="sm" variant="outline" disabled={salveaza} onClick={() => alege(obiectiv.id)}>
                        {TEXTE.T13}
                      </Button>
                    </div>
                  )}
                </CardContent>
              </Card>
            </li>
          );
        })}
      </ul>
      {inapoi}
    </div>
  );
}
