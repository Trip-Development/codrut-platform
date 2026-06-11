"use client";

import Link from "next/link";
import { useState } from "react";

import { BrandMark } from "../brand/brand-mark";
import { ThemeToggle } from "../theme/theme-toggle";
import type { ShellNavItem } from "./nav";
import { SessionBanner } from "./session-banner";
import type { SessionState } from "@/api/auth";

type AppShellProps = {
  audience: "trainer" | "participant";
  eyebrow: string;
  title: string;
  description: string;
  navItems: ShellNavItem[];
  activeHref: string;
  userLabel?: string;
  session?: SessionState;
  accessNote?: string;
  children: React.ReactNode;
};

function getNavIcon(href: string) {
  if (href.endsWith("/trainer") || href === "/participant") {
    return (
      <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    );
  }
  if (href.includes("/companies") || href.includes("/projects")) {
    return (
      <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 21h18M5 21V8.8a1.8 1.8 0 0 1 1.8-1.8h6.4A1.8 1.8 0 0 1 15 8.8V21M8 11h1.5M8 14h1.5M8 17h1.5M15 12h2.2A1.8 1.8 0 0 1 19 13.8V21" />
      </svg>
    );
  }
  if (href.includes("/roster") || href.includes("/participants") || href.includes("/account")) {
    return (
      <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM12 14a7 7 0 0 0-7 7h14a7 7 0 0 0-7-7Z" />
      </svg>
    );
  }
  if (href.includes("/org") || href.includes("/org-chart")) {
    return (
      <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v4m0 0H7.5A2.5 2.5 0 0 0 5 10.5V13m7-5h4.5A2.5 2.5 0 0 1 19 10.5V13M5 13h5v5H5v-5Zm9 0h5v5h-5v-5Z" />
      </svg>
    );
  }
  if (href.includes("/email") || href.includes("/onboarding")) {
    return (
      <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    );
  }
  if (href.includes("/questionnaires") || href.includes("/tasks")) {
    return (
      <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2Z" />
      </svg>
    );
  }
  if (href.includes("/final-evaluation")) {
    return (
      <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 21v-4m0 0V5a2 2 0 012-2h6.5l1 1H21l-3 6 3 6h-8.5l-1-1H5a2 2 0 00-2 2zm9-13.5V9" />
      </svg>
    );
  }
  if (href.includes("/chat")) {
    return (
      <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 0 1-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    );
  }
  if (href.includes("/reports")) {
    return (
      <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.907c.961 0 1.36 1.253.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.772-.557-.373-1.81.588-1.81h4.906a1 1 0 00.95-.69l1.519-4.674z" />
      </svg>
    );
  }
  if (href.includes("/settings")) {
    return (
      <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M10.3 4.3 11 2h2l.7 2.3a7.8 7.8 0 0 1 1.6.7l2.1-1.1 1.4 1.4-1.1 2.1c.3.5.5 1 .7 1.6L21 10v2l-2.3.7a7.8 7.8 0 0 1-.7 1.6l1.1 2.1-1.4 1.4-2.1-1.1c-.5.3-1 .5-1.6.7L13 20h-2l-.7-2.3a7.8 7.8 0 0 1-1.6-.7l-2.1 1.1-1.4-1.4 1.1-2.1c-.3-.5-.5-1-.7-1.6L3 12v-2l2.3-.7c.2-.6.4-1.1.7-1.6L4.9 5.6l1.4-1.4L8.7 5c.5-.3 1-.5 1.6-.7Z" />
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 11a3 3 0 1 0 6 0 3 3 0 0 0-6 0Z" />
      </svg>
    );
  }
  return (
    <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
      <path strokeLinecap="round" strokeLinejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
    </svg>
  );
}

export function AppShell({
  audience,
  eyebrow,
  title,
  description,
  navItems,
  activeHref,
  userLabel,
  session,
  accessNote,
  children,
}: AppShellProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const isTrainer = audience === "trainer";

  const renderNavLinks = () => (
    <div className="flex flex-col gap-1.5">
      {navItems.map((item) => {
        const active = item.href === activeHref;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => setMobileMenuOpen(false)}
            className={[
              "tap-soft group relative flex items-center gap-3.5 rounded-2xl px-4 py-3.5 text-sm font-semibold",
              active
                ? "bg-burgundy text-white shadow-md shadow-burgundy/12"
                : "text-foreground/72 hover:bg-surface-muted hover:text-burgundy",
            ].join(" ")}
          >
            <span className={active ? "text-white" : "text-foreground/48 group-hover:text-burgundy"}>{getNavIcon(item.href)}</span>
            <span className="truncate">{item.label}</span>
          </Link>
        );
      })}
    </div>
  );

  return (
    <div className={`app-min-height flex flex-col bg-background md:flex-row ${audience === "participant" ? "bg-vines-pattern" : ""}`}>
      <aside className="hidden h-screen w-64 shrink-0 flex-col border-r border-[var(--border)] bg-[var(--shell-sidebar)] p-6 shadow-sm backdrop-blur md:sticky md:top-0 md:flex">
        <div className="mb-8">
          <Link
            href="/"
            className="tap-soft group -m-2 block rounded-2xl p-2 transition-colors hover:bg-surface-muted"
          >
            <BrandMark
              size="sm"
              subtitle={isTrainer ? "Spațiu trainer" : "Spațiu participant"}
            />
          </Link>
        </div>

        <nav className="flex-1 overflow-y-auto" aria-label="Desktop navigation">
          {renderNavLinks()}
        </nav>

        <div className="mt-auto flex flex-col gap-4 border-t border-[var(--border)] pt-6">
          <div className="flex items-center justify-between gap-3">
            <div className="max-w-[130px] truncate rounded-full border border-[var(--border)] bg-surface-muted px-3 py-1.5 text-xs font-bold text-foreground/75">
              {userLabel ?? (isTrainer ? "Andrei" : "Participant")}
            </div>
            <ThemeToggle />
          </div>
        </div>
      </aside>

      <header className="safe-top sticky top-0 z-40 flex items-center justify-between border-b border-[var(--border)] bg-surface/90 px-4 py-3 shadow-sm backdrop-blur-xl md:hidden">
        <Link
          href="/"
          className="tap-soft group -m-2 block min-w-0 rounded-2xl p-2 transition-colors hover:bg-surface-muted"
        >
            <BrandMark
              size="sm"
              subtitle={isTrainer ? "Trainer" : "Participant"}
            />
        </Link>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="tap-soft rounded-xl border border-[var(--border)] bg-surface p-2.5 text-foreground/75 hover:bg-surface-muted"
            aria-label="Deschide meniul de navigare"
          >
            <svg className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        </div>
      </header>

      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm transition-opacity duration-300 md:hidden"
          onClick={() => setMobileMenuOpen(false)}
        >
          <nav
            className="animate-slide-in absolute bottom-0 left-0 top-0 flex h-full w-72 flex-col border-r border-[var(--border)] bg-[var(--shell-sidebar)] p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
            aria-label="Navigare mobilă"
          >
            <div className="mb-8 flex items-center justify-between">
                <BrandMark
                  size="sm"
                  subtitle={isTrainer ? "Trainer" : "Participant"}
                />
              <button
                onClick={() => setMobileMenuOpen(false)}
                className="tap-soft rounded-xl p-1.5 text-foreground/50 hover:bg-surface-muted"
                aria-label="Închide meniul"
              >
                <svg className="h-6 w-6" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              {renderNavLinks()}
            </div>
            <div className="mt-auto border-t border-[var(--border)] pt-6">
              <div className="rounded-full border border-[var(--border)] bg-surface-muted px-3 py-2 text-center text-xs font-bold text-foreground/75">
                {userLabel ?? (isTrainer ? "Andrei" : "Participant")}
              </div>
            </div>
          </nav>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-7 md:px-8 lg:px-10 lg:py-10">
          <section className="mb-7 border-b border-[var(--border)] pb-6">
            <p className="text-sm font-semibold text-burgundy/75">{eyebrow}</p>
            <h1 className="mt-2 font-display text-3xl font-semibold leading-tight text-foreground md:text-4xl">
              {title}
            </h1>
            <p className="mt-3 max-w-3xl text-base leading-7 text-foreground/64">{description}</p>
          </section>
          <SessionBanner session={session} note={accessNote} />
          {children}
        </main>
      </div>
    </div>
  );
}
