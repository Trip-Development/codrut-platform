"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties } from "react";
import {
  BarChart3Icon,
  Building2Icon,
  ChevronDownIcon,
  ClipboardListIcon,
  FolderIcon,
  HomeIcon,
  InfoIcon,
  LogOutIcon,
  MailIcon,
  MenuIcon,
  NetworkIcon,
  SettingsIcon,
  Repeat2Icon,
  UserIcon,
  UsersIcon,
  XIcon,
  type LucideIcon,
} from "lucide-react";

import type { SessionState } from "@/api/auth";
import { apiFetch, ensureCsrfToken } from "@/api/http";
import { getApiBaseUrl } from "@/api/runtime";
import { BrandMark } from "@/components/brand/brand-mark";
import { InlineFeedback } from "@/components/presentation/inline-feedback";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { ThemeSelector } from "@/components/theme/theme-selector";
import { cn } from "@/utils/cn";
import type { ShellNavItem } from "./nav";
import { SessionBanner } from "./session-banner";

type AppShellProps = {
  audience: "trainer" | "participant";
  eyebrow?: string;
  title: string;
  description?: string;
  navItems: ShellNavItem[];
  activeHref: string;
  userLabel?: string;
  session?: SessionState;
  accountIdentityPending?: boolean;
  accessNote?: string;
  showHeader?: boolean;
  headerActions?: React.ReactNode;
  children: React.ReactNode;
};

const NAV_ICON_BY_MATCH: Array<[string, LucideIcon]> = [
  ["/companies", Building2Icon],
  ["/projects", FolderIcon],
  ["/participants", UsersIcon],
  ["/roster", UsersIcon],
  ["/org-chart", NetworkIcon],
  ["/org", NetworkIcon],
  ["/email", MailIcon],
  ["/onboarding", MailIcon],
  ["/questionnaires", ClipboardListIcon],
  ["/tasks", ClipboardListIcon],
  ["/final-evaluation", ClipboardListIcon],
  ["/chat", InfoIcon],
  ["/reports", BarChart3Icon],
  ["/results", BarChart3Icon],
  ["/settings", SettingsIcon],
  ["/account", UserIcon],
];

const SIDEBAR_COLLAPSED_STORAGE_KEY = "codrut_sidebar_collapsed";

let globalIsSidebarCollapsed = false;
type AccountIdentitySnapshot = {
  label: string;
  avatarSeed: string;
  avatarPaletteKey?: number | null;
};

const accountIdentitySnapshots: Partial<Record<AppShellProps["audience"], AccountIdentitySnapshot>> = {};

export function clearAppShellIdentityCache(audience?: AppShellProps["audience"]) {
  if (audience) {
    delete accountIdentitySnapshots[audience];
    return;
  }
  delete accountIdentitySnapshots.trainer;
  delete accountIdentitySnapshots.participant;
}

function syncSidebarCollapsedDataset(collapsed: boolean) {
  if (typeof document === "undefined") {
    return;
  }

  document.documentElement.dataset.sidebarCollapsed = String(collapsed);
}

function getInitialSidebarCollapsed(): boolean {
  if (typeof window === "undefined") {
    return globalIsSidebarCollapsed;
  }

  const prePaintValue = document.documentElement.dataset.sidebarCollapsed;
  if (prePaintValue === "true" || prePaintValue === "false") {
    globalIsSidebarCollapsed = prePaintValue === "true";
    return globalIsSidebarCollapsed;
  }

  try {
    const stored = window.localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY);
    if (stored === "true" || stored === "false") {
      globalIsSidebarCollapsed = stored === "true";
      syncSidebarCollapsedDataset(globalIsSidebarCollapsed);
    }
  } catch {
    return globalIsSidebarCollapsed;
  }

  return globalIsSidebarCollapsed;
}

function getNavIcon(href: string): LucideIcon {
  if (href.endsWith("/trainer") || href === "/participant") {
    return HomeIcon;
  }

  return NAV_ICON_BY_MATCH.find(([match]) => href.includes(match))?.[1] ?? InfoIcon;
}

function getPathnameActiveHref(pathname: string, navItems: ShellNavItem[], fallbackHref: string): string {
  const normalizedPathname = pathname === "/" ? pathname : pathname.replace(/\/+$/, "");

  return navItems
    .filter(({ href }) => normalizedPathname === href || normalizedPathname.startsWith(`${href}/`))
    .sort((left, right) => right.href.length - left.href.length)[0]?.href ?? fallbackHref;
}

export function AppShell({
  audience,
  eyebrow = "",
  title,
  description = "",
  navItems,
  activeHref,
  userLabel,
  session,
  accountIdentityPending = false,
  accessNote,
  showHeader = true,
  headerActions,
  children,
}: AppShellProps) {
  const pathname = usePathname();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [isLoggingOut, setIsLoggingOut] = useState(false);
  const [logoutError, setLogoutError] = useState<string | null>(null);
  const [accountMenuOpen, setAccountMenuOpen] = useState(false);
  // Match the server markup first; pre-paint CSS keeps the stored collapsed width stable until React syncs.
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isSidebarWidthTransitioning, setIsSidebarWidthTransitioning] = useState(false);
  const [optimisticHref, setOptimisticHref] = useState<string | null>(null);
  const [retainedIdentity, setRetainedIdentity] = useState<AccountIdentitySnapshot | null>(
    () => accountIdentitySnapshots[audience] ?? null,
  );
  const sidebarTransitionTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const logoutSubmittingRef = useRef(false);

  const isTrainer = audience === "trainer";
  const label = userLabel ?? session?.user.name ?? (isTrainer ? "Trainer" : "Participant");
  const avatarSeed = session?.user.id ?? `${audience}:${label}`;
  const avatarPaletteKey = session?.user.avatarPaletteKey;
  const currentIdentity = session?.user.id
    ? { label, avatarSeed, avatarPaletteKey }
    : null;
  const displayedIdentity = currentIdentity ?? (accountIdentityPending ? retainedIdentity : null);
  const displayedLabel = displayedIdentity?.label ?? label;
  const displayedAvatarSeed = displayedIdentity?.avatarSeed ?? avatarSeed;
  const displayedAvatarPaletteKey = displayedIdentity?.avatarPaletteKey ?? avatarPaletteKey;
  const identityIsPending = accountIdentityPending && displayedIdentity === null;
  const accountHref = isTrainer ? "/trainer/settings" : "/participant/account";
  const availableWorkspaces = session?.user.availableWorkspaces ?? [session?.user.role ?? audience];
  const alternateWorkspaceHref =
    availableWorkspaces.includes("trainer")
    && availableWorkspaces.includes("participant")
      ? isTrainer
        ? "/participant"
        : "/trainer"
      : null;
  const alternateWorkspaceLabel = isTrainer
    ? "Spațiu participant"
    : "Portal trainer";
  const currentNavHref = optimisticHref ?? getPathnameActiveHref(pathname, navItems, activeHref);

  useLayoutEffect(() => {
    const collapsed = getInitialSidebarCollapsed();
    setIsSidebarCollapsed(collapsed);
    syncSidebarCollapsedDataset(collapsed);
  }, []);

  useLayoutEffect(() => {
    if (!session?.user.id) return;
    const nextIdentity = { label, avatarSeed, avatarPaletteKey };
    accountIdentitySnapshots[audience] = nextIdentity;
    setRetainedIdentity((previous) => (
      previous?.label === nextIdentity.label
        && previous.avatarSeed === nextIdentity.avatarSeed
        && previous.avatarPaletteKey === nextIdentity.avatarPaletteKey
        ? previous
        : nextIdentity
    ));
  }, [audience, avatarPaletteKey, avatarSeed, label, session?.user.id]);

  useEffect(() => {
    return () => {
      if (sidebarTransitionTimer.current) {
        clearTimeout(sidebarTransitionTimer.current);
      }
    };
  }, []);

  useEffect(() => {
    setOptimisticHref(null);
  }, [pathname]);

  useEffect(() => {
    void ensureCsrfToken();
  }, []);

  function handleToggleCollapse() {
    if (sidebarTransitionTimer.current) {
      clearTimeout(sidebarTransitionTimer.current);
    }
    setIsSidebarWidthTransitioning(true);
    sidebarTransitionTimer.current = setTimeout(() => {
      setIsSidebarWidthTransitioning(false);
      sidebarTransitionTimer.current = null;
    }, 220);

    setIsSidebarCollapsed((currentState) => {
      const nextState = !currentState;
      globalIsSidebarCollapsed = nextState;
      syncSidebarCollapsedDataset(nextState);

      try {
        window.localStorage.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, String(nextState));
      } catch {
        // Keep the in-memory preference if localStorage is unavailable.
      }

      return nextState;
    });
  }

  async function handleLogout() {
    if (logoutSubmittingRef.current) return;

    logoutSubmittingRef.current = true;
    setIsLoggingOut(true);
    setLogoutError(null);
    try {
      await ensureCsrfToken();
      const response = await apiFetch(`${getApiBaseUrl()}/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok && response.status !== 401) {
        logoutSubmittingRef.current = false;
        setIsLoggingOut(false);
        setLogoutError("Deconectarea nu a reușit. Încearcă din nou.");
        return;
      }
      clearAppShellIdentityCache(audience);
      window.location.href = "/";
    } catch {
      logoutSubmittingRef.current = false;
      setIsLoggingOut(false);
      setLogoutError("Deconectarea nu a reușit. Verifică conexiunea și încearcă din nou.");
    }
  }

  const renderNavLinks = (isDesktop: boolean) => (
    <div className={cn("flex flex-col", isDesktop && isSidebarCollapsed ? "gap-2" : "gap-1.5")}>
      {navItems.map((item) => {
        const Icon = getNavIcon(item.href);
        const active = item.href === currentNavHref;
        const collapsed = isDesktop && isSidebarCollapsed;

        return (
          <Link
            key={item.href}
            href={item.href}
            data-sidebar-nav-link
            title={collapsed ? item.label : undefined}
            aria-current={active ? "page" : undefined}
            onClick={() => {
              setOptimisticHref(item.href);
              setMobileMenuOpen(false);
            }}
            className={cn(
              "group relative flex items-center text-sm font-semibold transition-[background-color,color,box-shadow,transform]",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45 focus-visible:ring-offset-2 focus-visible:ring-offset-background",
              collapsed ? "mx-auto size-8 justify-center rounded-md" : "h-10 gap-3 rounded-md px-2.5",
              active
                ? "bg-sidebar-accent text-foreground"
                : "text-muted-foreground hover:bg-sidebar-accent hover:text-foreground",
            )}
          >
            <Icon
              aria-hidden="true"
              className={cn(
                "size-4 shrink-0 transition-colors",
                active ? "text-brand-text" : "text-foreground/45 group-hover:text-foreground/72",
              )}
              strokeWidth={1.8}
            />
            <span data-sidebar-label className={cn("truncate", collapsed && "sr-only")}>{item.label}</span>
          </Link>
        );
      })}
    </div>
  );

  return (
    <div className="app-min-height flex flex-col bg-background text-foreground lg:flex-row">
      <aside
        aria-label="Navigare principală"
        data-codrut-sidebar
        className={cn(
          "hidden h-[100dvh] shrink-0 border-r bg-sidebar text-sidebar-foreground lg:sticky lg:top-0 lg:z-30 lg:flex lg:flex-col",
          isSidebarWidthTransitioning ? "transition-[width] duration-200 ease-out" : "transition-none",
          isSidebarCollapsed ? "w-14" : "w-[248px]",
        )}
      >
        <div className={cn("flex items-center gap-2 px-3 py-4", isSidebarCollapsed && "justify-center px-2")}>
          <Link
            href="/"
            data-sidebar-brand
            className={cn(
              "rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45",
              isSidebarCollapsed && "hidden",
            )}
            aria-label="Cody"
          >
            <BrandMark
              size="sm"
              subtitle=""
            />
          </Link>
          <Button
            type="button"
            variant="ghost"
            size="icon-xs"
            data-sidebar-collapse-button
            aria-label={isSidebarCollapsed ? "Extinde meniul lateral" : "Restrânge meniul lateral"}
            aria-pressed={isSidebarCollapsed}
            onClick={handleToggleCollapse}
            className={cn(
              "text-muted-foreground hover:bg-sidebar-accent hover:text-foreground",
              !isSidebarCollapsed && "ml-auto",
            )}
          >
            <MenuIcon aria-hidden="true" strokeWidth={1.8} />
          </Button>
        </div>

        <nav className={cn("flex-1 overflow-y-auto py-2", isSidebarCollapsed ? "px-2" : "px-3")} aria-label="Rute aplicație">
          {renderNavLinks(true)}
        </nav>

        <div className={cn("relative mt-auto border-t border-sidebar-border/80", isSidebarCollapsed ? "px-2 py-3" : "px-3 py-4")}>

          {accountMenuOpen ? (
            <>
              <Button
                type="button"
                variant="ghost"
                aria-label="Închide meniul contului"
                className="fixed inset-0 z-40 h-auto w-auto cursor-default rounded-none border-0 bg-transparent p-0 hover:bg-transparent focus-visible:ring-0 focus-visible:ring-offset-0"
                onClick={() => setAccountMenuOpen(false)}
              />
              <div
                data-sidebar-account-menu
                className="absolute bottom-[4.75rem] left-3 z-50 flex w-64 flex-col gap-1 rounded-lg border bg-popover p-2 text-popover-foreground shadow-xl"
              >
                <div className="flex items-center gap-3 rounded-lg bg-muted p-3">
                  <ProfileMark
                    className="size-10"
                    audience={audience}
                    seed={displayedAvatarSeed}
                    paletteKey={displayedAvatarPaletteKey}
                    pending={identityIsPending}
                  />
                  <div className="min-w-0">
                    {identityIsPending ? (
                      <span className="block h-4 w-24 animate-pulse rounded bg-foreground/10" aria-label="Se încarcă identitatea contului" />
                    ) : (
                      <p className="truncate text-sm font-semibold">{displayedLabel}</p>
                    )}
                  </div>
                </div>

                <div className="grid grid-cols-[minmax(0,1fr)_8rem] items-center gap-3 px-3 py-2">
                  <span className="text-xs font-medium text-muted-foreground">Temă</span>
                  <ThemeSelector className="h-9 w-full min-w-0 bg-control px-3 font-medium" />
                </div>

                <Separator />

                {alternateWorkspaceHref ? (
                  <Button asChild variant="ghost" className="justify-start">
                    <Link href={alternateWorkspaceHref} onClick={() => setAccountMenuOpen(false)}>
                      <Repeat2Icon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
                      {alternateWorkspaceLabel}
                    </Link>
                  </Button>
                ) : null}

                {logoutError ? (
                  <InlineFeedback tone="danger" className="px-3 py-2" descriptionClassName="text-xs leading-5">
                    {logoutError}
                  </InlineFeedback>
                ) : null}

                <Button asChild variant="ghost" className="justify-start">
                  <Link href={accountHref} onClick={() => setAccountMenuOpen(false)}>
                    <SettingsIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
                    Setări cont
                  </Link>
                </Button>

                <Button
                  type="button"
                  variant="ghost"
                  onClick={handleLogout}
                  disabled={isLoggingOut}
                  className="justify-start text-destructive hover:text-destructive"
                >
                  <LogOutIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
                  {isLoggingOut ? "Închidem sesiunea" : "Deconectare"}
                </Button>
              </div>
            </>
          ) : null}

          <Button
            type="button"
            variant="ghost"
            onClick={() => setAccountMenuOpen((open) => !open)}
            aria-expanded={accountMenuOpen}
            data-sidebar-account-trigger
            className={cn(
              "group min-w-0 text-left hover:bg-sidebar-accent",
              isSidebarCollapsed ? "mx-auto size-10 justify-center" : "w-full gap-3 p-1.5 pr-2",
            )}
          >
            <ProfileMark
              className="size-8"
              audience={audience}
              seed={displayedAvatarSeed}
              paletteKey={displayedAvatarPaletteKey}
              pending={identityIsPending}
            />
            {!isSidebarCollapsed ? (
              <>
                <span data-sidebar-account-label className="min-w-0 flex-1">
                  {identityIsPending ? (
                    <span className="block h-3.5 w-20 animate-pulse rounded bg-foreground/10" aria-label="Se încarcă identitatea contului" />
                  ) : (
                    <span className="block truncate text-sm font-semibold leading-tight">{displayedLabel}</span>
                  )}
                </span>
                <ChevronDownIcon
                  data-sidebar-account-chevron
                  aria-hidden="true"
                  className={cn("shrink-0 text-muted-foreground transition-transform", accountMenuOpen && "rotate-180")}
                  strokeWidth={1.8}
                />
              </>
            ) : (
              <span className="sr-only">{displayedLabel}</span>
            )}
          </Button>
        </div>
      </aside>

      <header className="safe-top sticky top-0 z-40 flex items-center justify-between border-b bg-surface/95 px-4 py-3 lg:hidden">
        <Link
          href="/"
          className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45"
          aria-label="Cody"
        >
          <BrandMark size="sm" subtitle="" />
        </Link>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            aria-label="Deschide meniul de navigare"
            className="border-0 shadow-none"
          >
            <MenuIcon aria-hidden="true" strokeWidth={1.8} />
          </Button>
        </div>
      </header>

      {mobileMenuOpen ? (
        <div
          className="fixed inset-0 z-50 bg-foreground/35 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        >
          <nav
            className="animate-slide-in absolute bottom-0 left-0 top-0 flex h-full w-[86%] max-w-80 flex-col border-r bg-surface p-5 shadow-xl"
            onClick={(event) => event.stopPropagation()}
            aria-label="Navigare mobilă"
          >
            <div className="mb-6 flex items-center justify-between gap-4">
              <BrandMark size="sm" subtitle="" />
              <Button
                type="button"
                variant="ghost"
                size="icon-sm"
                onClick={() => setMobileMenuOpen(false)}
                aria-label="Închide meniul"
              >
                <XIcon aria-hidden="true" strokeWidth={1.8} />
              </Button>
            </div>

            <div className="flex-1 overflow-y-auto">{renderNavLinks(false)}</div>

            <div className="mt-auto flex flex-col gap-3 pt-5">
              <Separator />
              <div className="flex items-center gap-3 rounded-lg border bg-muted p-2">
                <ProfileMark
                  className="size-9"
                  audience={audience}
                  seed={displayedAvatarSeed}
                  paletteKey={displayedAvatarPaletteKey}
                  pending={identityIsPending}
                />
                <div className="min-w-0 flex-1">
                  {identityIsPending ? (
                    <span className="block h-4 w-24 animate-pulse rounded bg-foreground/10" aria-label="Se încarcă identitatea contului" />
                  ) : (
                    <p className="truncate text-sm font-semibold">{displayedLabel}</p>
                  )}
                </div>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-sm font-medium text-muted-foreground">Temă</span>
                <ThemeSelector className="h-10 min-w-36 bg-control px-3 font-medium" />
              </div>
              {alternateWorkspaceHref ? (
                <Button asChild variant="outline" className="w-full justify-start">
                  <Link href={alternateWorkspaceHref} onClick={() => setMobileMenuOpen(false)}>
                    <Repeat2Icon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
                    {alternateWorkspaceLabel}
                  </Link>
                </Button>
              ) : null}
              {logoutError ? (
                <InlineFeedback tone="danger" className="px-3 py-2" descriptionClassName="text-xs leading-5">
                  {logoutError}
                </InlineFeedback>
              ) : null}
              <Button
                type="button"
                variant="outline"
                onClick={handleLogout}
                disabled={isLoggingOut}
                className="w-full justify-start text-destructive hover:text-destructive"
              >
                <LogOutIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
                {isLoggingOut ? "Închidem sesiunea" : "Deconectare"}
              </Button>
            </div>
          </nav>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-5 md:px-6 lg:px-6 lg:py-6">
          {showHeader ? (
            <section className="mb-7 flex flex-col items-start justify-between gap-4 px-1 py-2 md:flex-row md:gap-6">
              <div className="min-w-0">
                {eyebrow ? (
                  <p className="text-[0.68rem] font-semibold uppercase tracking-[0.16em] text-brand-text">{eyebrow}</p>
                ) : null}
                <h1 className="text-[28px] font-semibold leading-[34px] tracking-[-0.02em] text-foreground">
                  {title}
                </h1>
                {description ? (
                  <p className="mt-3 max-w-3xl text-sm leading-6 text-muted-foreground">{description}</p>
                ) : null}
              </div>
              {headerActions ? (
                <div className="hidden shrink-0 items-center gap-2 md:flex">{headerActions}</div>
              ) : null}
              {headerActions ? (
                <div className="flex w-full items-center gap-2 md:hidden">{headerActions}</div>
              ) : null}
            </section>
          ) : null}
          <SessionBanner session={session} note={accessNote} />
          {children}
        </main>
      </div>
    </div>
  );
}

function ProfileMark({
  audience,
  seed,
  paletteKey,
  className,
  pending = false,
}: {
  audience: AppShellProps["audience"];
  seed: string;
  paletteKey?: number | null;
  className?: string;
  pending?: boolean;
}) {
  if (pending) {
    return (
      <span
        aria-hidden="true"
        className={cn("inline-flex shrink-0 animate-pulse rounded-full bg-foreground/10", className)}
      />
    );
  }
  const palette = profilePalette(`${audience}:${seed}`, paletteKey);

  return (
    <span
      aria-hidden="true"
      data-profile-avatar
      data-avatar-palette-key={paletteKey ?? undefined}
      style={palette.base}
      className={cn(
        "relative inline-flex shrink-0 overflow-hidden rounded-full shadow-[inset_0_1px_1px_rgba(255,255,255,0.56),0_10px_24px_-16px_rgba(0,0,0,0.55)]",
        className,
      )}
    >
      <span
        className="absolute -left-[18%] top-[8%] size-[66%] rounded-full blur-[1.5px]"
        style={palette.first}
      />
      <span
        className="absolute bottom-[-18%] right-[-12%] size-[72%] rounded-full blur-[2px]"
        style={palette.second}
      />
      <span className="absolute inset-[18%] rounded-full bg-white/18 blur-[3px]" />
    </span>
  );
}

const AVATAR_PALETTE_SPACE = 55_520_640;

export function profilePalette(seed: string, paletteKey?: number | null): {
  base: CSSProperties;
  first: CSSProperties;
  second: CSSProperties;
} {
  const persistedPalette = decodeAvatarPaletteKey(paletteKey);
  const primaryHash = unsignedHash(seed);
  const secondaryHash = unsignedHash(`${seed}:secondary`);
  const primaryHue = persistedPalette?.primaryHue ?? (primaryHash % 360);
  const highlightOffset = persistedPalette?.highlightOffset ?? (secondaryHash % 68);
  const depthOffset = persistedPalette?.depthOffset ?? (primaryHash % 54);
  const angleOffset = persistedPalette?.angleOffset ?? (secondaryHash % 42);
  const highlightHue = (primaryHue + 24 + highlightOffset) % 360;
  const depthHue = (primaryHue + 154 + depthOffset) % 360;
  const angle = 22 + angleOffset;
  const base = `hsl(${primaryHue} 52% 31%)`;
  const first = `hsl(${highlightHue} 76% 68%)`;
  const second = `hsl(${depthHue} 48% 22%)`;

  return {
    base: {
      backgroundColor: base,
      backgroundImage: `linear-gradient(${angle}deg, transparent 12%, hsl(${highlightHue} 78% 72% / 0.18) 48%, transparent 72%), radial-gradient(circle at 32% 22%, ${first} 0, transparent 38%), radial-gradient(circle at 74% 80%, ${second} 0, transparent 48%)`,
    },
    first: { backgroundColor: first },
    second: { backgroundColor: second },
  };
}

function decodeAvatarPaletteKey(paletteKey?: number | null): {
  primaryHue: number;
  highlightOffset: number;
  depthOffset: number;
  angleOffset: number;
} | null {
  if (
    paletteKey === null
    || paletteKey === undefined
    || !Number.isSafeInteger(paletteKey)
    || paletteKey < 0
    || paletteKey >= AVATAR_PALETTE_SPACE
  ) {
    return null;
  }

  let remaining = paletteKey;
  const primaryHue = remaining % 360;
  remaining = Math.floor(remaining / 360);
  const highlightOffset = remaining % 68;
  remaining = Math.floor(remaining / 68);
  const depthOffset = remaining % 54;
  remaining = Math.floor(remaining / 54);
  const angleOffset = remaining % 42;
  return { primaryHue, highlightOffset, depthOffset, angleOffset };
}

function unsignedHash(value: string): number {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}
