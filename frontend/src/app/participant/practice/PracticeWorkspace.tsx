"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  PracticeError,
  startPracticeSession,
  submitPracticeTurn,
  endPracticeSession,
  type PracticeSession,
  type PracticeTurn,
  type SessionKind,
} from "@/api/practice";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { MicIcon, MicOffIcon, Loader2Icon } from "lucide-react";
import { useVoiceToText } from "@/hooks/useVoiceToText";

const PRACTICE_OPTIONS: {
  kind: SessionKind;
  title: string;
  subtitle: string;
  description: string;
  disabled?: boolean;
}[] = [
  {
    kind: "roleplay",
    title: "Role-Play",
    subtitle: "Simulare de conversație",
    description: "Exersează o discuție dificilă într-un rol concret cu un interlocutor provocator.",
  },
  {
    kind: "knowledge",
    title: "Verificăm cât ai reținut",
    subtitle: "Verificare cunoștințe",
    description: "Răspunde la întrebări practice despre concepte, tehnici și tipare de comunicare.",
  },
  {
    kind: "coaching",
    title: "Facem strategia",
    subtitle: "Coaching pe situație reală",
    description: "Analizăm o situație reală din echipa ta și pregătim abordarea optimă.",
  },
  {
    kind: "research",
    title: "Cercetare",
    subtitle: "Explorare ghidată",
    description: "Explorare aprofundată a materialelor de curs (în dezvoltare).",
    disabled: true,
  },
];

/**
 * Ce scrie pe ecran cand serverul refuza pornirea unei sesiuni.
 *
 * Plafonul zilnic nu e cod stricat, e o setare — dar pana la plicul 35 omul apasa si
 * primea acelasi text generic, deci parea ca aplicatia s-a blocat. Acum spune cate
 * sesiuni are pe zi, cate a facut, si ca numaratoarea se reia maine.
 */
function mesajDeRefuz(err: unknown): string {
  if (err instanceof PracticeError && err.code === "practice_daily_limit") {
    const peZi = Number(err.details.max_sessions_per_day);
    const facute = Number(err.details.sessions_today);
    const cate = Number.isFinite(peZi)
      ? `Ai ${peZi} ${peZi === 1 ? "sesiune" : "sesiuni"} pe zi pe acest program`
      : "Ai atins numărul de sesiuni pe zi al acestui program";
    const consumate = Number.isFinite(facute) ? `, iar azi ai făcut ${facute}` : "";
    return (
      `Ai ajuns la limita de sesiuni pe ziua de azi. ${cate}${consumate}. ` +
      "Numărătoarea se reia mâine. Dacă ai nevoie de mai multe, cere-i trainerului " +
      "să ridice limita din fila Setări a proiectului."
    );
  }
  if (err instanceof Error) return err.message;
  return "Nu am putut porni sesiunea de practică";
}

const FIXED_OPENINGS = [
  {
    id: "1",
    label: "1. Colegul care întârzie",
    text: "Am un coleg care întârzie de trei luni cu partea lui din proiect. De fiecare dată are un motiv. Eu îmi refac planurile în jurul lui și nu i-am spus niciodată nimic direct. Nu vreau să îl pun la zid.",
  },
  {
    id: "2",
    label: "2. Feedbackul vag",
    text: "Vreau să îi spun unuia din echipă să fie mai implicat. Am tot amânat. Cum îi zic fără să îl demotivez?",
  },
  {
    id: "3",
    label: "3. Victima organizațională",
    text: "La noi în fabrică nu merge cu discuții din astea. Oamenii sunt obișnuiți altfel. Am încercat, nu se poate.",
  },
  {
    id: "4",
    label: "4. Mesaj fără context",
    text: "Sunt varză azi.",
  },
  {
    id: "5",
    label: "5. Exercițiu în rol greu",
    text: "Hai să exersăm. Eu sunt șeful care ți-a cerut raportul de vineri și tu ești omul care nu l-a făcut. Începe tu.",
  },
];

export function PracticeWorkspace({
  projectId,
}: {
  projectId?: string | null;
}) {
  const [selectedKind, setSelectedKind] = useState<SessionKind>("roleplay");
  const [session, setSession] = useState<PracticeSession | null>(null);
  const [turns, setTurns] = useState<PracticeTurn[]>([]);
  const [inputText, setInputText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isEnding, setIsEnding] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  // „Inapoi" duce la alegerea modului FARA sa inchida sesiunea. Sesiunea ramane in
  // stare si pe server; omul se poate intoarce la ea din bannerul de sus.
  const [arataAlegerea, setArataAlegerea] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [turns, isLoading]);

  const handleStartSession = async (initialText?: string) => {
    if (!projectId) {
      setErrorMsg("Nu a fost selectat niciun proiect activ.");
      return;
    }
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const newSession = await startPracticeSession({
        projectId,
        kind: selectedKind,
      });
      setSession(newSession);
      setTurns([]);

      if (initialText && initialText.trim()) {
        const turnRes = await submitPracticeTurn(newSession.id, initialText.trim());
        const newTurns: PracticeTurn[] = [turnRes.participantTurn];
        if (turnRes.actorTurn) {
          newTurns.push(turnRes.actorTurn);
        }
        setTurns(newTurns);
        setSession((prev) =>
          prev
            ? {
                ...prev,
                state: turnRes.sessionState,
                turnCount: prev.turnCount + 1,
              }
            : null
        );
      }
    } catch (err: unknown) {
      setErrorMsg(mesajDeRefuz(err));
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!session || !inputText.trim() || isLoading || session.state !== "open") {
      return;
    }

    const textToSend = inputText.trim();
    setInputText("");
    setIsLoading(true);
    setErrorMsg(null);

    try {
      const turnRes = await submitPracticeTurn(session.id, textToSend);
      setTurns((prev) => {
        const next = [...prev, turnRes.participantTurn];
        if (turnRes.actorTurn) {
          next.push(turnRes.actorTurn);
        }
        return next;
      });
      setSession((prev) =>
        prev
          ? {
              ...prev,
              state: turnRes.sessionState,
              turnCount: prev.turnCount + 1,
            }
          : null
      );
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Eroare la trimiterea mesajului");
      setInputText(textToSend); // restabilim textul pentru retrimitere
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const [sessionSummary, setSessionSummary] = useState<string | null>(null);

  const handleEndSession = async () => {
    if (!session || isEnding) return;
    setIsEnding(true);
    setErrorMsg(null);
    try {
      const res = await endPracticeSession(session.id, {
        note: "Încheiat manual de participant",
      });
      setSession(res.session);
      setSessionSummary(res.summary);
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Eroare la încheierea sesiunii");
    } finally {
      setIsEnding(false);
    }
  };

  const handleReset = () => {
    setSession(null);
    setTurns([]);
    setInputText("");
    setErrorMsg(null);
    setSessionSummary(null);
    setArataAlegerea(false);
  };

  /** Inapoi la alegerea modului, cu sesiunea deschisa pastrata intreaga. */
  const handleInapoiLaAlegere = () => {
    setErrorMsg(null);
    setArataAlegerea(true);
  };

  /** Inapoi in sesiunea care a ramas deschisa. */
  const handleInapoiInSesiune = () => {
    setErrorMsg(null);
    setArataAlegerea(false);
  };

  const handleAutoSubmitVoice = async (textToSend: string) => {
    if (!session || !textToSend.trim() || isLoading || session.state !== "open") {
      setInputText((prev) => (prev ? `${prev} ${textToSend}` : textToSend));
      return;
    }

    setIsLoading(true);
    setErrorMsg(null);

    try {
      const turnRes = await submitPracticeTurn(session.id, textToSend.trim());
      setTurns((prev) => {
        const next = [...prev, turnRes.participantTurn];
        if (turnRes.actorTurn) {
          next.push(turnRes.actorTurn);
        }
        return next;
      });
      setSession((prev) =>
        prev
          ? {
              ...prev,
              state: turnRes.sessionState,
              turnCount: prev.turnCount + 1,
            }
          : null
      );
    } catch (err: unknown) {
      setErrorMsg(err instanceof Error ? err.message : "Eroare la trimiterea mesajului");
      setInputText(textToSend);
    } finally {
      setIsLoading(false);
    }
  };

  const {
    isListening,
    isTranscribing,
    error: voiceError,
    startListening,
    stopListening,
  } = useVoiceToText({
    onTranscript: (transcribedText) => {
      setInputText((prev) => (prev ? `${prev} ${transcribedText}` : transcribedText));
    },
    onAutoSubmit: (transcribedText) => {
      handleAutoSubmitVoice(transcribedText);
    },
    onError: (err) => {
      setErrorMsg(`Eroare voce: ${err}`);
    },
  });

  // Ecran 1: Selecția modului și pornirea sesiunii
  if (!session || arataAlegerea) {
    const sesiuneDeschisaPusaDeoparte = session && session.state === "open";
    return (
      <div className="flex flex-col gap-6 py-4 max-w-4xl mx-auto w-full">
        {sesiuneDeschisaPusaDeoparte ? (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-primary/30 bg-primary/5 p-4">
            <div>
              <p className="text-sm font-semibold text-foreground">
                Ai o sesiune deschisă.
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Nu s-a pierdut nimic. Te poți întoarce la ea oricând.
              </p>
            </div>
            <Button size="sm" onClick={handleInapoiInSesiune}>
              Întoarce-te la sesiune
            </Button>
          </div>
        ) : null}

        <div>
          <h2 className="text-xl font-heading font-semibold text-foreground">
            Alege modul de antrenament
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Selectează tipul de exercițiu pe care vrei să îl lucrezi astăzi cu Cody.
          </p>
        </div>

        {errorMsg && (
          <div className="p-3 text-sm rounded-md bg-destructive/10 text-destructive border border-destructive/20">
            {errorMsg}
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {PRACTICE_OPTIONS.map((opt) => {
            const isSelected = selectedKind === opt.kind;
            return (
              <Card
                key={opt.kind}
                className={`cursor-pointer transition-all border-2 ${
                  opt.disabled
                    ? "opacity-50 cursor-not-allowed bg-muted/40 border-border"
                    : isSelected
                    ? "border-primary bg-primary/5 shadow-sm"
                    : "border-border hover:border-primary/50 bg-surface"
                }`}
                onClick={() => {
                  if (!opt.disabled) setSelectedKind(opt.kind);
                }}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-base font-semibold">
                      {opt.title}
                    </CardTitle>
                    {opt.disabled ? (
                      <Badge variant="outline" className="text-xs">
                        În curând
                      </Badge>
                    ) : isSelected ? (
                      <Badge className="text-xs bg-primary text-primary-foreground">
                        Selectat
                      </Badge>
                    ) : null}
                  </div>
                  <CardDescription className="text-xs font-medium text-muted-foreground">
                    {opt.subtitle}
                  </CardDescription>
                </CardHeader>
                <CardContent className="text-xs text-muted-foreground">
                  {opt.description}
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Deschideri rapide recomandate */}
        <div className="mt-2 flex flex-col gap-3">
          <h3 className="text-sm font-semibold text-foreground">
            Sau alege o situație de deschidere directă:
          </h3>
          <div className="flex flex-wrap gap-2">
            {FIXED_OPENINGS.map((op) => (
              <Button
                key={op.id}
                variant="outline"
                size="sm"
                className="text-xs h-8 text-left"
                disabled={isLoading}
                onClick={() => handleStartSession(op.text)}
              >
                {op.label}
              </Button>
            ))}
          </div>
        </div>

        <div className="flex justify-end mt-4">
          <Button
            size="default"
            className="px-6"
            disabled={isLoading || !projectId}
            onClick={() => handleStartSession()}
          >
            {isLoading ? "Se inițializează..." : "Începe conversația"}
          </Button>
        </div>
      </div>
    );
  }

  // Ecran 2: Conversația activă
  const activeOption = PRACTICE_OPTIONS.find((o) => o.kind === session.kind);

  return (
    <div className="flex flex-col gap-4 max-w-4xl mx-auto w-full h-[calc(100vh-14rem)] min-h-[500px]">
      {/* Header sesiune */}
      <div className="flex items-center justify-between border-b pb-3 pt-1">
        <div className="flex items-center gap-2">
          <Badge variant="outline" className="text-xs font-semibold px-2 py-0.5">
            {activeOption?.title || session.kind}
          </Badge>
          <span className="text-xs text-muted-foreground">
            • Replica {session.turnCount} / 10
          </span>
          {session.state === "closed" && (
            <Badge variant="destructive" className="text-xs">
              Sesiune încheiată
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          {session.state === "open" ? (
            <>
              {/* Iesirea care NU inchide nimic. Pana la plicul 34 singura cale
                  afara dintr-o sesiune pornita era „Incheie sesiunea". */}
              <Button
                variant="ghost"
                size="sm"
                className="text-xs h-8"
                onClick={handleInapoiLaAlegere}
              >
                ← Înapoi
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="text-xs h-8 text-destructive hover:bg-destructive/10"
                disabled={isEnding || isLoading}
                onClick={handleEndSession}
              >
                {isEnding ? "Se încheie..." : "Încheie sesiunea"}
              </Button>
            </>
          ) : (
            <>
              {/* Drumul inapoi, sus, unde se vede fara sa derulezi. Pana la plicul 36
                  statea doar in caseta de jos, dupa toata zona de conversatie. */}
              <Button
                variant="default"
                size="sm"
                className="text-xs h-8"
                onClick={handleReset}
              >
                ← Înapoi la alegerea modului
              </Button>
            </>
          )}
        </div>
      </div>

      {errorMsg && (
        <div className="p-2 text-xs rounded bg-destructive/10 text-destructive border border-destructive/20">
          {errorMsg}
        </div>
      )}

      {/* Container mesaje */}
      <div className="flex-1 overflow-y-auto px-1 py-2 flex flex-col gap-4">
        {turns.length === 0 && !isLoading && (
          <div className="text-center text-muted-foreground my-auto p-6 text-sm">
            {/* Textul asta se arata si cand sesiunea era inchisa, deci ecranul se
                contrazicea singur: sus scria „Sesiune încheiată", iar aici „Sesiunea
                este deschisă". */}
            {session.state === "open" ? (
              <>
                <p className="font-medium text-foreground">Sesiunea este deschisă.</p>
                <p className="text-xs mt-1">
                  Scrie un prim mesaj sau alege o situație concretă pentru a începe dialogul cu Cody.
                </p>
              </>
            ) : (
              <>
                <p className="font-medium text-foreground">
                  Sesiunea s-a încheiat fără nicio replică.
                </p>
                <p className="text-xs mt-1">
                  Nu s-a schimbat nimic. Începe alta când vrei, din butonul de sus.
                </p>
              </>
            )}
          </div>
        )}

        {turns.map((turn) => {
          const isParticipant = turn.role === "participant";
          return (
            <div
              key={turn.id || turn.ordinal}
              className={`flex flex-col ${
                isParticipant ? "items-end" : "items-start"
              }`}
            >
              <span className="text-[11px] font-medium text-muted-foreground mb-1 px-1">
                {isParticipant ? "Tu" : "Cody"}
              </span>
              <div
                className={`max-w-[85%] rounded-lg px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap ${
                  isParticipant
                    ? "bg-primary text-primary-foreground rounded-br-none shadow-sm"
                    : "bg-muted/70 text-foreground border rounded-bl-none shadow-none"
                }`}
              >
                {turn.text}
              </div>
            </div>
          );
        })}

        {isLoading && (
          <div className="flex flex-col items-start">
            <span className="text-[11px] font-medium text-muted-foreground mb-1 px-1">
              Cody
            </span>
            <div className="bg-muted/70 text-muted-foreground border rounded-lg rounded-bl-none px-4 py-2.5 text-xs flex items-center gap-2">
              <span className="inline-block w-2 h-2 rounded-full bg-primary animate-pulse" />
              <span>Cody scrie...</span>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Zona de input / sumar */}
      {session.state === "open" ? (
        <form
          onSubmit={handleSendMessage}
          className="flex flex-col gap-2 pt-2 border-t bg-background"
        >
          <div className="relative flex items-end gap-2">
            <Textarea
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={isListening ? "Ascult... vorbește liber..." : isTranscribing ? "Se transcrie mesajul audio..." : "Scrie un mesaj... (Enter pentru a trimite, Shift+Enter pentru rând nou)"}
              rows={2}
              className="resize-none pr-28 text-sm focus-visible:ring-1"
              disabled={isLoading || isListening || isTranscribing}
            />
            <div className="absolute right-2 bottom-2 flex items-center gap-1.5">
              <Button
                type="button"
                variant={isListening ? "destructive" : "outline"}
                size="sm"
                className={`h-8 w-8 p-0 rounded-full ${
                  isListening ? "animate-pulse" : ""
                }`}
                disabled={isLoading || isTranscribing}
                onClick={isListening ? stopListening : startListening}
                title={isListening ? "Oprește înregistrarea" : "Vorbește (microfon)"}
              >
                {isTranscribing ? (
                  <Loader2Icon className="size-4 animate-spin text-muted-foreground" />
                ) : isListening ? (
                  <MicOffIcon className="size-4 text-destructive-foreground" />
                ) : (
                  <MicIcon className="size-4 text-foreground" />
                )}
              </Button>

              <Button
                type="submit"
                size="sm"
                className="h-8 px-3 text-xs"
                disabled={!inputText.trim() || isLoading || isListening || isTranscribing}
              >
                Trimite
              </Button>
            </div>
          </div>
        </form>
      ) : (
        <div className="space-y-4 pt-3 border-t">
          {/* Drumul inapoi, primul lucru de pe ecran. Pana la plicul 34 era un link
              in subsolul unei casete, sub sinteza, si omul ramanea in transcript. */}
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-surface p-4">
            <div>
              <p className="text-sm font-semibold text-foreground">
                Sesiunea s-a încheiat.
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                Sinteza rămâne mai jos. Poți începe alta oricând.
              </p>
            </div>
            <Button size="sm" onClick={handleReset}>
              ← Înapoi la alegerea modului
            </Button>
          </div>

          {sessionSummary ? (
            <div className="p-4 rounded-lg border border-primary/20 bg-primary/5 text-sm space-y-3">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-foreground flex items-center gap-1.5">
                  <span>📊</span> Sinteza și Evaluarea Sesiunii
                </span>
                <Badge variant="outline" className="text-xs bg-surface">
                  Finalizat
                </Badge>
              </div>
              <div className="whitespace-pre-wrap leading-relaxed text-foreground font-sans text-xs bg-surface p-3 rounded border">
                {sessionSummary}
              </div>
            </div>
          ) : null}

          <div className="p-3 text-center text-xs text-muted-foreground bg-muted/20 rounded">
            Această sesiune de practică a fost încheiată.{" "}
            <button
              onClick={handleReset}
              className="text-primary underline font-medium hover:opacity-80 ml-1"
            >
              Începe o sesiune nouă
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
