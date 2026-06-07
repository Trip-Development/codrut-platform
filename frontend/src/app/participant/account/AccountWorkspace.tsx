"use client";

import React, { useState, useEffect } from "react";

type WorkspaceSummary = {
  projectName: string;
  participantEmail?: string | null;
};

type AccountWorkspaceProps = {
  session: import("@/api/auth").SessionState;
  summary: WorkspaceSummary;
};

const pcmProfiles = [
  {
    type: "harmonizer",
    name: "Empatic (Harmonizer)",
    color: "var(--bloom-gold)",
    channel: "Nutritiv (Cald, suportiv, empatic)",
    need: "Relaționare și apreciere necondiționată a persoanei",
    tip: "Fă-ți timp pentru conectarea personală înainte de task-uri și reîncarcă-ți bateriile într-un mediu primitor. Nu uita să ai grijă și de nevoile tale, nu doar de ale celorlalți.",
    distress: "Tinde să facă greșeli din neatenție în încercarea de a mulțumi pe toată lumea și evită confruntările directe."
  },
  {
    type: "thinker",
    name: "Logician (Thinker)",
    color: "var(--bloom-blue)",
    channel: "Informativ/Întrebări (Logic, structurat, orientat pe fapte)",
    need: "Recunoaștere a muncii și organizarea timpului / structură",
    tip: "Planifică-ți agenda detaliat și bazează-te pe date clare în luarea deciziilor. Alocă-ți intervale dedicate de concentrare neîntreruptă pentru analiză.",
    distress: "Poate deveni ultra-critic, micro-manageriază sau tinde să controleze excesiv detaliile nesemnificative."
  },
  {
    type: "persister",
    name: "Perseverent (Persister)",
    color: "var(--bloom-green)",
    channel: "Informativ/Întrebări/Opinii (Respectuos, axat pe principii și valori)",
    need: "Recunoaștere a opiniilor și respect pentru convingeri/loialitate",
    tip: "Angajează-te în proiecte aliniate cu valorile tale și oferă feedback bazat pe principii solide. Permite-ți să asculți opinii diferite fără a le percepe ca atacuri personale.",
    distress: "Tinde să predice, să observe doar greșelile celorlalți sau să devină inflexibil în opinii."
  },
  {
    type: "rebel",
    name: "Spontan (Rebel)",
    color: "var(--bloom-red)",
    channel: "Emotiv (Ludic, energic, spontan)",
    need: "Contact social și stimulare senzorială prin activități variate",
    tip: "Adaugă elemente de joc (gamification) în activitățile de zi cu zi. Colaborează în moduri nestructurate și dinamice cu echipa ta pentru a-ți menține entuziasmul.",
    distress: "Are tendința de a delega vina, de a se plânge că e plictisitor sau de a lăsa task-urile neterminate."
  },
  {
    type: "imaginer",
    name: "Reflexiv (Imaginer)",
    color: "var(--bloom-blue)",
    channel: "Directiv (Clar, concis, orientat pe instrucțiuni)",
    need: "Solitudine, timp și spațiu pentru reflecție",
    tip: "Alocă-ți un spațiu de lucru liniștit pentru a procesa ideile complexe în ritmul tău. Cere instrucțiuni scrise și concise atunci când colaborezi la proiecte mari.",
    distress: "Se izolează complet, devine pasiv și poate fi copleșit de prea mulți stimuli sau interacțiuni sociale directe."
  },
  {
    type: "promoter",
    name: "Promotor (Promoter)",
    color: "var(--bloom-red)",
    channel: "Directiv (Orientat spre acțiune, energic)",
    need: "Excitare/Acțiune și rezultate rapide",
    tip: "Focalizează-te pe rezultate pe termen scurt, inițiază proiecte noi cu impact vizibil și asumă-ți riscuri calculate pentru a-ți păstra nivelul de adrenalină.",
    distress: "Tinde să manipuleze pentru a obține ce dorește, creează situații de conflict artificiale sau lasă în urmă detalii importante."
  }
];

const predefinedGoals = [
  "Ascultare activă",
  "Feedback asertiv",
  "Gestiunea reacțiilor",
  "Delegare cu sens",
  "Gestionarea conflictelor",
  "Comunicare empatică",
  "Prezentări cu impact",
  "Managementul timpului"
];

export function AccountWorkspace({ session, summary }: AccountWorkspaceProps) {
  const [activeTab, setActiveTab] = useState<"general" | "pcm" | "notifications" | "privacy">("general");
  
  // Settings States loaded from localStorage on mount
  const [selectedPcm, setSelectedPcm] = useState<string>("harmonizer");
  const [goals, setGoals] = useState<string[]>([
    "Ascultare activă",
    "Feedback asertiv",
    "Gestiunea reacțiilor",
    "Delegare cu sens"
  ]);
  const [newGoalInput, setNewGoalInput] = useState("");
  const [notifications, setNotifications] = useState({
    emailTasks: true,
    emailWeekly: true,
    pushReminders: true,
  });
  const [privacy, setPrivacy] = useState({
    shareWithCoach: true,
    benchmarkAnon: true,
    visibleOnLeaderboard: false,
  });

  const [savedMessage, setSavedMessage] = useState<string | null>(null);

  // Load preferences from localStorage on mount
  useEffect(() => {
    const storedPcm = localStorage.getItem("codrut_account_pcm");
    if (storedPcm) setSelectedPcm(storedPcm);

    const storedGoals = localStorage.getItem("codrut_account_goals");
    if (storedGoals) {
      try {
        setGoals(JSON.parse(storedGoals));
      } catch (e) {
        console.error("Failed to parse stored goals", e);
      }
    }

    const storedNotifications = localStorage.getItem("codrut_account_notifications");
    if (storedNotifications) {
      try {
        setNotifications(JSON.parse(storedNotifications));
      } catch (e) {}
    }

    const storedPrivacy = localStorage.getItem("codrut_account_privacy");
    if (storedPrivacy) {
      try {
        setPrivacy(JSON.parse(storedPrivacy));
      } catch (e) {}
    }
  }, []);

  const triggerSaveNotification = (msg: string) => {
    setSavedMessage(msg);
    setTimeout(() => {
      setSavedMessage(null);
    }, 2500);
  };

  const handleToggleGoal = (goal: string) => {
    let updated: string[];
    if (goals.includes(goal)) {
      updated = goals.filter((g) => g !== goal);
    } else {
      updated = [...goals, goal];
    }
    setGoals(updated);
    localStorage.setItem("codrut_account_goals", JSON.stringify(updated));
    triggerSaveNotification("Obiective actualizate cu succes!");
  };

  const handleAddCustomGoal = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newGoalInput.trim()) return;
    if (goals.includes(newGoalInput.trim())) return;
    const updated = [...goals, newGoalInput.trim()];
    setGoals(updated);
    localStorage.setItem("codrut_account_goals", JSON.stringify(updated));
    setNewGoalInput("");
    triggerSaveNotification("Obiectiv personalizat adăugat!");
  };

  const handlePcmChange = (type: string) => {
    setSelectedPcm(type);
    localStorage.setItem("codrut_account_pcm", type);
    triggerSaveNotification("Profil PCM salvat!");
  };

  const handleToggleNotification = (key: keyof typeof notifications) => {
    const updated = { ...notifications, [key]: !notifications[key] };
    setNotifications(updated);
    localStorage.setItem("codrut_account_notifications", JSON.stringify(updated));
    triggerSaveNotification("Preferințe notificări actualizate!");
  };

  const handleTogglePrivacy = (key: keyof typeof privacy) => {
    const updated = { ...privacy, [key]: !privacy[key] };
    setPrivacy(updated);
    localStorage.setItem("codrut_account_privacy", JSON.stringify(updated));
    triggerSaveNotification("Preferințe confidențialitate actualizate!");
  };

  const name = session.user.name || "Radu Georgescu";
  const email = summary.participantEmail || "radu.georgescu@michelin.ro";
  const company = summary.projectName.includes("Michelin") ? "Michelin România" : "Companie Parteneră";
  const activePcmData = pcmProfiles.find((p) => p.type === selectedPcm) || pcmProfiles[0];

  return (
    <div className="relative">
      {/* Toast Save Message */}
      <div 
        className={`fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-3 bg-surface border border-[var(--border)] rounded-2xl shadow-xl transition-all duration-300 transform ${
          savedMessage ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0 pointer-events-none"
        }`}
      >
        <span className="w-2 h-2 rounded-full bg-burgundy animate-ping" />
        <span className="text-xs font-bold text-foreground/80">{savedMessage}</span>
      </div>

      <div className="grid gap-6 md:grid-cols-12 animate-fade-up">
        {/* Navigation Tabs (Left side) */}
        <div className="md:col-span-3 flex flex-col gap-1.5">
          <button
            onClick={() => setActiveTab("general")}
            className={`flex items-center gap-3 px-4 py-3 rounded-2xl border text-xs font-bold uppercase tracking-wider transition-all text-left ${
              activeTab === "general"
                ? "bg-burgundy text-white border-burgundy shadow-sm"
                : "bg-surface border-[var(--border)] text-foreground/72 hover:bg-surface-muted/50"
            }`}
          >
            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
            Profil & Rol
          </button>

          <button
            onClick={() => setActiveTab("pcm")}
            className={`flex items-center gap-3 px-4 py-3 rounded-2xl border text-xs font-bold uppercase tracking-wider transition-all text-left ${
              activeTab === "pcm"
                ? "bg-burgundy text-white border-burgundy shadow-sm"
                : "bg-surface border-[var(--border)] text-foreground/72 hover:bg-surface-muted/50"
            }`}
          >
            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            Profilul PCM
          </button>

          <button
            onClick={() => setActiveTab("notifications")}
            className={`flex items-center gap-3 px-4 py-3 rounded-2xl border text-xs font-bold uppercase tracking-wider transition-all text-left ${
              activeTab === "notifications"
                ? "bg-burgundy text-white border-burgundy shadow-sm"
                : "bg-surface border-[var(--border)] text-foreground/72 hover:bg-surface-muted/50"
            }`}
          >
            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            Notificări
          </button>

          <button
            onClick={() => setActiveTab("privacy")}
            className={`flex items-center gap-3 px-4 py-3 rounded-2xl border text-xs font-bold uppercase tracking-wider transition-all text-left ${
              activeTab === "privacy"
                ? "bg-burgundy text-white border-burgundy shadow-sm"
                : "bg-surface border-[var(--border)] text-foreground/72 hover:bg-surface-muted/50"
            }`}
          >
            <svg className="w-4 h-4 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
            </svg>
            Confidențialitate
          </button>
        </div>

        {/* Tab Contents (Right side) */}
        <div className="md:col-span-9 space-y-6">
          {/* TAB 1: General Info & Goals */}
          {activeTab === "general" && (
            <div className="space-y-6">
              <section className="rounded-3xl border border-[var(--border)] bg-surface p-6 md:p-8 shadow-sm space-y-6">
                <h3 className="font-display text-lg font-bold text-foreground">Date Generale Profil</h3>
                
                <div className="grid gap-6 sm:grid-cols-2">
                  <div>
                    <span className="block text-xs font-bold uppercase tracking-wider text-foreground/45">Nume complet</span>
                    <span className="block text-sm sm:text-base font-semibold text-foreground mt-1.5">{name}</span>
                  </div>
                  <div>
                    <span className="block text-xs font-bold uppercase tracking-wider text-foreground/45">Adresă email corporate</span>
                    <span className="block text-sm sm:text-base font-semibold text-foreground mt-1.5">{email}</span>
                  </div>
                  <div>
                    <span className="block text-xs font-bold uppercase tracking-wider text-foreground/45">Companie</span>
                    <span className="block text-sm sm:text-base font-semibold text-foreground mt-1.5">{company}</span>
                  </div>
                  <div>
                    <span className="block text-xs font-bold uppercase tracking-wider text-foreground/45">Rol în program</span>
                    <span className="block text-sm sm:text-base font-semibold text-burgundy font-bold mt-1.5">Participant Evaluat (Leadership)</span>
                  </div>
                </div>
              </section>

              {/* Goals Manager Widget */}
              <section className="rounded-3xl border border-[var(--border)] bg-surface p-6 md:p-8 shadow-sm space-y-6">
                <div>
                  <h3 className="font-display text-lg font-bold text-foreground">Obiectivele tale de dezvoltare</h3>
                  <p className="text-xs sm:text-sm text-foreground/62 mt-1">
                    Selectează sau adaugă competențele pe care vrei să te focusezi în sesiunile actuale de coaching.
                  </p>
                </div>

                <div className="flex flex-wrap gap-2.5">
                  {predefinedGoals.map((goal) => {
                    const isActive = goals.includes(goal);
                    return (
                      <button
                        key={goal}
                        onClick={() => handleToggleGoal(goal)}
                        className={`px-3 py-1.5 rounded-full text-xs font-bold transition-all border ${
                          isActive
                            ? "bg-burgundy border-burgundy text-white shadow-sm"
                            : "bg-surface-muted/60 border-[var(--border)] text-foreground/72 hover:bg-surface-muted"
                        }`}
                      >
                        {goal} {isActive ? "✓" : "+"}
                      </button>
                    );
                  })}
                </div>

                {/* Custom Goal Form */}
                <form onSubmit={handleAddCustomGoal} className="flex gap-3 pt-4 border-t border-[var(--border)]">
                  <input
                    type="text"
                    placeholder="Adaugă un obiectiv personalizat..."
                    value={newGoalInput}
                    onChange={(e) => setNewGoalInput(e.target.value)}
                    className="flex-1 px-4 py-2.5 rounded-2xl border border-[var(--border)] bg-surface-muted/40 text-sm focus:outline-none focus:border-burgundy/40 text-foreground transition-all"
                  />
                  <button
                    type="submit"
                    className="px-4 py-2 bg-burgundy hover:bg-burgundy/90 text-white rounded-2xl text-xs font-bold uppercase tracking-wider shadow-sm transition-all"
                  >
                    Adaugă
                  </button>
                </form>

                {/* Active Goals Checklist */}
                {goals.length > 0 && (
                  <div className="pt-2">
                    <span className="block text-xs font-bold uppercase tracking-wider text-foreground/45 mb-3">Priority Focus List</span>
                    <div className="grid gap-3 sm:grid-cols-2">
                      {goals.map((goal, idx) => (
                        <div key={goal} className="flex items-center gap-3 p-3 rounded-2xl border border-[var(--border)] bg-surface-muted/20">
                          <span className="flex items-center justify-center w-6 h-6 rounded-xl bg-burgundy/10 text-burgundy font-mono text-xs font-bold">
                            {idx + 1}
                          </span>
                          <span className="text-sm font-semibold text-foreground">{goal}</span>
                          <button
                            onClick={() => handleToggleGoal(goal)}
                            className="ml-auto text-foreground/35 hover:text-burgundy transition-all p-1"
                            title="Elimină din listă"
                          >
                            ×
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </section>
            </div>
          )}

          {/* TAB 2: Process Communication Model (PCM) Profile */}
          {activeTab === "pcm" && (
            <section className="rounded-3xl border border-[var(--border)] bg-surface p-6 md:p-8 shadow-sm space-y-6">
              <div>
                <h3 className="font-display text-lg font-bold text-foreground">Structura Profilului Tău PCM</h3>
                <p className="text-sm text-foreground/62 mt-1">
                  Rezultatele oficiale din evaluarea ta Process Communication Model. Profilul tău indică energia Bazei și Fazei curente.
                </p>
              </div>

              <div className="grid gap-6 md:grid-cols-2">
                {/* Baza (Base) Card */}
                <div className="p-6 rounded-3xl border border-[var(--border)] bg-surface-muted/20 space-y-4">
                  <div className="flex items-center gap-3 border-b border-[var(--border)] pb-3">
                    <span className="w-4 h-4 rounded-full bg-[var(--bloom-gold)] shrink-0" />
                    <div>
                      <span className="block text-[10px] font-bold uppercase tracking-wider text-burgundy">Baza ta PCM</span>
                      <h4 className="text-base font-extrabold text-foreground">Empatic (Harmonizer)</h4>
                    </div>
                  </div>
                  <div className="space-y-3 text-xs leading-normal">
                    <p className="text-foreground/72">
                      <strong className="text-foreground">Canal de Comunicare:</strong> Nutritiv (Cald, suportiv, empatic)
                    </p>
                    <p className="text-foreground/72">
                      <strong className="text-foreground">Nevoie Psihologică:</strong> Relaționare și apreciere necondiționată a persoanei
                    </p>
                    <div className="pt-2 border-t border-[var(--border)]">
                      <span className="block font-bold text-burgundy uppercase tracking-wider text-[10px] mb-1">Recomandare:</span>
                      <p className="text-foreground/80 leading-relaxed">
                        Fă-ți timp pentru conectarea personală înainte de task-uri și reîncarcă-ți bateriile într-un mediu primitor. Nu uita să ai grijă și de nevoile tale, nu doar de ale celorlalți.
                      </p>
                    </div>
                    <div className="pt-2 border-t border-[var(--border)]">
                      <span className="block font-bold text-foreground/55 uppercase tracking-wider text-[10px] mb-1">Sub stres (Distress):</span>
                      <p className="text-foreground/72 italic">
                        Tinde să facă greșeli din neatenție în încercarea de a mulțumi pe toată lumea și evită confruntările directe.
                      </p>
                    </div>
                  </div>
                </div>

                {/* Faza (Phase) Card */}
                <div className="p-6 rounded-3xl border border-[var(--border)] bg-surface-muted/20 space-y-4">
                  <div className="flex items-center gap-3 border-b border-[var(--border)] pb-3">
                    <span className="w-4 h-4 rounded-full bg-[var(--bloom-blue)] shrink-0" />
                    <div>
                      <span className="block text-[10px] font-bold uppercase tracking-wider text-burgundy">Faza ta PCM</span>
                      <h4 className="text-base font-extrabold text-foreground">Logician (Thinker)</h4>
                    </div>
                  </div>
                  <div className="space-y-3 text-xs leading-normal">
                    <p className="text-foreground/72">
                      <strong className="text-foreground">Canal de Comunicare:</strong> Informativ/Întrebări (Logic, structurat, fapte)
                    </p>
                    <p className="text-foreground/72">
                      <strong className="text-foreground">Nevoie Psihologică:</strong> Recunoaștere a muncii și organizarea timpului
                    </p>
                    <div className="pt-2 border-t border-[var(--border)]">
                      <span className="block font-bold text-burgundy uppercase tracking-wider text-[10px] mb-1">Recomandare:</span>
                      <p className="text-foreground/80 leading-relaxed">
                        Planifică-ți agenda detaliat și bazează-te pe date clare în luarea deciziilor. Alocă-ți intervale dedicate de concentrare neîntreruptă pentru analiză.
                      </p>
                    </div>
                    <div className="pt-2 border-t border-[var(--border)]">
                      <span className="block font-bold text-foreground/55 uppercase tracking-wider text-[10px] mb-1">Sub stres (Distress):</span>
                      <p className="text-foreground/72 italic">
                        Poate deveni ultra-critic, micro-manageriază sau tinde să controleze excesiv detaliile nesemnificative.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* TAB 3: Notifications Settings */}
          {activeTab === "notifications" && (
            <section className="rounded-3xl border border-[var(--border)] bg-surface p-6 md:p-8 shadow-sm space-y-6">
              <div>
                <h3 className="font-display text-lg font-bold text-foreground">Preferințe Notificări</h3>
                <p className="text-xs sm:text-sm text-foreground/62 mt-1">
                  Configurează cum și când dorești să primești alerte legate de programul tău.
                </p>
              </div>

              <div className="space-y-4 pt-2">
                <div className="flex items-center justify-between p-4 rounded-2xl border border-[var(--border)] bg-surface-muted/20">
                  <div className="flex flex-col pr-4">
                    <span className="text-sm sm:text-base font-bold text-foreground">Alerte chestionare noi</span>
                    <span className="text-xs text-foreground/55 mt-0.5 leading-normal">
                      Primește un e-mail când trainerul îți alocă un chestionar sau un exercițiu nou.
                    </span>
                  </div>
                  <button
                    onClick={() => handleToggleNotification("emailTasks")}
                    className={`w-11 h-6 shrink-0 rounded-full transition-colors relative ${
                      notifications.emailTasks ? "bg-burgundy" : "bg-foreground/20"
                    }`}
                  >
                    <span 
                      className={`absolute top-1 left-1 bg-white w-4 h-4 rounded-full transition-transform ${
                        notifications.emailTasks ? "translate-x-5" : "translate-x-0"
                      }`} 
                    />
                  </button>
                </div>

                <div className="flex items-center justify-between p-4 rounded-2xl border border-[var(--border)] bg-surface-muted/20">
                  <div className="flex flex-col pr-4">
                    <span className="text-sm sm:text-base font-bold text-foreground">Raport săptămânal de progres</span>
                    <span className="text-xs text-foreground/55 mt-0.5 leading-normal">
                      Sinteză cu punctele XP acumulate, progresul sarcinilor și recomandările curente.
                    </span>
                  </div>
                  <button
                    onClick={() => handleToggleNotification("emailWeekly")}
                    className={`w-11 h-6 shrink-0 rounded-full transition-colors relative ${
                      notifications.emailWeekly ? "bg-burgundy" : "bg-foreground/20"
                    }`}
                  >
                    <span 
                      className={`absolute top-1 left-1 bg-white w-4 h-4 rounded-full transition-transform ${
                        notifications.emailWeekly ? "translate-x-5" : "translate-x-0"
                      }`} 
                    />
                  </button>
                </div>

                <div className="flex items-center justify-between p-4 rounded-2xl border border-[var(--border)] bg-surface-muted/20">
                  <div className="flex flex-col pr-4">
                    <span className="text-sm sm:text-base font-bold text-foreground">Memento-uri zilnice</span>
                    <span className="text-xs text-foreground/55 mt-0.5 leading-normal">
                      Alerte pentru menținerea seriei de activități (streak) și obiectivele zilei.
                    </span>
                  </div>
                  <button
                    onClick={() => handleToggleNotification("pushReminders")}
                    className={`w-11 h-6 shrink-0 rounded-full transition-colors relative ${
                      notifications.pushReminders ? "bg-burgundy" : "bg-foreground/20"
                    }`}
                  >
                    <span 
                      className={`absolute top-1 left-1 bg-white w-4 h-4 rounded-full transition-transform ${
                        notifications.pushReminders ? "translate-x-5" : "translate-x-0"
                      }`} 
                    />
                  </button>
                </div>
              </div>
            </section>
          )}

          {/* TAB 4: Privacy Settings */}
          {activeTab === "privacy" && (
            <section className="rounded-3xl border border-[var(--border)] bg-surface p-6 md:p-8 shadow-sm space-y-5">
              <div>
                <h3 className="font-display text-lg font-bold text-foreground">Confidențialitate Date & Reguli</h3>
                <p className="text-sm text-foreground/62 mt-1">
                  Informații despre confidențialitatea datelor tale și modul în care sunt utilizate rezultatele în platformă.
                </p>
              </div>

              <div className="space-y-4 pt-2">
                <div className="p-5 rounded-2xl border border-[var(--border)] bg-surface-muted/30 space-y-2.5">
                  <span className="inline-block px-2.5 py-1 rounded-full bg-burgundy/10 text-burgundy text-[10px] font-bold uppercase tracking-wider">
                    Securitate și Anonimat
                  </span>
                  <p className="text-xs sm:text-sm text-foreground/75 leading-relaxed">
                    Răspunsurile individuale la chestionarele 360 sunt complet anonimizate și agregate. Managementul direct, departamentul de HR sau colegii tăi nu vor avea niciodată acces la răspunsurile tale specifice detaliate, asigurând un mediu sigur pentru feedback onest.
                  </p>
                </div>

                <div className="p-5 rounded-2xl border border-[var(--border)] bg-surface-muted/30 space-y-2.5">
                  <span className="inline-block px-2.5 py-1 rounded-full bg-burgundy/10 text-burgundy text-[10px] font-bold uppercase tracking-wider">
                    Rolul Trainerului
                  </span>
                  <p className="text-xs sm:text-sm text-foreground/75 leading-relaxed">
                    Doar trainerul tău acreditat (Andrei Văcaru) are acces la rezultatele individuale agregate din chestionarele de baseline pentru a putea ghida sesiunile de coaching 1-la-1 și a ajusta exercițiile conform nevoilor tale specifice.
                  </p>
                </div>

                <div className="p-5 rounded-2xl border border-[var(--border)] bg-surface-muted/30 space-y-2.5">
                  <span className="inline-block px-2.5 py-1 rounded-full bg-burgundy/10 text-burgundy text-[10px] font-bold uppercase tracking-wider">
                    Scopul Dezvoltării
                  </span>
                  <p className="text-xs sm:text-sm text-foreground/75 leading-relaxed">
                    Obiectivele stabilite în program sunt exclusiv în scop de dezvoltare personală și leadership. Platforma nu este utilizată pentru evaluări oficiale de performanță (performance review) sau decizii administrative.
                  </p>
                </div>
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
