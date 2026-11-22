"use client";

import { useEffect, useState } from "react";
import { getNotificare, opresteNotificarea, pornesteNotificarea, stareaNotificarii } from "@/api/notificareZilnica";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  aboneaza,
  abonareaDeAcum,
  dezaboneaza,
  eIphoneFaraEcranPrincipal,
  permisiunea,
  PermisiuneRefuzata,
  suportat,
} from "@/lib/notificare-browser";
import { TEXTE_NOTIFICARE as T, textulOrei, textulPornita } from "./texte-notificare";

type Faza = "ascuns" | "iphone" | "fara_suport" | "blocat" | "oprita" | "porneste" | "pornita";
const ORA_PROPUSA = 9;

/**
 * Notificarea zilnică a replicii zilei — plicul 252 (L3-P2).
 *
 * OPRITĂ până o pornește omul cu T5 (telefonul întreabă de permisiune numai atunci). Cartonașul
 * nu apare deloc dacă serverul spune că notificarea nu e disponibilă sau refuză omul.
 */
export function NotificareaZilnica({ projectId }: { projectId: string }) {
  const [faza, setFaza] = useState<Faza>("ascuns");
  const [cheie, setCheie] = useState<string | null>(null);
  const [ore, setOre] = useState<number[]>([]);
  const [ora, setOra] = useState(ORA_PROPUSA);
  const [endpoint, setEndpoint] = useState<string | null>(null);
  const [eroare, setEroare] = useState<string | null>(null);

  useEffect(() => {
    let activ = true;
    (async () => {
      let info;
      try {
        info = await getNotificare(projectId);
      } catch {
        return; // refuzul omului sau orice eroare: nimic pe ecran
      }
      if (!activ || !info.disponibila || !info.cheiePublica) return;
      setCheie(info.cheiePublica);
      setOre(info.ore);
      if (eIphoneFaraEcranPrincipal()) return setFaza("iphone");
      if (!suportat()) return setFaza("fara_suport");
      if (permisiunea() === "denied") return setFaza("blocat");
      try {
        const acum = await abonareaDeAcum();
        if (acum) {
          const stare = await stareaNotificarii(projectId, acum);
          if (!activ) return;
          setEndpoint(acum);
          if (stare.pornita && stare.ora !== null) {
            setOra(stare.ora);
            return setFaza("pornita");
          }
        }
      } catch {
        // starea nu s-a putut afla: arătăm notificarea oprită
      }
      if (activ) setFaza("oprita");
    })();
    return () => {
      activ = false;
    };
  }, [projectId]);

  async function porneste() {
    if (!cheie) return;
    setEroare(null);
    setFaza("porneste");
    let adresa: string;
    try {
      adresa = await aboneaza(cheie);
    } catch (e) {
      if (e instanceof PermisiuneRefuzata && permisiunea() === "denied") return setFaza("blocat");
      setEroare(T.T13);
      return setFaza("oprita");
    }
    try {
      const stare = await pornesteNotificarea(projectId, adresa, ora);
      setEndpoint(adresa);
      setOra(stare.ora ?? ora);
      setFaza("pornita");
    } catch {
      await dezaboneaza().catch(() => undefined);
      setEroare(T.T13);
      setFaza("oprita");
    }
  }

  async function schimbaOra(noua: number) {
    setOra(noua);
    if (faza !== "pornita" || !endpoint) return;
    setEroare(null);
    try {
      const stare = await pornesteNotificarea(projectId, endpoint, noua);
      setOra(stare.ora ?? noua);
    } catch {
      setEroare(T.T13);
    }
  }

  async function opreste() {
    setEroare(null);
    try {
      await dezaboneaza();
    } catch {
      return setEroare(T.T14);
    }
    if (endpoint) await opresteNotificarea(projectId, endpoint).catch(() => undefined);
    setEndpoint(null);
    setFaza("oprita");
  }

  if (faza === "ascuns") return null;

  const listaOrelor = (
    <label className="flex w-full flex-col gap-1">
      <span className="text-sm font-medium">{T.T3}</span>
      <select
        className="min-h-11 w-full rounded-md border border-control-border bg-control px-3 text-sm"
        value={ora}
        disabled={faza === "porneste"}
        onChange={(e) => void schimbaOra(Number(e.target.value))}
      >
        {ore.map((o) => (
          <option key={o} value={o}>
            {textulOrei(o)}
          </option>
        ))}
      </select>
    </label>
  );

  return (
    <Card className="mt-4">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-semibold">{T.T1}</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-3 text-sm text-foreground">
        {faza === "iphone" && <p>{T.T10}</p>}
        {faza === "fara_suport" && <p>{T.T11}</p>}
        {faza === "blocat" && <p>{T.T12}</p>}
        {(faza === "oprita" || faza === "porneste") && (
          <>
            <p>{T.T2}</p>
            {listaOrelor}
            <Button className="min-h-11 w-full" disabled={faza === "porneste"} onClick={() => void porneste()}>
              {faza === "porneste" ? T.T6 : T.T5}
            </Button>
            <p className="text-muted-foreground">{T.T15}</p>
          </>
        )}
        {faza === "pornita" && (
          <>
            <p>{textulPornita(ora)}</p>
            <p>{T.T8}</p>
            {listaOrelor}
            <Button className="min-h-11 w-full" variant="outline" onClick={() => void opreste()}>
              {T.T9}
            </Button>
            <p className="text-muted-foreground">{T.T15}</p>
          </>
        )}
        {eroare && <p role="alert">{eroare}</p>}
      </CardContent>
    </Card>
  );
}
