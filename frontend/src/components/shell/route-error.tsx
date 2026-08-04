"use client";

import Link from "next/link";
import {
  AlertTriangleIcon,
  ArrowLeftIcon,
  HomeIcon,
  RefreshCcwIcon,
} from "lucide-react";

import { BrandMark } from "@/components/brand/brand-mark";
import { AppShell } from "@/components/shell/app-shell";
import { participantNavItems, trainerNavItems } from "@/components/shell/nav";
import { Button } from "@/components/ui/button";

type RouteError = Error & { digest?: string };

type RouteErrorContentProps = {
  eyebrow: string;
  title: string;
  description: string;
  homeHref: string;
  loginHref: string;
  reset: () => void;
  error?: RouteError;
};

export function RootRouteError({
  error,
  reset,
}: {
  error: RouteError;
  reset: () => void;
}) {
  return (
    <main className="min-h-[100dvh] bg-background px-4 py-8 text-foreground md:px-8">
      <div className="mx-auto flex min-h-[calc(100dvh-4rem)] w-full max-w-6xl flex-col">
        <header className="flex items-center justify-between gap-4">
          <Link href="/" className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/45">
            <BrandMark subtitle="Platformă de training și coaching" />
          </Link>
          <Button asChild variant="outline" size="sm">
            <Link href="/login">Autentificare</Link>
          </Button>
        </header>

        <section className="grid flex-1 items-center gap-10 py-16 lg:grid-cols-[minmax(0,0.82fr)_minmax(18rem,0.44fr)]">
          <RouteErrorContent
            eyebrow="Eroare"
            title="Ceva nu s-a încărcat."
            description="Pagina s-a oprit înainte să termine încărcarea. Reîncearcă sau revino la intrarea principală."
            homeHref="/"
            loginHref="/login"
            reset={reset}
            error={error}
          />
          <ErrorContextCard />
        </section>
      </div>
    </main>
  );
}

export function TrainerRouteError({
  error,
  reset,
}: {
  error: RouteError;
  reset: () => void;
}) {
  return (
    <AppShell
      audience="trainer"
      eyebrow=""
      title="Pagina nu s-a încărcat"
      description=""
      navItems={trainerNavItems}
      activeHref="/trainer"
      accountIdentityPending
      showHeader={false}
    >
      <section className="grid min-h-[calc(100dvh-6rem)] items-center gap-6 lg:grid-cols-[minmax(0,0.78fr)_minmax(18rem,0.36fr)]">
        <RouteErrorContent
          eyebrow="Portal trainer"
          title="Nu am putut încărca zona trainer."
          description="Datele sau componenta acestei pagini au eșuat la încărcare. Poți reîncerca fără să pierzi sesiunea."
          homeHref="/trainer"
          loginHref="/trainer/login"
          reset={reset}
          error={error}
        />
        <ErrorContextCard />
      </section>
    </AppShell>
  );
}

export function ParticipantRouteError({
  error,
  reset,
}: {
  error: RouteError;
  reset: () => void;
}) {
  return (
    <AppShell
      audience="participant"
      eyebrow=""
      title="Pagina nu s-a încărcat"
      description=""
      navItems={participantNavItems}
      activeHref="/participant"
      accountIdentityPending
      showHeader={false}
    >
      <section className="grid min-h-[calc(100dvh-6rem)] items-center gap-6 lg:grid-cols-[minmax(0,0.78fr)_minmax(18rem,0.36fr)]">
        <RouteErrorContent
          eyebrow="Spațiu participant"
          title="Nu am putut încărca pagina."
          description="Răspunsurile salvate pe server rămân în cont. Reîncearcă pagina sau revino la spațiul participant."
          homeHref="/participant"
          loginHref="/login"
          reset={reset}
          error={error}
        />
        <ErrorContextCard />
      </section>
    </AppShell>
  );
}

function RouteErrorContent({
  eyebrow,
  title,
  description,
  homeHref,
  loginHref,
  reset,
  error,
}: RouteErrorContentProps) {
  const digest = typeof error?.digest === "string" && error.digest ? error.digest : null;

  return (
    <div role="alert" aria-live="assertive" className="min-w-0">
      <p className="inline-flex items-center gap-2 text-sm font-semibold text-primary">
        <AlertTriangleIcon aria-hidden="true" className="size-4" strokeWidth={1.8} />
        {eyebrow}
      </p>
      <h1 className="mt-5 max-w-3xl text-5xl font-semibold leading-[0.98] tracking-normal text-foreground md:text-7xl">
        {title}
      </h1>
      <p className="mt-6 max-w-xl text-base leading-7 text-muted-foreground">
        {description}
      </p>
      {digest ? (
        <p className="mt-4 w-fit rounded-lg bg-muted px-3 py-2 font-mono text-xs font-semibold text-muted-foreground">
          Ref: {digest}
        </p>
      ) : null}
      <div className="mt-8 flex flex-wrap gap-3">
        <Button type="button" size="lg" onClick={reset}>
          <RefreshCcwIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
          Reîncearcă
        </Button>
        <Button asChild variant="outline" size="lg">
          <Link href={homeHref}>
            <HomeIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
            Înapoi
          </Link>
        </Button>
        <Button asChild variant="ghost" size="lg">
          <Link href={loginHref}>
            <ArrowLeftIcon data-icon="inline-start" aria-hidden="true" strokeWidth={1.8} />
            Autentificare
          </Link>
        </Button>
      </div>
    </div>
  );
}

function ErrorContextCard() {
  return (
    <aside className="rounded-lg border bg-surface p-5 shadow-none">
      <div className="rounded-lg bg-primary p-4 text-primary-foreground">
        <p className="text-sm font-semibold">Cody</p>
        <p className="mt-3 text-3xl font-semibold leading-tight">Recuperare curată.</p>
      </div>
      <div className="mt-4 grid gap-3">
        <div className="rounded-lg bg-muted p-4">
          <p className="text-xs font-semibold text-muted-foreground">Sesiune</p>
          <p className="mt-1 text-sm font-semibold text-foreground">Cookie-ul rămâne activ cât timp reîncerci încărcarea.</p>
        </div>
        <div className="rounded-lg bg-muted p-4">
          <p className="text-xs font-semibold text-muted-foreground">Date</p>
          <p className="mt-1 text-sm font-semibold text-foreground">Acțiunile finalizate rămân înregistrate pe server.</p>
        </div>
      </div>
    </aside>
  );
}
