"use client";

import Link from "next/link";
import { Fraunces } from "next/font/google";
import { ArrowRightIcon } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import type { CurrentUser } from "@/api/auth";

import { BrandMark } from "@/components/brand/brand-mark";
import { cn } from "@/utils/cn";

export const REMEMBERED_SESSION_DELAY_MS = 900;

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  weight: ["500", "700"],
});

type AuthQuoteVariant = "participant" | "trainer" | "activation" | "recovery" | "security";

const authQuoteCopy: Record<
  AuthQuoteVariant,
  {
    subtitle: string;
    kicker: string;
    quote: string;
    caption: string;
  }
> = {
  participant: {
    subtitle: "Spațiu participant",
    kicker: "Confidențial",
    quote: "„Un chestionar bun nu grăbește răspunsul. Îți lasă spațiu să vezi ce se întâmplă cu tine și cu echipa.”",
    caption: "Cody pentru participanți",
  },
  trainer: {
    subtitle: "Portal trainer",
    kicker: "Rollout controlat",
    quote: "„Un program de training are nevoie de suport după workshop, nu doar de prezență în sală.”",
    caption: "Cody pentru traineri",
  },
  activation: {
    subtitle: "Activare cont",
    kicker: "Acces permanent",
    quote: "„Accesul bun începe cu încredere: profil clar, acord explicit și date păstrate în contextul proiectului.”",
    caption: "Activare cont Cody",
  },
  recovery: {
    subtitle: "Recuperare acces",
    kicker: "Securitate",
    quote: "„Recuperarea parolei trebuie să fie simplă, dar să păstreze controlul asupra contului.”",
    caption: "Resetare securizată",
  },
  security: {
    subtitle: "Securitate cont",
    kicker: "Parolă nouă",
    quote: "„Schimbarea parolei trebuie să fie simplă, iar accesul vechi să nu mai poată fi folosit.”",
    caption: "Acces Cody",
  },
};

type AuthQuotePanelProps = {
  variant: AuthQuoteVariant;
  className?: string;
};

export function AuthQuotePanel({ variant, className }: AuthQuotePanelProps) {
  const copy = authQuoteCopy[variant];

  return (
    <section
      className={cn(
        "hidden overflow-hidden border-r border-burgundy-700 bg-burgundy-900 p-10 text-white lg:flex lg:flex-col lg:justify-between",
        fraunces.variable,
        className,
      )}
    >
      <Link href="/" className="inline-flex w-fit rounded-lg px-2 py-1 transition-colors hover:bg-white/10">
        <BrandMark subtitle={copy.subtitle} tone="inverted" />
      </Link>

      <div className="max-w-xl">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/60">{copy.kicker}</p>
        <blockquote className="mt-8">
          <p className="text-5xl font-medium leading-tight tracking-normal [font-family:var(--font-fraunces)]">{copy.quote}</p>
          <footer className="mt-6 text-sm font-semibold text-white/68">{copy.caption}</footer>
        </blockquote>
      </div>

    </section>
  );
}

type AuthTextLinkProps = {
  href: string;
  children: ReactNode;
  className?: string;
};

export function AuthTextLink({ href, children, className }: AuthTextLinkProps) {
  return (
    <Link
      href={href}
      className={cn(
        "inline-flex items-center gap-1.5 text-sm font-semibold text-burgundy underline-offset-4 transition-colors hover:text-burgundy-700 hover:underline",
        className,
      )}
    >
      {children}
      <ArrowRightIcon className="size-3.5" aria-hidden="true" />
    </Link>
  );
}

type RememberedSessionSplashProps = {
  user: CurrentUser;
};

export function RememberedSessionSplash({ user }: RememberedSessionSplashProps) {
  const [progressStarted, setProgressStarted] = useState(false);
  const display = getRememberedSessionDisplay(user);
  const destinationLabel = user.role === "trainer" ? "portalul de trainer" : "spațiul tău";

  useEffect(() => {
    const root = document.documentElement;
    const progressTimer = window.setTimeout(() => setProgressStarted(true), 40);
    root.dataset.rememberedSession = "true";
    return () => {
      window.clearTimeout(progressTimer);
      delete root.dataset.rememberedSession;
    };
  }, []);

  return (
    <main className="flex min-h-[100dvh] items-center justify-center bg-background px-4 py-10 text-foreground">
      <section className="w-full max-w-md rounded-lg border bg-surface p-8 shadow-sm" role="status" aria-live="polite">
        <BrandMark subtitle="Sesiune salvată" />
        <div className="mt-12">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-burgundy">Bine ai revenit</p>
          <h1 className="mt-3 text-4xl font-semibold leading-tight tracking-normal text-foreground">
            {display.title}
          </h1>
          <p className="mt-4 text-sm font-medium leading-6 text-muted-foreground">
            {display.body} Te ducem în {destinationLabel}.
          </p>
        </div>

        <div className="mt-10 h-2 overflow-hidden rounded-full bg-muted" aria-label="Încărcăm sesiunea salvată">
          <div
            className={cn(
              "h-full w-full origin-left scale-x-0 rounded-full bg-burgundy transition-transform ease-out motion-reduce:scale-x-100 motion-reduce:transition-none",
              progressStarted && "scale-x-100",
            )}
            style={{ transitionDuration: `${REMEMBERED_SESSION_DELAY_MS}ms` }}
          />
        </div>
      </section>
    </main>
  );
}

function getRememberedSessionDisplay(user: CurrentUser): { title: string; body: string } {
  const displayName = formatRememberedUserName(user);
  if (displayName) {
    return {
      title: displayName,
      body: "Am găsit sesiunea ta salvată.",
    };
  }

  const roleLabel = user.role === "trainer" ? "trainer" : "participant";
  return {
    title: user.role === "trainer" ? "Cont trainer salvat" : "Cont participant salvat",
    body: `Am găsit o sesiune salvată pentru contul ${roleLabel}.`,
  };
}

function formatRememberedUserName(user: CurrentUser): string {
  const source = user.name || user.email?.split("@")[0] || "";
  const words = source.replace(/[._-]+/g, " ").trim().split(/\s+/).filter(Boolean);
  if (words.length === 0 || isGenericSessionName(words, user.role)) return "";
  const name = words
    .map((word) => {
      if (word.length <= 2 && word === word.toUpperCase()) return word;
      return `${word.charAt(0).toLocaleUpperCase("ro-RO")}${word.slice(1).toLocaleLowerCase("ro-RO")}`;
    })
    .join(" ");
  return name;
}

function isGenericSessionName(words: string[], role: CurrentUser["role"]): boolean {
  const normalized = words.join(" ").toLocaleLowerCase("ro-RO");
  const genericNames = new Set([
    role,
    `${role} demo`,
    `demo ${role}`,
    `${role} test`,
    `test ${role}`,
    "codrut",
    "codruț",
    "test",
    "user",
    "utilizator",
    "demo",
    "admin",
    "cont",
    "account",
  ]);
  return genericNames.has(normalized);
}
