import Link from "next/link";

import { BrandMark } from "../brand/brand-mark";
import { ThemeToggle } from "../theme/theme-toggle";
import type { ShellNavItem } from "./nav";

type AppShellProps = {
  audience: "trainer" | "participant";
  eyebrow: string;
  title: string;
  description: string;
  navItems: ShellNavItem[];
  activeHref: string;
  userLabel?: string;
  children: React.ReactNode;
};

export function AppShell({
  audience,
  eyebrow,
  title,
  description,
  navItems,
  activeHref,
  userLabel,
  children,
}: AppShellProps) {
  const isTrainer = audience === "trainer";

  return (
    <div className="app-min-height bg-background">
      <header className="safe-top sticky top-0 z-40 border-b border-[var(--border)] bg-surface/95 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 md:px-6">
          <div className="flex items-center justify-between gap-3">
            <Link href="/" className="min-w-0">
              <BrandMark
                size="sm"
                subtitle={isTrainer ? "Trainer dashboard" : "Participant workspace"}
              />
            </Link>
            <div className="flex items-center gap-2">
              <ThemeToggle />
              <div className="rounded-full border border-[var(--border)] bg-surface-muted px-3 py-1 text-xs font-semibold text-foreground/70">
                {userLabel ?? (isTrainer ? "Andrei" : "Participant")}
              </div>
            </div>
          </div>

          <nav aria-label={isTrainer ? "Trainer navigation" : "Participant navigation"} className="flex gap-2 overflow-x-auto pb-1">
            {navItems.map((item) => {
              const active = item.href === activeHref;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={[
                    "tap-soft whitespace-nowrap rounded-full border px-3 py-2 text-sm font-semibold",
                    active
                      ? "border-burgundy bg-burgundy text-white"
                      : "border-[var(--border)] bg-surface text-foreground/70 hover:border-burgundy/50 hover:text-burgundy",
                  ].join(" ")}
                >
                  <span className="sm:hidden">{item.shortLabel ?? item.label}</span>
                  <span className="hidden sm:inline">{item.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-6 md:px-6 md:py-8">
        <section className="mb-6">
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-burgundy">{eyebrow}</p>
          <h1 className="mt-2 font-display text-3xl font-semibold tracking-tight text-foreground md:text-5xl">
            {title}
          </h1>
          <p className="mt-3 max-w-3xl text-base leading-7 text-foreground/65">{description}</p>
        </section>
        {children}
      </main>
    </div>
  );
}
