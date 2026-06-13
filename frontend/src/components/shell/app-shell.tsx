"use client";

import Link from "next/link";
import { useState, useEffect } from "react";

import { BrandMark } from "../brand/brand-mark";
import { ThemeToggle } from "../theme/theme-toggle";
import type { ShellNavItem } from "./nav";
import { SessionBanner } from "./session-banner";
import type { SessionState } from "@/api/auth";
import { getApiBaseUrl } from "@/api/runtime";

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
  if (href.includes("/companies")) {
    return (
      <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
      </svg>
    );
  }
  if (href.includes("/projects")) {
    return (
      <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
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


let globalIsSidebarCollapsed: boolean = false;
let globalHasReadStorage: boolean = false;

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
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(globalIsSidebarCollapsed);
  const [optimisticHref, setOptimisticHref] = useState(activeHref);
  
  const isTrainer = audience === "trainer";

  const isEffectivelyCollapsed = isSidebarCollapsed;

  useEffect(() => {
    if (!globalHasReadStorage) {
      const stored = localStorage.getItem("codrut_sidebar_collapsed");
      if (stored === "true") {
        setIsSidebarCollapsed(true);
        globalIsSidebarCollapsed = true;
      }
      globalHasReadStorage = true;
    } else {
      setIsSidebarCollapsed(globalIsSidebarCollapsed);
    }
  }, []);

  const handleToggleCollapse = () => {
    const newState = !isSidebarCollapsed;
    setIsSidebarCollapsed(newState);
    globalIsSidebarCollapsed = newState;
    localStorage.setItem("codrut_sidebar_collapsed", String(newState));
  };

  useEffect(() => {
    setOptimisticHref(activeHref);
  }, [activeHref]);



  const handleLogout = async () => {
    if (isLoggingOut) return;
    setIsLoggingOut(true);
    try {
      await fetch(`${getApiBaseUrl()}/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } finally {
      window.location.href = "/";
    }
  };

  const renderNavLinks = (isDesktop: boolean) => (
    <div className="flex flex-col gap-1.5 relative mt-4">

      {navItems.map((item) => {
        const active = item.href === optimisticHref;
        return (
          <Link
            key={item.href}
            href={item.href}
            data-href={item.href}
            onClick={() => {
              setOptimisticHref(item.href);
              setMobileMenuOpen(false);
            }}
            className={[
              "tap-soft group relative flex items-center rounded-full py-3 text-sm font-bold transition-colors duration-150",
              isDesktop && isEffectivelyCollapsed ? "justify-center px-0 aspect-square h-11 mx-auto" : "gap-3.5 px-4 h-11",
              active
                ? "text-white bg-burgundy shadow-md dark:bg-[#E65C5C]"
                : "text-foreground/60 hover:text-burgundy hover:bg-burgundy/5 dark:hover:bg-burgundy/10",
            ].join(" ")}
          >
            <span className={`relative z-10 shrink-0 transition-colors ${active ? "text-white" : "text-foreground/45 group-hover:text-burgundy"}`}>
              {getNavIcon(item.href)}
            </span>
            <span className={`relative z-10 whitespace-nowrap transition-all duration-300 ${isDesktop && isEffectivelyCollapsed ? "w-0 opacity-0 overflow-hidden" : "opacity-100"}`}>
              {item.label}
            </span>
          </Link>
        );
      })}
    </div>
  );

  return (
    <div className={`app-min-height flex flex-col md:flex-row bg-background`}>
      <aside
        aria-label="Desktop sidebar"
        className={`hidden h-[100vh] shrink-0 flex-col bg-[var(--shell-sidebar)] border-r border-[var(--border)] py-6 px-4 shadow-[4px_0_24px_-12px_rgba(0,0,0,0.05)] md:sticky md:top-0 md:flex z-40 overflow-visible transition-[width] duration-200 ease-out relative ${
          isEffectivelyCollapsed ? "w-[5.5rem]" : "w-[18rem]"
        }`}
      >
        <button
          onClick={handleToggleCollapse}
          className="absolute -right-3 top-8 z-50 flex h-6 w-6 items-center justify-center rounded-full border border-[var(--border)] bg-surface text-foreground/50 hover:text-foreground shadow-sm hover:scale-110 transition-all"
        >
          <svg className={`h-3 w-3 transition-transform duration-300 ${isSidebarCollapsed ? "rotate-180" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={3}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        
        <div className={`mb-6 pt-2 shrink-0 whitespace-nowrap transition-all duration-200 ${isEffectivelyCollapsed ? "flex justify-center" : "pl-3"}`}>
          <Link
            href="/"
            className={`tap-soft group inline-block rounded-xl transition-colors hover:bg-surface-muted/50 ${isEffectivelyCollapsed ? "p-1" : "p-2 -ml-2"}`}
          >
            <BrandMark
              size="sm"
              showText={!isEffectivelyCollapsed}
              subtitle={isTrainer ? "Spațiu trainer" : "Spațiu participant"}
            />
          </Link>
        </div>

        <nav className="flex-1 overflow-y-auto overflow-x-hidden pr-2 custom-scrollbar" aria-label="Desktop navigation">
          {renderNavLinks(true)}
        </nav>

        <div className="relative mt-auto flex flex-col gap-4 pt-6 shrink-0 z-10">
          <div className="h-px w-full bg-gradient-to-r from-transparent via-[var(--border)] to-transparent absolute top-0 left-0" />
          <div className={`flex px-1 transition-all duration-200 ${isEffectivelyCollapsed ? "flex-col items-center gap-4" : "items-center justify-between gap-3"}`}>
            <button
              type="button"
              onClick={() => setAccountMenuOpen((open) => !open)}
              className={`tap-soft flex min-w-0 items-center justify-start gap-3 rounded-full border border-[var(--border)] bg-surface-muted/50 p-1.5 text-sm font-bold text-foreground hover:border-burgundy/30 hover:bg-surface transition-colors shadow-sm overflow-hidden ${isEffectivelyCollapsed ? "w-11 justify-center p-1.5 mx-auto" : "w-full pr-4"}`}
              aria-expanded={accountMenuOpen}
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-burgundy text-xs font-bold text-white shadow-inner">
                {(userLabel ?? (isTrainer ? "Andrei" : "Participant")).charAt(0).toUpperCase()}
              </div>
              <span className={`truncate text-left flex-1 transition-opacity duration-300 ${isEffectivelyCollapsed ? "opacity-0 w-0 hidden" : "opacity-100"}`}>{userLabel ?? (isTrainer ? "Andrei" : "Participant")}</span>
              <svg className={`h-4 w-4 shrink-0 text-foreground/50 transition-transform duration-300 ${accountMenuOpen ? "rotate-180" : ""} ${isEffectivelyCollapsed ? "hidden" : "block"}`} fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" d="m6 9 6 6 6-6" />
              </svg>
            </button>
            <div className={`shrink-0 transition-opacity duration-300 ${isEffectivelyCollapsed ? "hidden" : "flex items-center justify-center"}`}>
              <ThemeToggle />
            </div>
          </div>
          {accountMenuOpen ? (
            <div className="absolute bottom-full left-0 right-0 mb-3 rounded-xl border border-[var(--border)] glass-panel p-2 shadow-2xl animate-fade-in-up">
              <Link
                href={isTrainer ? "/trainer/settings" : "/participant/account"}
                className="tap-soft block rounded-xl px-4 py-2.5 text-sm font-semibold text-foreground/80 hover:bg-surface-muted hover:text-foreground"
              >
                Setări cont
              </Link>
              <button
                type="button"
                onClick={handleLogout}
                disabled={isLoggingOut}
                className="tap-soft mt-1 flex w-full items-center justify-between rounded-xl px-4 py-2.5 text-left text-sm font-bold text-red-600 hover:bg-red-50 dark:hover:bg-red-500/10 disabled:cursor-not-allowed disabled:opacity-50"
              >
                <span>{isLoggingOut ? "Se iese..." : "Deconectare"}</span>
                <svg className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 9V5.25A2.25 2.25 0 0 0 13.5 3h-6A2.25 2.25 0 0 0 5.25 5.25v13.5A2.25 2.25 0 0 0 7.5 21h6a2.25 2.25 0 0 0 2.25-2.25V15m3-3H9.75m9 0-3-3m3 3-3 3" />
                </svg>
              </button>
            </div>
          ) : null}
        </div>
      </aside>

      <header className="safe-top sticky top-0 z-40 flex items-center justify-between border-b border-[var(--border)] glass-panel px-5 py-4 shadow-sm md:hidden">
        <Link
          href="/"
          className="tap-soft group block min-w-0 rounded-xl transition-colors hover:bg-surface-muted"
        >
            <BrandMark
              size="sm"
              subtitle={isTrainer ? "Trainer" : "Participant"}
            />
        </Link>
        <div className="flex items-center gap-3">
          <ThemeToggle />
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="tap-soft rounded-full border border-[var(--border)] bg-surface/80 p-2.5 text-foreground/80 hover:bg-surface-muted shadow-sm"
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
            className="animate-slide-in absolute bottom-0 left-0 top-0 flex h-full w-[85%] max-w-[20rem] flex-col border-r border-[var(--border)] bg-surface p-6 shadow-2xl"
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
                className="tap-soft rounded-full p-2 text-foreground/50 hover:bg-surface-muted bg-surface-muted/50 border border-[var(--border)]"
                aria-label="Închide meniul"
              >
                <svg className="h-5 w-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto overflow-x-hidden">
              {renderNavLinks(false)}
            </div>
            <div className="mt-auto pt-6 relative">
              <div className="h-px w-full bg-gradient-to-r from-transparent via-[var(--border)] to-transparent absolute top-0 left-0" />
              <div className="flex items-center gap-3 rounded-full border border-[var(--border)] bg-surface-muted/50 p-1.5 pr-4 text-sm font-bold text-foreground">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-burgundy text-xs font-bold text-white shadow-inner">
                  {(userLabel ?? (isTrainer ? "Andrei" : "Participant")).charAt(0).toUpperCase()}
                </div>
                <span className="truncate text-left flex-1">{userLabel ?? (isTrainer ? "Andrei" : "Participant")}</span>
              </div>
              <button
                type="button"
                onClick={handleLogout}
                disabled={isLoggingOut}
                className="tap-soft mt-3 w-full rounded-full border border-red-200 bg-red-50 px-4 py-3 text-sm font-bold text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isLoggingOut ? "Se iese..." : "Deconectare"}
              </button>
            </div>
          </nav>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-8 md:px-10 lg:px-12 lg:py-10">
          <section className="mb-10 hero-shape p-10 md:p-14 shadow-glass animate-fade-in-up relative overflow-hidden">
            <div className="absolute inset-0 bg-hero-mesh opacity-100"></div>
            <div className="relative z-10">
              <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-burgundy/80 mb-4">{eyebrow}</p>
              <h1 className="font-display text-4xl font-bold leading-[1.1] text-foreground md:text-5xl lg:text-6xl tracking-tight">
                {title}
              </h1>
              {description && (
                <p className="mt-5 max-w-2xl text-lg leading-relaxed text-foreground/60">{description}</p>
              )}
            </div>
          </section>
          <SessionBanner session={session} note={accessNote} />
          {children}
        </main>
      </div>
    </div>
  );
}
