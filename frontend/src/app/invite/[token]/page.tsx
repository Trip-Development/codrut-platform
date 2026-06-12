"use client";

import { use, useEffect, useState } from "react";
import NextLink from "next/link";
import { BrandMark } from "@/components/brand/brand-mark";
import { TaskBundle } from "@/components/tasks/task-bundle";
import { resolveInviteBundle, type InviteBundle } from "@/api/invites";

type ValidInviteBundle = Extract<InviteBundle, { state: "valid" }>;

type InvitePageProps = {
  params: Promise<{ token: string }>;
};

export default function InvitePage({ params }: InvitePageProps) {
  const { token } = use(params);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<ValidInviteBundle | null>(null);

  useEffect(() => {
    async function verify() {
      try {
        const bundle = await resolveInviteBundle(token);
        if (bundle.state !== "valid") {
          throw new Error(bundle.message);
        }

        setData(bundle);

        sessionStorage.setItem(
          "codrut_invite",
          JSON.stringify({
            email: bundle.participantEmail,
            token,
            fullName: bundle.participantFullName,
            anonymousName: bundle.anonymousName,
            isLeadership: bundle.isLeadership,
          })
        );
      } catch (err) {
        const msg = err instanceof Error ? err.message : "A apărut o eroare la verificarea invitației.";
        setError(msg);
      } finally {
        setLoading(false);
      }
    }
    verify();
  }, [token]);

  if (loading) {
    return (
      <main className="bg-vines-pattern app-min-height flex items-center justify-center bg-background px-4 py-10">
        <section className="w-full max-w-md rounded-[2.5rem] border border-[var(--border)] bg-surface p-10 text-center shadow-brand">
          <BrandMark size="lg" showText={false} className="mx-auto" />
          <div className="mt-8 flex justify-center">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-burgundy border-t-transparent"></div>
          </div>
          <p className="mt-6 text-foreground/60 font-semibold text-sm">Se verifică invitația...</p>
        </section>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="bg-vines-pattern app-min-height flex items-center justify-center bg-background px-4 py-10">
        <section className="w-full max-w-md rounded-[2.5rem] border border-[var(--border)] bg-surface p-10 text-center shadow-brand">
          <BrandMark size="lg" showText={false} className="mx-auto" />
          <div className="mt-6 flex justify-center text-burgundy">
            <svg className="w-16 h-16" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
          </div>
          <h1 className="font-display mt-6 text-2xl font-bold text-foreground">Invitație nevalidă</h1>
          <p className="mt-3 text-sm text-foreground/60 leading-6">
            {error || "Nu am putut valida această invitație. Cere un link nou de la trainer."}
          </p>
          <div className="mt-8">
            <NextLink
              href="/"
              className="tap-soft block w-full rounded-2xl bg-burgundy hover:bg-burgundy-dark px-4 py-3.5 font-bold text-white transition-colors text-center"
            >
              Mergi la Codruț
            </NextLink>
          </div>
        </section>
      </main>
    );
  }

  if (data.alreadyRegistered && data.isLeadership) {
    return (
      <main className="bg-vines-pattern app-min-height flex items-center justify-center bg-background px-4 py-10">
        <section className="w-full max-w-md rounded-[2.5rem] border border-[var(--border)] bg-surface p-10 text-center shadow-brand">
          <BrandMark size="lg" showText={false} className="mx-auto" />
          <h1 className="font-display mt-8 text-2xl font-bold text-foreground">Cont deja existent</h1>
          <p className="mt-3 text-sm text-foreground/60 leading-6">
            Ai creat deja un cont de Leadership pentru adresa de e-mail <strong className="text-foreground/80">{data.participantEmail}</strong>.
          </p>
          <div className="mt-8 space-y-3">
            <NextLink
              href="/login"
              className="tap-soft block w-full rounded-2xl bg-burgundy hover:bg-burgundy-dark px-4 py-3.5 font-bold text-white transition-colors text-center"
            >
              Autentifică-te aici
            </NextLink>
            <NextLink
              href="/"
              className="tap-soft block w-full rounded-2xl border border-[var(--border)] bg-surface hover:bg-surface-muted px-4 py-3.5 font-bold text-foreground transition-colors text-center"
            >
              Pagina principală
            </NextLink>
          </div>
        </section>
      </main>
    );
  }

  if (data.isLeadership && !data.alreadyRegistered) {
    return (
      <main className="bg-vines-pattern app-min-height flex items-center justify-center bg-background px-4 py-10">
        <section className="w-full max-w-md rounded-[2.5rem] border border-[var(--border)] bg-surface p-10 text-center shadow-brand">
          <BrandMark size="lg" showText={false} className="mx-auto" />
          <p className="mt-8 text-xs font-bold uppercase tracking-[0.18em] text-burgundy">Cont Leadership</p>
          <h1 className="font-display mt-3 text-2xl font-bold text-foreground">Activează contul înainte de chestionare</h1>
          <p className="mt-3 text-sm text-foreground/60 leading-6">
            Invitația pentru <strong className="text-foreground/80">{data.participantEmail}</strong> este pregătită. Creează contul ca să vezi dashboardul tău de participant și sarcinile proiectului.
          </p>
          <div className="mt-8 space-y-3">
            <NextLink
              href="/register"
              className="tap-soft block w-full rounded-2xl bg-burgundy hover:bg-burgundy-dark px-4 py-3.5 font-bold text-white transition-colors text-center"
            >
              Înregistrează cont Leadership
            </NextLink>
            <NextLink
              href="/"
              className="tap-soft block w-full rounded-2xl border border-[var(--border)] bg-surface hover:bg-surface-muted px-4 py-3.5 font-bold text-foreground transition-colors text-center"
            >
              Pagina principală
            </NextLink>
          </div>
        </section>
      </main>
    );
  }

  return (
    <main className="bg-vines-pattern app-min-height flex items-center justify-center bg-background px-4 py-10 text-foreground">
      <section className="w-full max-w-3xl rounded-[2.5rem] border border-[var(--border)] bg-surface/90 p-8 shadow-brand backdrop-blur md:p-10">
        <NextLink href="/" className="mb-8 inline-flex">
          <BrandMark subtitle="Invitație securizată" />
        </NextLink>

        <p className="text-xs font-bold uppercase tracking-[0.18em] text-burgundy">Link proiect</p>
        <h1 className="mt-3 font-display text-4xl font-semibold text-foreground md:text-5xl tracking-tight">
          Sarcinile tale pentru acest proiect
        </h1>

        <p className="mt-4 max-w-2xl text-base leading-7 text-foreground/65">
          Acest link strânge chestionarele pentru proiectul <strong className="text-foreground/80">{data.projectName}</strong>. Vei lucra ca <strong className="text-foreground/80">{data.anonymousName ?? "participant anonim"}</strong>.
        </p>

        <div className="mt-8">
          <TaskBundle
            tasks={data.tasks}
            projectName={data.projectName}
            participantEmail={data.participantEmail}
          />
        </div>

        <div className="mt-10 flex flex-col gap-4 border-t border-[var(--border)] pt-8 sm:flex-row">
          {data.isLeadership ? (
            <NextLink
              href="/register"
              className="tap-soft rounded-2xl bg-burgundy hover:bg-burgundy-dark px-6 py-4 text-center font-bold text-white shadow-md transition-colors"
            >
              Înregistrează cont Leadership
            </NextLink>
          ) : null}
          <NextLink
            href="/"
            className="tap-soft rounded-2xl border border-[var(--border)] bg-surface hover:bg-surface-muted px-6 py-4 text-center font-bold text-foreground transition-colors sm:ml-auto"
          >
            Pagina principală
          </NextLink>
        </div>
      </section>
    </main>
  );
}
