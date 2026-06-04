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

// Helper to get SVG icon path based on navigation item href
function getNavIcon(href: string) {
  if (href.endsWith("/trainer") || href === "/participant") {
    // Home / Dashboard
    return (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
      </svg>
    );
  }
  if (href.includes("/projects") || href.includes("/questionnaires")) {
    // Folders / Assessments
    return (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    );
  }
  if (href.includes("/org-chart")) {
    // Org Chart
    return (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94-3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
      </svg>
    );
  }
  if (href.includes("/participants") || href.includes("/account")) {
    // Users / Profile
    return (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
      </svg>
    );
  }
  if (href.includes("/email") || href.includes("/onboarding")) {
    // Messaging / Outbox
    return (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    );
  }
  if (href.includes("/reports") || href.includes("/final-evaluation") || href.includes("/chat")) {
    // Analytics / Star
    return (
      <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.907c.961 0 1.36 1.253.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.772-.557-.373-1.81.588-1.81h4.906a1 1 0 00.95-.69l1.519-4.674z" />
      </svg>
    );
  }
  return (
    <svg className="w-5 h-5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
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
              "tap-soft flex items-center gap-3.5 rounded-2xl px-4 py-3.5 text-sm font-semibold transition-all duration-200",
              active
                ? "bg-burgundy text-white shadow-md shadow-burgundy/10"
                : "text-foreground/75 hover:bg-surface-muted hover:text-burgundy",
            ].join(" ")}
          >
            {getNavIcon(item.href)}
            <span>{item.label}</span>
          </Link>
        );
      })}
    </div>
  );

  return (
    <div className="app-min-height flex flex-col md:flex-row bg-background">
      {/* Desktop Sidebar (Left) */}
      <aside className="hidden md:flex w-64 shrink-0 flex-col border-r border-[var(--border)] bg-surface p-6 sticky top-0 h-screen">
        <div className="mb-8">
          <Link href="/">
            <BrandMark
              size="sm"
              subtitle={isTrainer ? "Trainer dashboard" : "Participant workspace"}
            />
          </Link>
        </div>

        <nav className="flex-1 overflow-y-auto" aria-label="Desktop navigation">
          {renderNavLinks()}
        </nav>

        <div className="mt-auto pt-6 border-t border-[var(--border)] flex flex-col gap-4">
          <div className="flex items-center justify-between gap-3">
            <div className="rounded-full border border-[var(--border)] bg-surface-muted px-3 py-1.5 text-xs font-bold text-foreground/75 truncate max-w-[130px]">
              {userLabel ?? (isTrainer ? "Andrei" : "Participant")}
            </div>
            <ThemeToggle />
          </div>
        </div>
      </aside>

      {/* Mobile Top Header (Fixed Top) */}
      <header className="safe-top md:hidden sticky top-0 z-40 border-b border-[var(--border)] bg-surface/90 shadow-sm backdrop-blur-xl flex items-center justify-between px-4 py-3">
        <Link href="/">
          <BrandMark
            size="sm"
            subtitle={isTrainer ? "Trainer" : "Participant"}
          />
        </Link>
        <div className="flex items-center gap-2">
          <ThemeToggle />
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="p-2.5 rounded-xl border border-[var(--border)] bg-surface text-foreground/75 hover:bg-surface-muted active:scale-95 transition-transform"
            aria-label="Toggle Navigation Menu"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
        </div>
      </header>

      {/* Mobile Menu Drawer Overlay */}
      {mobileMenuOpen && (
        <div
          className="md:hidden fixed inset-0 z-50 bg-black/40 backdrop-blur-sm transition-opacity duration-300"
          onClick={() => setMobileMenuOpen(false)}
        >
          <nav
            className="absolute left-0 top-0 bottom-0 w-72 bg-surface p-6 shadow-2xl flex flex-col h-full animate-slide-in"
            onClick={(e) => e.stopPropagation()}
            aria-label="Mobile Drawer Navigation"
          >
            <div className="flex items-center justify-between mb-8">
              <BrandMark
                size="sm"
                subtitle={isTrainer ? "Trainer" : "Participant"}
              />
              <button
                onClick={() => setMobileMenuOpen(false)}
                className="p-1.5 rounded-xl text-foreground/50 hover:bg-surface-muted"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              {renderNavLinks()}
            </div>
            <div className="mt-auto pt-6 border-t border-[var(--border)]">
              <div className="rounded-full border border-[var(--border)] bg-surface-muted px-3 py-2 text-center text-xs font-bold text-foreground/75">
                {userLabel ?? (isTrainer ? "Andrei" : "Participant")}
              </div>
            </div>
          </nav>
        </div>
      )}

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        <main className="flex-1 px-4 py-8 md:px-10 md:py-12 max-w-7xl mx-auto w-full">
          <section className="mb-8">
            <p className="text-xs font-bold uppercase tracking-[0.18em] text-burgundy">{eyebrow}</p>
            <h1 className="mt-2.5 font-display text-4xl font-semibold tracking-tight text-foreground md:text-5xl">
              {title}
            </h1>
            <p className="mt-3.5 max-w-3xl text-base leading-7 text-foreground/65">{description}</p>
          </section>
          <SessionBanner session={session} note={accessNote} />
          {children}
        </main>
      </div>
    </div>
  );
}
