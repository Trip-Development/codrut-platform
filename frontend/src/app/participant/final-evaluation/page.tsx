"use client";

import Link from "next/link";
import React, { useState, useEffect } from "react";

import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";

type Question = {
  id: string;
  competency: string;
  text: string;
  options: { text: string; score: number }[];
};

const finalQuestions: Question[] = [
  {
    id: "listening_out",
    competency: "Ascultare Activă",
    text: "Un membru al echipei spune că are o idee pentru optimizarea procesului de suport, dar se teme că va fi respinsă de conducere. Cum acționezi?",
    options: [
      { text: "Îi ceri să scrie o propunere formală și o trimiți tu mai departe când ai timp.", score: 50 },
      { text: "Îl încurajezi să o prezinte direct în ședință și să își asume eventualele critici.", score: 65 },
      { text: "Îl asculți pentru a înțelege conceptul, îi validezi inițiativa și stabiliți împreună un plan de a structura propunerea axată pe beneficiile de business înainte de prezentare.", score: 100 }
    ]
  },
  {
    id: "feedback_out",
    competency: "Feedback Constructiv",
    text: "Cum livrezi un feedback negativ referitor la calitatea codului scris de un programator senior, fără a-i demotiva experiența?",
    options: [
      { text: "„Codul tău are multe bug-uri la ultimul modul. Trebuie să fii mai atent, doar ești senior.”", score: 30 },
      { text: "„Am observat că la ultimul modul au apărut 4 erori de validare în producție. Consecința este că echipa de QA a lucrat suplimentar. Haide să ne uităm pe cauze și să vedem cum prevenim asta pe viitor.”", score: 100 },
      { text: "Lasei lucrurile așa pentru că este senior și probabil își va da singur seama de greșeală la următoarea revizie.", score: 45 }
    ]
  },
  {
    id: "assertiveness_out",
    competency: "Comunicare Asertivă",
    text: "Directorul diviziei îți cere să lucrezi în weekend pentru o urgență minoră care ar putea aștepta până luni, dar tu ai programat un eveniment important în familie. Cum răspunzi?",
    options: [
      { text: "Accepti politicos, anulezi evenimentul, dar acumulezi frustrare internă.", score: 40 },
      { text: "Refuzi direct și îi spui că viața privată este mai importantă decât urgențele lui.", score: 30 },
      { text: "Îi explici că ai un angajament personal critic în acest weekend și îi propui să preiei rezolvarea luni la prima oră, sau să delegați către cineva de gardă dacă este critic.", score: 100 }
    ]
  }
];

export default function ParticipantFinalEvaluationPage() {
  const [completed, setCompleted] = useState<boolean | null>(null);
  const [step, setStep] = useState<"welcome" | "quiz" | "result">("welcome");
  const [currentIdx, setCurrentIdx] = useState<number>(0);

  const [baselineAvg, setBaselineAvg] = useState<number>(70);

  useEffect(() => {
    const isCompleted = localStorage.getItem("codrut_final_evaluation_completed") === "true";
    setCompleted(isCompleted);

    const storedScores = localStorage.getItem("codrut_participant_scores");
    if (storedScores) {
      try {
        const parsed = JSON.parse(storedScores);
        const avg = Math.round(
          ((parsed.listening || 70) + (parsed.feedback || 70) + (parsed.assertiveness || 70)) / 3
        );
        setBaselineAvg(avg);
      } catch (e) {
        console.error(e);
      }
    }
  }, []);

  const handleSelectOption = () => {


    if (currentIdx < finalQuestions.length - 1) {
      setCurrentIdx(prev => prev + 1);
    } else {
      // Complete evaluation
      localStorage.setItem("codrut_final_evaluation_completed", "true");

      // Update scores to 100% on completion
      const storedScores = localStorage.getItem("codrut_participant_scores");
      if (storedScores) {
        try {
          const parsed = JSON.parse(storedScores);
          parsed.listening = 95;
          parsed.feedback = 100;
          parsed.assertiveness = 95;
          localStorage.setItem("codrut_participant_scores", JSON.stringify(parsed));
        } catch (e) {
          console.error(e);
        }
      }

      // Add XP
      const storedXp = localStorage.getItem("codrut_participant_xp");
      const currentXp = storedXp ? parseInt(storedXp, 10) : 150;
      localStorage.setItem("codrut_participant_xp", (currentXp + 200).toString());

      setCompleted(true);
      setStep("result");
    }
  };

  const handleReset = () => {
    localStorage.setItem("codrut_final_evaluation_completed", "false");
    setCompleted(false);
    setStep("welcome");
    setCurrentIdx(0);
  };

  return (
    <AppShell
      audience="participant"
      eyebrow="Evaluare Finală"
      title="Măsurarea Impactului (Test OUT)"
      description="Evaluarea finală compară cunoștințele și tendințele tale actuale cu cele de la începutul programului."
      navItems={participantNavItems}
      activeHref="/participant/final-evaluation"
    >
      {completed && step !== "result" ? (
        <section className="rounded-3xl border border-[var(--border)] bg-surface p-8 shadow-sm text-center max-w-2xl mx-auto animate-fade-up">
          <div className="w-16 h-16 bg-success/15 rounded-full flex items-center justify-center text-success-ink mx-auto mb-6">
            <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z" />
            </svg>
          </div>
          <h2 className="font-display text-2xl font-bold text-foreground">Evaluarea Finală a fost finalizată!</h2>
          <p className="text-sm text-foreground/62 leading-6 mt-3">
            Ai completat cu succes toate etapele din Test OUT. Raportul tău de evoluție a fost consolidat și transmis către Andrei Văcaru.
          </p>

          <div className="my-6 rounded-2xl bg-surface-muted border border-[var(--border)] p-5 max-w-md mx-auto">
            <h4 className="text-xs font-bold uppercase text-foreground/45 mb-3">Evoluție scor mediu</h4>
            <div className="flex items-center justify-center gap-6">
              <div>
                <span className="text-xs font-semibold text-foreground/55">Test IN (Inițial)</span>
                <span className="block text-2xl font-bold text-foreground/50 mt-1">{baselineAvg}%</span>
              </div>
              <span className="text-xl text-burgundy">➔</span>
              <div>
                <span className="text-xs font-semibold text-burgundy">Test OUT (Final)</span>
                <span className="block text-3xl font-extrabold text-burgundy mt-1">96%</span>
              </div>
            </div>
            <p className="text-xs text-success-ink font-bold mt-4">▲ Creștere de competență: +{96 - baselineAvg}%</p>
          </div>

          <div className="mt-8 pt-6 border-t border-[var(--border)] flex justify-between items-center text-xs text-foreground/45">
            <span>Demo finalizat</span>
            <button onClick={handleReset} className="hover:text-burgundy underline">
              Resetează Evaluarea Finală (Pentru Demo)
            </button>
          </div>
        </section>
      ) : (
        <div className="max-w-2xl mx-auto">
          {step === "welcome" && (
            <section className="rounded-3xl border border-[var(--border)] bg-surface p-8 shadow-md animate-fade-up">
              <div className="flex items-center gap-4 mb-6">
                <div className="w-12 h-12 bg-burgundy/10 dark:bg-burgundy/20 rounded-2xl flex items-center justify-center text-burgundy shrink-0">
                  <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2zm9-13.5V9" />
                  </svg>
                </div>
                <div>
                  <span className="text-xs font-bold uppercase tracking-wider text-burgundy">Ultimul Pas</span>
                  <h2 className="font-display text-2xl font-bold text-foreground">Pregătit pentru evaluarea finală?</h2>
                </div>
              </div>

              <div className="space-y-4 text-sm leading-6 text-foreground/75">
                <p>
                  Ai parcurs modulele de coaching și antrenament practic. Trainerul a activat acum evaluarea de ieșire (Test OUT).
                </p>
                <p>
                  Scenariile sunt similare cu cele inițiale, adaptate pentru a evidenția modul în care aplici ascultarea activă, feedback-ul constructiv și asertivitatea în munca ta.
                </p>
                <p className="text-xs text-foreground/55">
                  Completarea durează în jur de 5 minute. La final, vei obține raportul tău de performanță și un bonus de <strong>200 XP</strong>!
                </p>
              </div>

              <div className="mt-8 border-t border-[var(--border)] pt-6">
                <button
                  onClick={() => setStep("quiz")}
                  className="tap-soft w-full rounded-2xl bg-burgundy py-4 text-center text-base font-bold text-white shadow-brand hover:bg-burgundy-700"
                >
                  Începe Test OUT
                </button>
              </div>
            </section>
          )}

          {step === "quiz" && (
            <section className="rounded-3xl border border-[var(--border)] bg-surface p-8 shadow-md animate-fade-up">
              <div className="flex items-center justify-between border-b border-[var(--border)] pb-4 mb-6">
                <div>
                  <span className="text-xs font-bold uppercase tracking-wider text-burgundy">Test OUT</span>
                  <h2 className="text-lg font-bold text-foreground mt-0.5">Scenariul {currentIdx + 1} din {finalQuestions.length}</h2>
                </div>
                <span className="text-xs font-bold text-foreground/55">{Math.round((currentIdx / finalQuestions.length) * 100)}%</span>
              </div>

              <div className="mb-6">
                <div className="flex gap-3 items-start">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-burgundy-50 dark:bg-burgundy/10 text-xs font-black text-burgundy">
                    ?
                  </span>
                  <p className="text-base font-semibold leading-7 text-foreground">{finalQuestions[currentIdx].text}</p>
                </div>
              </div>

              <div className="space-y-3">
                {finalQuestions[currentIdx].options.map((opt, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSelectOption()}
                    className="tap-soft w-full text-left rounded-2xl border border-[var(--border)] bg-surface px-5 py-4 text-sm leading-6 text-foreground/80 hover:border-burgundy/45 hover:bg-burgundy-50/10 hover:text-burgundy"
                  >
                    {opt.text}
                  </button>
                ))}
              </div>
            </section>
          )}

          {step === "result" && (
            <section className="rounded-3xl border border-[var(--border)] bg-surface p-8 shadow-md text-center animate-fade-up">
              <div className="w-16 h-16 bg-success/15 rounded-full flex items-center justify-center text-success-ink mx-auto mb-6">
                <svg className="w-8 h-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 14l9-5-9-5-9 5 9 5zm0 0l6.16-3.422a12.083 12.083 0 01.665 6.479A11.952 11.952 0 0012 20.055a11.952 11.952 0 00-6.824-2.998 12.078 12.078 0 01.665-6.479L12 14zm-4 6v-7.5l4-2.222" />
                </svg>
              </div>
              <h2 className="font-display text-2xl font-bold text-foreground">Felicitări! Test OUT finalizat!</h2>
              <p className="text-sm text-foreground/62 leading-6 mt-3">
                Ai absolvit cu succes programul de coaching. Performanțele tale au fost agregate și sunt gata pentru evaluare.
              </p>

              <div className="my-6 rounded-2xl bg-surface-muted border border-[var(--border)] p-5 max-w-md mx-auto">
                <div className="flex items-center justify-center gap-6">
                  <div>
                    <span className="text-xs font-semibold text-foreground/55">Test IN (Inițial)</span>
                    <span className="block text-xl font-bold text-foreground/50 mt-1">{baselineAvg}%</span>
                  </div>
                  <span className="text-xl text-burgundy">➔</span>
                  <div>
                    <span className="text-xs font-semibold text-burgundy">Test OUT (Final)</span>
                    <span className="block text-2xl font-extrabold text-burgundy mt-1">96%</span>
                  </div>
                </div>
                <p className="text-xs text-success-ink font-bold mt-3">Creștere medie: +{96 - baselineAvg}%</p>
              </div>

              <p className="text-xs text-foreground/55 mb-6">
                Ți-au fost adăugate <strong>200 puncte XP</strong> în cont. Mulțumim pentru implicare!
              </p>

              <Link
                href="/participant"
                className="tap-soft block w-full rounded-2xl bg-burgundy py-4 text-center text-base font-bold text-white shadow-brand hover:bg-burgundy-700"
              >
                Mergi la ecranul principal
              </Link>
            </section>
          )}
        </div>
      )}
    </AppShell>
  );
}
