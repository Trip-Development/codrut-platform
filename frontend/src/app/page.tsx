"use client";

import Image from "next/image";
import Link from "next/link";
import React, { useState, useEffect, useRef } from "react";

import { BrandMark } from "../components/brand/brand-mark";
import { ThemeToggle } from "../components/theme/theme-toggle";

type Message = {
  sender: "user" | "bot";
  text: string;
};

type Scenario = {
  title: string;
  shortLabel: string;
  conversation: Message[];
};

const landingNavItems = [
  { key: "top", href: "#top", label: "Acasă" },
  { key: "metodologie", href: "#metodologie", label: "Metodologie" },
  { key: "impact", href: "#impact", label: "Măsurarea impactului" },
  { key: "companii", href: "#companii", label: "Pentru organizații" },
] as const;

const chatScenarios: Scenario[] = [
  {
    title: "Cum deleg pregătirea unui raport important?",
    shortLabel: "Delegare eficientă",
    conversation: [
      { sender: "user", text: "Cum deleg pregătirea raportului de vânzări?" },
      { sender: "bot", text: "Delegarea este un pas excelent pentru creșterea echipei. Cui dorești să predai această responsabilitate?" },
      { sender: "user", text: "Ioanei, dar mi-e teamă că nu va avea timp sau că va greși cifrele." },
      { sender: "bot", text: "E o îngrijorare firească. Îți propun să planificați o discuție de 15 minute: explică-i contextul ('de ce' este important acest raport) și faceți prima completare împreună. Sună ca un plan bun pentru săptămâna aceasta?" },
      { sender: "user", text: "Da, stabilim o întâlnire mâine." },
      { sender: "bot", text: "Excelent! Am notat asta. Vrei să programăm un scurt reminder vineri pentru a vedea cum a decurs?" }
    ]
  },
  {
    title: "Cum dau feedback unui coleg care întârzie la ședințe?",
    shortLabel: "Feedback constructiv",
    conversation: [
      { sender: "user", text: "Cum dau feedback unui coleg care întârzie constant la ședințe?" },
      { sender: "bot", text: "Încearcă modelul de feedback orientat pe impact. Descrie comportamentul observat în mod obiectiv și cum afectează restul echipei." },
      { sender: "user", text: "Cum aș putea începe discuția fără să pară un atac?" },
      { sender: "bot", text: "Poți folosi o formulare neutră: 'Am observat că la ultimele trei ședințe ai ajuns cu 10 minute întârziere. Impactul este că reluăm discuțiile și pierdem din ritm. Cum se vede situația de la tine?'" },
      { sender: "user", text: "E mult mai bine așa, nu sună defensiv." },
      { sender: "bot", text: "Exact. Cheia este să te concentrezi pe fapte și consecințe, nu pe persoană. Vrei să facem o scurtă simulare de răspunsuri?" }
    ]
  },
  {
    title: "Cum gestionez distresul în timpul unui sprint aglomerat?",
    shortLabel: "Managementul distresului",
    conversation: [
      { sender: "user", text: "Cum gestionez distresul în timpul unui sprint extrem de aglomerat?" },
      { sender: "bot", text: "Când presiunea crește, primul pas este izolarea factorilor de distres. Ce anume te stresează cel mai mult în acest moment?" },
      { sender: "user", text: "Am prea multe sarcini urgente și termene suprapuse." },
      { sender: "bot", text: "Înțeleg. Atunci când totul pare urgent, nimic nu mai este o prioritate clară. Îți recomand să selectezi o singură activitate critică pentru următoarele 90 de minute și să blochezi toate notificările. Cum ți se pare această abordare?" },
      { sender: "user", text: "O să încerc asta chiar acum cu sarcina de design." },
      { sender: "bot", text: "Perfect! Oprește notificările de Slack. Eu te voi întreba peste 90 de minute cum te simți. Spor la lucru!" }
    ]
  }
];

export default function HomePage() {
  const [activeScenarioIdx, setActiveScenarioIdx] = useState<number>(0);
  const [displayedMessages, setDisplayedMessages] = useState<Message[]>([]);
  const [isTyping, setIsTyping] = useState<boolean>(false);

  const [activeSection, setActiveSection] = useState<string>("top");
  const [hoveredSection, setHoveredSection] = useState<string>("");
  const [indicatorStyle, setIndicatorStyle] = useState({ left: 0, width: 0, opacity: 0 });
  const navRef = useRef<HTMLDivElement>(null);
  const visibleSection = hoveredSection || activeSection;

  // Intersection Observer to detect active section on scroll
  useEffect(() => {
    const sections = ["metodologie", "impact", "companii"];
    const observerOptions = {
      root: null,
      rootMargin: "-30% 0px -50% 0px", // Trigger when the section occupies a good chunk of viewport
      threshold: 0.1,
    };

    const observerCallback = (entries: IntersectionObserverEntry[]) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          setActiveSection(entry.target.id);
        }
      });
    };

    const observer = new IntersectionObserver(observerCallback, observerOptions);

    sections.forEach((id) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });

    const handleScroll = () => {
      // Keep the first nav item active while the hero is in view.
      if (window.scrollY < 80) {
        setActiveSection("top");
      }
    };
    window.addEventListener("scroll", handleScroll);

    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", handleScroll);
    };
  }, []);

  // Update sliding indicator style when active or hovered section changes
  useEffect(() => {
    if (!navRef.current) return;

    if (!visibleSection) {
      setIndicatorStyle((prev) => ({ ...prev, opacity: 0 }));
      return;
    }

    const activeEl = navRef.current.querySelector(`[data-section="${visibleSection}"]`) as HTMLAnchorElement;
    if (activeEl) {
      setIndicatorStyle({
        left: activeEl.offsetLeft,
        width: activeEl.offsetWidth,
        opacity: 1,
      });
    } else {
      setIndicatorStyle((prev) => ({ ...prev, opacity: 0 }));
    }
  }, [visibleSection]);

  useEffect(() => {
    const fullConversation = chatScenarios[activeScenarioIdx].conversation;
    setDisplayedMessages([]);
    setIsTyping(false);

    let messageIndex = 0;
    let timer: NodeJS.Timeout;

    const showNextMessage = () => {
      if (messageIndex < fullConversation.length) {
        const nextMsg = fullConversation[messageIndex];

        if (nextMsg.sender === "bot") {
          setIsTyping(true);
          timer = setTimeout(() => {
            setIsTyping(false);
            setDisplayedMessages((prev) => [...prev, nextMsg]);
            messageIndex++;
            timer = setTimeout(showNextMessage, 1500);
          }, 1200);
        } else {
          setDisplayedMessages((prev) => [...prev, nextMsg]);
          messageIndex++;
          timer = setTimeout(showNextMessage, 800);
        }
      }
    };

    timer = setTimeout(showNextMessage, 500);

    return () => clearTimeout(timer);
  }, [activeScenarioIdx]);

  return (
    <main id="top" className="bg-vines-pattern app-min-height bg-background text-foreground">
      <header className="safe-top sticky top-0 z-40 border-b border-[var(--border)] bg-surface/88 shadow-sm backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-4 py-4 md:px-6">
          <Link
            href="/"
            className="tap-soft group -ml-2 min-w-0 rounded-2xl px-2 py-1 transition-colors hover:bg-surface-muted/80"
          >
            <BrandMark subtitle="Platformă de coaching și training" />
          </Link>

          <nav
            ref={navRef}
            aria-label="Acces rapid"
            className="relative hidden items-center gap-1 md:flex"
          >
            {/* Sliding Highlight Pill */}
            <div
              className="pointer-events-none absolute h-9 rounded-full border border-[#890505]/35 bg-[#890505]/10 transition-[transform,width,opacity] duration-300 ease-out dark:border-[#e35f5f]/45 dark:bg-[#890505]/22"
              style={{
                transform: `translateX(${indicatorStyle.left}px)`,
                width: `${indicatorStyle.width}px`,
                opacity: indicatorStyle.opacity,
              }}
            />
            {landingNavItems.map((item) => (
              <Link
                key={item.key}
                href={item.href}
                data-section={item.key}
                onMouseEnter={() => setHoveredSection(item.key)}
                onMouseLeave={() => setHoveredSection("")}
                onClick={() => setActiveSection(item.key)}
                className={`tap-soft relative z-10 rounded-full px-4 py-2 text-sm font-bold transition-colors duration-200 ${
                  visibleSection === item.key
                    ? "text-burgundy"
                    : "text-foreground/62 hover:text-burgundy"
                }`}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-3">
            <ThemeToggle />
            <Link
              href="/login"
              className="tap-soft rounded-2xl border border-[var(--border)] bg-surface px-5 py-2.5 text-center text-sm font-bold text-foreground hover:bg-surface-muted"
            >
              Intră în cont
            </Link>
            <Link
              href="#contact"
              className="tap-soft hidden rounded-2xl bg-burgundy px-5 py-2.5 text-center text-sm font-bold text-white shadow-brand hover:bg-burgundy-700 md:block"
            >
              Solicită demo
            </Link>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative mx-auto grid min-h-[calc(100dvh-5rem)] max-w-7xl items-center gap-10 overflow-hidden px-4 pb-12 pt-10 md:grid-cols-[1.05fr_0.95fr] md:px-6 md:pb-16 md:pt-14">
        <div className="relative z-10 max-w-3xl">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-[#890505]/35 bg-[#890505]/8 px-3 py-1.5 text-xs font-bold text-[#890505] shadow-none dark:border-[#e35f5f]/45 dark:bg-[#890505]/22 dark:text-[#e35f5f]">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[#890505] dark:bg-[#e35f5f]" />
            Noul standard în dezvoltarea echipelor
          </span>
          <h1 className="font-display mt-4 text-5xl font-semibold leading-[1.03] text-foreground md:text-7xl">
            Codruț transformă trainingul în pași clari pentru fiecare om.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-foreground/68 md:text-xl md:leading-9">
            O platformă de coaching continuu și follow-up ghidat, susținută de traineri acreditați, concepută pentru a asigura că abilitățile învățate în workshop-uri devin obiceiuri durabile în organizația ta.
          </p>

          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <a
              href="#contact"
              className="tap-soft rounded-2xl bg-burgundy px-6 py-4 text-center text-base font-bold text-white shadow-brand hover:bg-burgundy-700"
            >
              Programează o discuție B2B
            </a>
            <Link
              href="/login"
              className="tap-soft rounded-2xl border border-burgundy bg-surface px-6 py-4 text-center text-base font-bold text-burgundy hover:bg-burgundy-50 dark:hover:bg-burgundy/10"
            >
              Intră în cont
            </Link>
          </div>

          <div className="mt-10 grid gap-3 sm:grid-cols-3">
            <article className="rounded-2xl border border-[var(--border)] bg-surface/84 p-4 shadow-sm backdrop-blur">
              <h2 className="text-sm font-bold text-foreground">Pentru HR & L&D</h2>
              <p className="mt-2 text-sm leading-6 text-foreground/58">
                Măsurarea impactului programelor, monitorizarea progresului general și date clare privind retenția competențelor.
              </p>
            </article>
            <article className="rounded-2xl border border-[var(--border)] bg-surface/84 p-4 shadow-sm backdrop-blur">
              <h2 className="text-sm font-bold text-foreground">Pentru Management</h2>
              <p className="mt-2 text-sm leading-6 text-foreground/58">
                Un mod simplu de a alinia obiectivele de business cu dezvoltarea reală a echipei, susținut de asistentul AI.
              </p>
            </article>
            <article className="rounded-2xl border border-[var(--border)] bg-surface/84 p-4 shadow-sm backdrop-blur">
              <h2 className="text-sm font-bold text-foreground">Pentru Participanți</h2>
              <p className="mt-2 text-sm leading-6 text-foreground/58">
                Ghidaj prietenos, fără conturi complicate sau efort administrativ. Doar progres zilnic, pas cu pas.
              </p>
            </article>
          </div>
        </div>

        {/* High-fidelity Chat Mockup */}
        <div className="relative z-10 flex flex-col gap-4">
          <div className="relative rounded-[2rem] border border-[var(--border)] bg-surface/92 p-4 shadow-2xl shadow-burgundy/10 backdrop-blur md:p-5">
            <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
              <div className="flex items-center gap-3">
                <span className="relative flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-[var(--border)] bg-white shadow-sm">
                  <Image
                    src="/logo.png"
                    alt="Sigla Codruț"
                    fill
                    sizes="40px"
                    priority
                    className="object-cover"
                  />
                </span>
                <div>
                  <h3 className="text-sm font-bold text-foreground">Codruț Asistent Coaching</h3>
                  <div className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-success" />
                    <span className="text-xs font-semibold text-foreground/55">Activ de implementare</span>
                  </div>
                </div>
              </div>
              <span className="rounded-full bg-success/20 px-3 py-1 text-xs font-bold text-success-ink">Simulare demo</span>
            </div>

            {/* Chat Messages Simulator */}
            <div className="mt-4 flex h-[320px] flex-col gap-3.5 overflow-y-auto px-1 py-2 scrollbar-thin">
              {displayedMessages.map((msg, index) => (
                <div
                  key={index}
                  className={`flex max-w-[85%] flex-col rounded-2xl p-3.5 text-sm leading-6 animate-fade-up ${
                    msg.sender === "user"
                      ? "self-end bg-burgundy text-white rounded-br-none"
                      : "self-start bg-surface-muted text-foreground border border-[var(--border)] rounded-bl-none"
                  }`}
                >
                  <p className="font-semibold text-[11px] uppercase tracking-wider opacity-60 mb-0.5">
                    {msg.sender === "user" ? "Tu (Manager)" : "Codruț"}
                  </p>
                  <p className="whitespace-pre-line">{msg.text}</p>
                </div>
              ))}

              {isTyping && (
                <div className="self-start rounded-2xl bg-surface-muted border border-[var(--border)] p-3.5 rounded-bl-none">
                  <div className="flex items-center gap-1">
                    <span className="h-2 w-2 animate-bounce rounded-full bg-foreground/30 [animation-delay:-0.3s]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-foreground/30 [animation-delay:-0.15s]" />
                    <span className="h-2 w-2 animate-bounce rounded-full bg-foreground/30" />
                  </div>
                </div>
              )}
            </div>

            {/* simulated input */}
            <div className="mt-4 border-t border-[var(--border)] pt-3 flex gap-2">
              <div className="flex-1 rounded-xl bg-surface-muted border border-[var(--border)] px-4 py-2.5 text-xs text-foreground/55">
                Scrie un răspuns către Codruț...
              </div>
              <button className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-burgundy text-white hover:bg-burgundy-700">
                ➔
              </button>
            </div>
          </div>

          {/* Quick Scenario Selector */}
          <div className="rounded-2xl border border-[var(--border)] bg-surface-muted/60 p-3">
            <p className="text-xs font-bold text-foreground/62 mb-2 px-1">Alege un scenariu de coaching pentru previzualizare:</p>
            <div className="grid gap-2 grid-cols-3">
              {chatScenarios.map((sc, idx) => (
                <button
                  key={idx}
                  onClick={() => setActiveScenarioIdx(idx)}
                  className={`tap-soft rounded-xl p-2.5 text-center text-xs font-bold border transition ${
                    activeScenarioIdx === idx
                      ? "bg-burgundy text-white border-burgundy"
                      : "bg-surface text-foreground/72 border-[var(--border)] hover:bg-surface-muted"
                  }`}
                >
                  <span className="block truncate">{sc.shortLabel}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Methodology Section */}
      <section id="metodologie" className="scroll-mt-20 mx-auto max-w-7xl px-4 py-16 md:px-6 md:py-24 border-t border-[var(--border)]">
        <div className="max-w-3xl">
          <span className="text-xs font-bold uppercase tracking-wider text-burgundy">O abordare structurată</span>
          <h2 className="font-display mt-2 text-4xl font-semibold text-foreground md:text-5xl">
            Simplu la suprafață, structurat în spate.
          </h2>
          <p className="mt-4 text-lg leading-8 text-foreground/65">
            Multe programe de training eșuează pentru că participanții se întorc la vechile obiceiuri a doua zi. Codruț acoperă această breșă prin micro-coaching ghidat, transformând teoria de leadership în acțiuni recurente evaluate în timp real.
          </p>
        </div>

        <div className="mt-12 grid gap-6 md:grid-cols-4">
          <article className="rounded-3xl border border-[var(--border)] bg-surface p-6 shadow-sm">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-burgundy-50 dark:bg-burgundy/10 text-sm font-black text-burgundy">
              1
            </span>
            <h3 className="mt-5 text-xl font-bold text-foreground">Diagnostic Științific</h3>
            <p className="mt-3 text-sm leading-6 text-foreground/62">
              Evaluăm dinamica echipei prin profile PCM (Process Communication Model), diagnoza Lencioni și evaluări 360 dedicate.
            </p>
          </article>
          <article className="rounded-3xl border border-[var(--border)] bg-surface p-6 shadow-sm">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-burgundy-50 dark:bg-burgundy/10 text-sm font-black text-burgundy">
              2
            </span>
            <h3 className="mt-5 text-xl font-bold text-foreground">Workshop & Aliniere</h3>
            <p className="mt-3 text-sm leading-6 text-foreground/62">
              Sesiuni practice facilitate de traineri acreditați pentru însușirea conceptelor și stabilirea obiectivelor de dezvoltare.
            </p>
          </article>
          <article className="rounded-3xl border border-[var(--border)] bg-surface p-6 shadow-sm">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-burgundy-50 dark:bg-burgundy/10 text-sm font-black text-burgundy">
              3
            </span>
            <h3 className="mt-5 text-xl font-bold text-foreground">Coaching Continuu</h3>
            <p className="mt-3 text-sm leading-6 text-foreground/62">
              Codruț ghidează zilnic fiecare lider prin întrebări, scenarii și micro-sarcini adaptate planului lor personal de acțiune.
            </p>
          </article>
          <article className="rounded-3xl border border-[var(--border)] bg-surface p-6 shadow-sm">
            <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-burgundy-50 dark:bg-burgundy/10 text-sm font-black text-burgundy">
              4
            </span>
            <h3 className="mt-5 text-xl font-bold text-foreground">Măsurarea Impactului</h3>
            <p className="mt-3 text-sm leading-6 text-foreground/62">
              HR-ul și managementul au vizibilitate deplină asupra evoluției indicatorilor cheie prin dashboard-uri agregate.
            </p>
          </article>
        </div>
      </section>

      {/* Impact Section */}
      <section id="impact" className="scroll-mt-20 mx-auto max-w-7xl px-4 pb-16 md:px-6 md:pb-24">
        <div className="rounded-[2.5rem] border border-[var(--border)] bg-surface/92 p-8 shadow-sm md:p-12">
          <div className="grid gap-10 lg:grid-cols-[0.85fr_1.15fr] items-center">
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-burgundy">Performanță dovedită</span>
              <h2 className="font-display mt-2 text-4xl font-semibold text-foreground">
                Continuitate după training, fără follow-up pierdut.
              </h2>
              <p className="mt-4 text-base leading-7 text-foreground/65">
                Vrem ca antrenamentul tău corporate să își demonstreze eficiența. Platforma monitorizează automat completările, trimite remindere inteligente și oferă o imagine clară asupra modului în care conceptele se aplică în munca de zi cu zi.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <article className="rounded-2xl border border-[var(--border)] bg-surface-muted p-5">
                <span className="mb-3 block h-1.5 w-10 rounded-full bg-success" />
                <h4 className="font-bold text-foreground text-sm">Link sigur</h4>
                <p className="mt-1 text-xs leading-5 text-foreground/58">Completare directă din invitația securizată primită pe email, fără parole.</p>
              </article>
              <article className="rounded-2xl border border-[var(--border)] bg-surface-muted p-5">
                <span className="mb-3 block h-1.5 w-10 rounded-full bg-success" />
                <h4 className="font-bold text-foreground text-sm">Chestionare grupate</h4>
                <p className="mt-1 text-xs leading-5 text-foreground/58">Toate evaluările active apar grupate pe proiect, ușor de urmărit.</p>
              </article>
              <article className="rounded-2xl border border-[var(--border)] bg-surface-muted p-5">
                <span className="mb-3 block h-1.5 w-10 rounded-full bg-success" />
                <h4 className="font-bold text-foreground text-sm">Rapoarte dinamice</h4>
                <p className="mt-1 text-xs leading-5 text-foreground/58">Date agregate actualizate automat, gata pentru prezentările executive.</p>
              </article>
              <article className="rounded-2xl border border-[var(--border)] bg-surface-muted p-5">
                <span className="mb-3 block h-1.5 w-10 rounded-full bg-success" />
                <h4 className="font-bold text-foreground text-sm">Confidențialitate garantată</h4>
                <p className="mt-1 text-xs leading-5 text-foreground/58">Răspunsurile individuale sunt protejate pentru a asigura transparență maximă.</p>
              </article>
            </div>
          </div>
        </div>
      </section>

      {/* B2B Demo / Contact Section */}
      <div id="companii" className="scroll-mt-20">
        <section id="contact" className="mx-auto max-w-4xl px-4 pb-24 text-center md:px-6">
          <div className="rounded-3xl border border-[var(--border)] bg-surface-muted/40 p-8 md:p-12">
            <h2 className="font-display text-3xl font-semibold text-foreground md:text-4xl">
              Pregătit să mărești impactul workshop-urilor tale?
            </h2>
            <p className="mt-4 mx-auto max-w-xl text-base text-foreground/65">
              Fie că ești director HR în căutarea unei soluții de follow-up sau manager care vrea alinierea echipei, programează o discuție cu noi pentru a vedea cum te poate ajuta asistentul Codruț.
            </p>
            <div className="mt-8 flex flex-col items-center gap-3 sm:flex-row justify-center">
              <input
                type="email"
                placeholder="Adresa de email corporate"
                className="w-full sm:w-72 rounded-2xl border border-[var(--border)] bg-surface px-5 py-4 text-sm text-foreground focus:border-burgundy focus:outline-none"
              />
              <button className="tap-soft w-full sm:w-auto rounded-2xl bg-burgundy px-7 py-4 text-sm font-bold text-white shadow-brand hover:bg-burgundy-700">
                Solicită o discuție
              </button>
            </div>
          </div>
        </section>
      </div>

      <footer className="border-t border-[var(--border)] bg-surface/70 px-4 py-8 md:px-6">
        <div className="mx-auto max-w-7xl flex flex-col sm:flex-row justify-between items-center gap-4 text-xs font-semibold text-foreground/55">
          <div>© {new Date().getFullYear()} Codruț. Toate drepturile rezervate.</div>
          <div className="flex gap-4">
            <Link href="/trainer/login" className="hover:text-burgundy">
              Autentificare trainer
            </Link>
          </div>
        </div>
      </footer>
    </main>
  );
}
