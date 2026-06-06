"use client";

import React, { useState, useEffect } from "react";

import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems } from "@/components/shell/nav";

type Message = {
  sender: "user" | "bot";
  text: string;
  time: string;
};

type ChatSession = {
  title: string;
  subtitle: string;
  description: string;
  icon: string;
  initialMessages: Message[];
  steps: {
    question: string;
    options: { label: string; text: string; botReply: string; score: number }[];
  }[];
};

const chatSessions: Record<string, ChatSession> = {
  "role-play": {
    title: "Simulare: Confruntare coleg tensionat",
    subtitle: "Exercițiu de Ascultare Activă",
    description: "Exersează gestionarea unei discuții cu un coleg care își exprimă frustrarea față de termenele limită.",
    icon: "role-play",
    initialMessages: [
      { sender: "bot", text: "Salut! Haide să începem simularea. Imaginează-ți că ești în birou și colegul tău Tudor intră tensionat, trântind dosarul pe masă și spunând:\n\n'Nu se mai poate! Proiectul Michelin este sub-dimensionat, echipa mea muncește peste program și nu vom livra la timp!'\n\nCare este prima ta reacție?", time: "Acum" }
    ],
    steps: [
      {
        question: "Alege răspunsul tău:",
        options: [
          {
            label: "Reacție defensivă",
            text: "Tudor, toți avem mult de lucru în perioada asta. Trebuie să ne organizăm mai bine și să livrăm ce am promis clientului.",
            botReply: "Tudor se crispează și mai tare: 'Da, sigur, organizarea e problema noastră! Nu mă asculți deloc.'\n\n⚠️ AI REACȚIONAT DEFENSIV. Într-o discuție tensionată, prima etapă este validarea emoției, nu rezolvarea sau apărarea. Haide să încercăm din nou. Cum reformulezi asertiv?",
            score: 20
          },
          {
            label: "Ascultare activă / Validare",
            text: "Aud că ești foarte presat și că te îngrijorează calitatea livrabilelor pentru Michelin. Simți că echipa este la limita resurselor. Spune-mi mai multe.",
            botReply: "Tudor își lasă umerii în jos, răsuflând ușurat: 'Exact! Oamenii sunt epuizați. Dacă ne mai cereți rapoarte zilnice suplimentare, vor ceda.'\n\n✅ EXCELENT. Ai de-tensionat atmosfera prin ascultare activă. Acum Tudor este deschis la cooperare. Cum continui pentru a găsi o soluție constructivă?",
            score: 100
          }
        ]
      },
      {
        question: "Cum continui discuția?",
        options: [
          {
            label: "Focus pe rezolvare comună",
            text: "Înțeleg. Haide să vedem ce activități administrative (cum sunt acele rapoarte zilnice) putem simplifica sau suspenda temporar, astfel încât să ne concentrăm pe livrarea Michelin. Ce propuneri ai?",
            botReply: "Tudor zâmbește ușor: 'Am putea face rapoartele săptămânale în loc de zilnice. Asta ar elibera 3 ore pe săptămână pentru fiecare om.'\n\nEXCELENT! Ai transformat o confruntare tensionată într-o sesiune de rezolvare de probleme. Sesiunea s-a încheiat cu succes! Ai câștigat +50 XP.",
            score: 100
          },
          {
            label: "Impuls administrativ",
            text: "Rapoartele zilnice sunt stabilite de Andrei și sunt obligatorii pentru monitorizare. Trebuie să găsim altă cale să facem față volumului.",
            botReply: "Tudor devine din nou distant: 'Înțeleg. Atunci nu am ce să mai zic.'\n\nDISCUȚIE BLOCATĂ. Ai prioritizat regulile administrative în detrimentul realității resurselor echipei. Sesiunea s-a încheiat. Ai obținut +20 XP.",
            score: 40
          }
        ]
      }
    ]
  },
  "quiz": {
    title: "Test rapid: Canale PCM & Distres",
    subtitle: "Evaluare cunoștințe PCM",
    description: "Verifică-ți înțelegerea conceptelor cheie din Process Communication Model.",
    icon: "quiz",
    initialMessages: [
      { sender: "bot", text: "Bine ai venit la testul rapid PCM! Am pregătit 2 întrebări pentru tine. Să începem!\n\nÎntrebarea 1: Care este canalul de comunicare potrivit pentru o persoană cu un tip de personalitate dominant 'Empatic' (Harmonizer)?", time: "Acum" }
    ],
    steps: [
      {
        question: "Alege varianta corectă:",
        options: [
          {
            label: "Canalul Directiv",
            text: "Canalul Directiv (comenzi scurte, instrucțiuni clare)",
            botReply: "Greșit. Canalul Directiv este potrivit pentru Promotor sau Rebel.\n\nÎntrebarea 2: Ce indică un comportament de distres de gradul 1 (Driver) precum 'Fii perfect' la o personalitate de tip Gânditor (Thinker)?",
            score: 0
          },
          {
            label: "Canalul Nutritiv",
            text: "Canalul Nutritiv (căldură sufletească, grijă, apreciere personală)",
            botReply: "Corect! Empaticii se conectează cel mai bine pe canalul nutritiv, având nevoie de apreciere ca persoană și validare emoțională.\n\nÎntrebarea 2: Ce indică un comportament de distres de gradul 1 (Driver) precum 'Fii perfect' la o personalitate de tip Gânditor (Thinker)?",
            score: 100
          }
        ]
      },
      {
        question: "Alege răspunsul pentru Întrebarea 2:",
        options: [
          {
            label: "Driver 'Fii perfect'",
            text: "O ușoară deviere spre supra-detaliere și tendința de a controla totul, cauzată de stres minor.",
            botReply: "Corect! Sub stres de gradul 1 (Driver), Gânditorii vor deveni excesiv de preocupați de detalii și ordine (Fii perfect), încercând să controleze situația.\n\nFelicitări! Ai finalizat testul rapid PCM. Ai obținut +50 XP!",
            score: 100
          },
          {
            label: "Distres profund",
            text: "O pierdere completă a capacității de analiză logică și izolare totală.",
            botReply: "Greșit. Aceasta corespunde mai degrabă distresului profund de gradul 2 sau 3.\n\nFelicitări! Ai finalizat testul rapid PCM. Ai obținut +20 XP!",
            score: 0
          }
        ]
      }
    ]
  }
};

export default function ParticipantChatPage() {
  const [activeMode, setActiveMode] = useState<"menu" | "role-play" | "quiz">("menu");
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentStepIdx, setCurrentStepIdx] = useState<number>(0);
  const [sessionCompleted, setSessionCompleted] = useState<boolean>(false);
  const [xpEarned, setXpEarned] = useState<number>(0);

  useEffect(() => {
    if (activeMode !== "menu") {
      const session = chatSessions[activeMode];
      setMessages(session.initialMessages);
      setCurrentStepIdx(0);
      setSessionCompleted(false);
      setXpEarned(0);
    }
  }, [activeMode]);

  const handleSelectOption = (option: { text: string; botReply: string; score: number }) => {
    // 1. Add user message
    const userTime = new Date().toLocaleTimeString("ro-RO", { hour: "2-digit", minute: "2-digit" });
    const userMsg: Message = { sender: "user", text: option.text, time: userTime };

    // 2. Add bot reply
    const botTime = new Date().toLocaleTimeString("ro-RO", { hour: "2-digit", minute: "2-digit" });
    const botMsg: Message = { sender: "bot", text: option.botReply, time: botTime };

    setMessages(prev => [...prev, userMsg, botMsg]);

    const session = chatSessions[activeMode];
    if (currentStepIdx < session.steps.length - 1) {
      setCurrentStepIdx(prev => prev + 1);
    } else {
      // End session
      setSessionCompleted(true);
      const earned = option.score === 100 ? 50 : 20;
      setXpEarned(earned);

      // Save to localStorage
      const storedXp = localStorage.getItem("codrut_participant_xp");
      const currentXp = storedXp ? parseInt(storedXp, 10) : 150;
      const newXp = currentXp + earned;
      localStorage.setItem("codrut_participant_xp", newXp.toString());

      const storedStreak = localStorage.getItem("codrut_participant_streak");
      const currentStreak = storedStreak ? parseInt(storedStreak, 10) : 1;
      localStorage.setItem("codrut_participant_streak", (currentStreak + 1).toString());
    }
  };

  const handleReturnToMenu = () => {
    setActiveMode("menu");
  };

  return (
    <AppShell
      audience="participant"
      eyebrow="Coaching Chat"
      title="Antrenament cu Codruț"
      description="Selectează o sesiune de interacțiune pentru a exersa scenarii practice de management și a acumula puncte XP."
      navItems={participantNavItems}
      activeHref="/participant/chat"
    >
      {activeMode === "menu" ? (
        <div className="grid gap-6 md:grid-cols-2 animate-fade-up">
          {Object.entries(chatSessions).map(([key, session]) => (
            <article
              key={key}
              className="rounded-3xl border border-[var(--border)] bg-surface p-6 shadow-sm flex flex-col justify-between"
            >
              <div>
                <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-burgundy-50 dark:bg-burgundy/10 text-burgundy mb-4 shrink-0">
                  {key === "role-play" ? (
                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M14.828 14.828a4 4 0 01-5.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                  ) : (
                    <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
                    </svg>
                  )}
                </span>
                <h2 className="font-display text-xl font-bold text-foreground">{session.title}</h2>
                <p className="text-xs text-burgundy font-semibold mt-1">{session.subtitle}</p>
                <p className="mt-3 text-sm leading-6 text-foreground/62">{session.description}</p>
              </div>

              <div className="mt-6 pt-4 border-t border-[var(--border)]">
                <button
                  onClick={() => setActiveMode(key as "role-play" | "quiz")}
                  className="tap-soft w-full rounded-xl bg-burgundy py-3 text-center text-sm font-bold text-white hover:bg-burgundy-700"
                >
                  Începe sesiunea
                </button>
              </div>
            </article>
          ))}

          <article className="rounded-3xl border border-[var(--border)] bg-surface-muted/50 p-6 shadow-sm border-dashed flex flex-col justify-between">
            <div>
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-foreground/5 text-foreground/45 mb-4">
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              </span>
              <h2 className="font-display text-xl font-bold text-foreground/55">Coaching pe situație reală</h2>
              <p className="text-xs text-foreground/45 font-semibold mt-1">Mod asistență activă</p>
              <p className="mt-3 text-sm leading-6 text-foreground/50">
                În curând vei putea descrie o situație dificilă din echipa ta și vei primi sfaturi personalizate bazate pe profilurile PCM ale colegilor.
              </p>
            </div>
            <div className="mt-6 pt-4">
              <button disabled className="w-full rounded-xl bg-foreground/10 py-3 text-center text-sm font-bold text-foreground/45 cursor-not-allowed">
                Indisponibil în demo
              </button>
            </div>
          </article>
        </div>
      ) : (
        <section className="rounded-3xl border border-[var(--border)] bg-surface shadow-xl overflow-hidden flex flex-col h-[600px] animate-fade-up">
          {/* Header */}
          <div className="bg-surface border-b border-[var(--border)] px-6 py-4 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={handleReturnToMenu}
                className="tap-soft rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-bold text-foreground hover:bg-surface-muted"
              >
                ← Înapoi
              </button>
              <div>
                <h3 className="text-sm font-bold text-foreground">{chatSessions[activeMode].title}</h3>
                <p className="text-xs font-semibold text-burgundy">{chatSessions[activeMode].subtitle}</p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 rounded-full bg-success" />
              <span className="text-xs font-semibold text-foreground/55">Sesiune Activă</span>
            </div>
          </div>

          {/* Messages body */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4 bg-background/30 scrollbar-thin">
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`flex max-w-[80%] flex-col rounded-2xl p-4 text-sm leading-6 animate-fade-up ${
                  msg.sender === "user"
                    ? "self-end bg-burgundy text-white rounded-br-none"
                    : "self-start bg-surface border border-[var(--border)] text-foreground rounded-bl-none"
                }`}
              >
                <p className="font-semibold text-[10px] uppercase tracking-wider opacity-60 mb-0.5">
                  {msg.sender === "user" ? "Tu" : "Codruț"}
                </p>
                <p className="whitespace-pre-line">{msg.text}</p>
                <span className="text-[9px] opacity-40 self-end mt-1.5">{msg.time}</span>
              </div>
            ))}
          </div>

          {/* Footer input area */}
          <div className="border-t border-[var(--border)] p-4 bg-surface">
            {sessionCompleted ? (
              <div className="text-center p-3">
                <p className="text-sm font-bold text-foreground">Sesiune Finalizată!</p>
                <p className="text-xs text-foreground/62 mt-1">
                  Ai completat activitatea de antrenament și ai obținut <strong className="text-burgundy">+{xpEarned} XP</strong>.
                </p>
                <button
                  onClick={handleReturnToMenu}
                  className="tap-soft mt-4 rounded-xl bg-burgundy px-6 py-2.5 text-xs font-bold text-white hover:bg-burgundy-700"
                >
                  Finalizează și revino la meniu
                </button>
              </div>
            ) : (
              <div>
                <p className="text-xs font-bold text-foreground/62 mb-3.5">
                  {chatSessions[activeMode].steps[currentStepIdx].question}
                </p>
                <div className="grid gap-2.5 md:grid-cols-2">
                  {chatSessions[activeMode].steps[currentStepIdx].options.map((opt, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSelectOption(opt)}
                      className="tap-soft text-left border border-[var(--border)] hover:border-burgundy/45 bg-surface-muted/50 hover:bg-burgundy-50/10 p-3 rounded-xl text-xs font-semibold text-foreground/80 hover:text-burgundy leading-5"
                    >
                      <span className="block font-bold text-[10px] uppercase text-foreground/45 mb-1">{opt.label}</span>
                      {opt.text}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>
      )}
    </AppShell>
  );
}
