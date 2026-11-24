"use client";

import { useEffect, useRef, useState } from "react";
import { MicIcon, MicOffIcon, Loader2Icon } from "lucide-react";
import { getReplicaZilei, trimiteReplicaZilei, type StareaZilei } from "@/api/replicaZilei";
import { PracticeError } from "@/api/practice";
import { useVoiceToText } from "@/hooks/useVoiceToText";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { TEXTE, formateazaNota, textulSituatiei } from "./texte";

/**
 * Ecranul replicii zilei — plicul 251 (L2-P2). Telefon întâi: o singură coloană.
 *
 * Totul e al omului: nimic de aici nu ajunge la trainer, la HR sau pe Tablou.
 * Răspunsul profesorului se arată întreg, exact cum l-a întors serverul (236).
 * Plicul 267: răspunsul vine din fundal; cât e „în lucru”, ecranul întreabă serverul la 2 s.
 */

const PAS_RASPUNS_MS = 2000;
// 120 s limita generală + 30 s până se socotește lipsă + 10 s rezervă
const CAT_ASTEPTAM_RASPUNS_MS = 160000;

// Mesajele serverului (S2–S5) se arată cum vin; celelalte coduri au textul lor.
const MESAJUL_SERVERULUI = new Set(["situatia_alta", "replica_goala", "replica_zilei_indisponibila", "profesor_indisponibil"]);

function mesajLaTrimitere(err: unknown): string {
  const cod = err instanceof PracticeError ? err.code : "";
  if (MESAJUL_SERVERULUI.has(cod) && err instanceof PracticeError && err.message) return err.message;
  if (cod === "acord_lipsa") return TEXTE.T27;
  if (cod === "practice_not_enabled") return TEXTE.T34;
  if (cod === "budget_exceeded") return TEXTE.T31;
  if (cod === "practice_busy") return TEXTE.T32;
  if (cod === "practice_turn_too_long") return TEXTE.T33;
  return TEXTE.T35;
}

function mesajLaIncarcare(err: unknown): string {
  const cod = err instanceof PracticeError ? err.code : "";
  if (cod === "acord_lipsa") return TEXTE.T27;
  if (cod === "practice_not_enabled") return TEXTE.T34;
  return TEXTE.T30;
}

export function ReplicaZilei({ projectId, exerseazaHref }: { projectId: string; exerseazaHref: string }) {
  const [stare, setStare] = useState<StareaZilei | null>(null);
  const [eroareIncarcare, setEroareIncarcare] = useState<string | null>(null);
  const [replica, setReplica] = useState("");
  const [trimite, setTrimite] = useState(false);
  const [eroare, setEroare] = useState<string | null>(null);
  // plicul 267: replica trimisă, ca omul s-o regăsească în casetă dacă profesorul cade
  const replicaTrimisa = useRef("");
  const primaIntrebare = useRef<number | null>(null);
  const inLucru = stare?.azi?.inLucru === true;
  if (stare?.azi) replicaTrimisa.current = stare.azi.replica;

  useEffect(() => {
    if (!inLucru) {
      primaIntrebare.current = null;
      return;
    }
    if (primaIntrebare.current === null) primaIntrebare.current = Date.now();
    let activ = true;
    let ceas: ReturnType<typeof setTimeout> | undefined;
    const aplica = (s: StareaZilei) => {
      setStare(s);
      if (s.azi === null) {
        // profesorul a căzut și rândul s-a șters: omul poate trimite din nou
        setEroare(TEXTE.T35);
        setReplica(replicaTrimisa.current);
      }
    };
    const pas = async () => {
      if (!activ) return;
      const ultima = Date.now() - (primaIntrebare.current ?? Date.now()) >= CAT_ASTEPTAM_RASPUNS_MS;
      try {
        const s = await getReplicaZilei(projectId);
        if (!activ) return;
        if (!s.azi?.inLucru) {
          aplica(s);
          return;
        }
        if (ultima) {
          setEroare(TEXTE.T30);
          return;
        }
      } catch {
        if (!activ) return;
        if (ultima) {
          setEroare(TEXTE.T30);
          return;
        }
        // o eroare la întrebare se ignoră până la pasul următor
      }
      ceas = setTimeout(pas, PAS_RASPUNS_MS);
    };
    ceas = setTimeout(pas, PAS_RASPUNS_MS);
    return () => {
      activ = false;
      if (ceas !== undefined) clearTimeout(ceas);
    };
  }, [projectId, inLucru]);

  useEffect(() => {
    let activ = true;
    setStare(null);
    setEroareIncarcare(null);
    getReplicaZilei(projectId)
      .then((s) => activ && setStare(s))
      .catch((err: unknown) => activ && setEroareIncarcare(mesajLaIncarcare(err)));
    return () => {
      activ = false;
    };
  }, [projectId]);

  const { isListening, isTranscribing, startListening, stopListening } = useVoiceToText({
    // Ca la Exersează (plicul 176): microfonul doar scrie în casetă; omul apasă butonul.
    onTranscript: (text) => setReplica((prev) => (prev ? `${prev} ${text}` : text)),
    // Ca la Exersează (plicul 170): mesajele microfonului sunt deja scrise pentru om.
    onError: (err, pentruOm) => setEroare(pentruOm ? err : `Eroare voce: ${err}`),
  });

  const handleTrimite = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!stare?.situatie || !replica.trim() || trimite) return;
    setTrimite(true);
    setEroare(null);
    try {
      setStare(await trimiteReplicaZilei(projectId, stare.situatie.id, replica));
    } catch (err) {
      if (err instanceof PracticeError && err.code === "replica_zilei_facuta") {
        try {
          setStare(await getReplicaZilei(projectId));
        } catch {
          setEroare(TEXTE.T35);
        }
      } else {
        setEroare(mesajLaTrimitere(err));
      }
    } finally {
      setTrimite(false);
    }
  };

  const inapoi = (
    <a href={exerseazaHref} className="text-sm font-medium text-primary underline-offset-4 hover:underline">
      {TEXTE.T28}
    </a>
  );

  let corp: React.ReactNode;
  if (eroareIncarcare) {
    corp = <p className="text-sm text-foreground">{eroareIncarcare}</p>;
  } else if (!stare) {
    corp = <p className="text-sm text-muted-foreground">{TEXTE.T29}</p>;
  } else if (!stare.situatie) {
    corp = <p className="text-sm text-foreground">{TEXTE.T26}</p>;
  } else {
    const { situatie, azi } = stare;
    const blocat = trimite || isListening || isTranscribing;
    corp = (
      <>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base font-semibold">{TEXTE.T9}</CardTitle>
            <p className="text-xs text-muted-foreground">
              {stare.dinObiectivulMeu ? TEXTE.T10(situatie.obiectivTitlu) : TEXTE.T11(situatie.obiectivTitlu)}
            </p>
          </CardHeader>
          <CardContent className="text-sm text-foreground">
            <p>{textulSituatiei(situatie.text)}</p>
          </CardContent>
        </Card>

        {azi?.inLucru ? (
          <Card>
            <CardContent className="flex flex-col gap-4 pt-6 text-sm text-foreground">
              <div className="flex flex-col gap-1">
                <h2 className="font-semibold">{TEXTE.T22}</h2>
                <p className="whitespace-pre-wrap">{azi.replica}</p>
              </div>
              <p role="status" className="text-sm text-muted-foreground">
                {TEXTE.T19}
              </p>
            </CardContent>
          </Card>
        ) : azi ? (
          <Card>
            <CardContent className="flex flex-col gap-4 pt-6 text-sm text-foreground">
              {azi.nota !== null ? <p className="text-base font-semibold">{TEXTE.T21(formateazaNota(azi.nota))}</p> : null}
              <div className="flex flex-col gap-1">
                <h2 className="font-semibold">{TEXTE.T20}</h2>
                <p data-testid="raspunsul-lui-cody" className="whitespace-pre-wrap">
                  {azi.raspuns}
                </p>
              </div>
              <div className="flex flex-col gap-1">
                <h2 className="font-semibold">{TEXTE.T22}</h2>
                <p className="whitespace-pre-wrap">{azi.replica}</p>
              </div>
              <p className="text-muted-foreground">{TEXTE.T23}</p>
            </CardContent>
          </Card>
        ) : (
          <form onSubmit={handleTrimite} className="flex flex-col gap-2">
            <label htmlFor="replica-zilei-caseta" className="text-sm font-medium text-foreground">
              {TEXTE.T12}
            </label>
            <div className="relative">
              <Textarea
                id="replica-zilei-caseta"
                value={replica}
                onChange={(e) => setReplica(e.target.value)}
                placeholder={isListening ? TEXTE.T14 : isTranscribing ? TEXTE.T15 : TEXTE.T13}
                rows={4}
                className="w-full resize-none pr-12 text-base"
                disabled={blocat}
              />
              <Button
                type="button"
                variant={isListening ? "destructive" : "outline"}
                size="sm"
                className={`absolute right-2 bottom-2 h-11 w-11 rounded-full p-0 ${isListening ? "animate-pulse" : ""}`}
                disabled={trimite || isTranscribing}
                onClick={isListening ? stopListening : startListening}
                title={isListening ? TEXTE.T17 : TEXTE.T16}
                aria-label={isListening ? TEXTE.T17 : TEXTE.T16}
              >
                {isTranscribing ? (
                  <Loader2Icon className="size-4 animate-spin text-muted-foreground" />
                ) : isListening ? (
                  <MicOffIcon className="size-4 text-destructive-foreground" />
                ) : (
                  <MicIcon className="size-4 text-foreground" />
                )}
              </Button>
            </div>
            <Button type="submit" className="w-full min-h-11" disabled={!replica.trim() || blocat}>
              {TEXTE.T18}
            </Button>
            {trimite ? <p className="text-sm text-muted-foreground">{TEXTE.T19}</p> : null}
          </form>
        )}

        {stare.serie >= 1 ? (
          <div className="flex flex-col gap-1 text-sm">
            <p className="font-semibold text-foreground">{TEXTE.T24(stare.serie)}</p>
            <p className="text-muted-foreground">{TEXTE.T25}</p>
          </div>
        ) : null}
      </>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-col gap-4">
      {corp}
      {eroare ? (
        <p role="alert" className="text-sm text-destructive">
          {eroare}
        </p>
      ) : null}
      <div>{inapoi}</div>
    </div>
  );
}
