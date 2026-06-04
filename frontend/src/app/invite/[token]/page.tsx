"use client";

import { use, useEffect, useState } from "react";
import NextLink from "next/link";
import { BrandMark } from "@/components/brand/brand-mark";
import { SessionBanner } from "@/components/shell/session-banner";
import { TaskBundle } from "@/components/tasks/task-bundle";
import { audienceAccessNote } from "@/api/auth";
import { resolveInviteBundle } from "@/api/invites";

type InviteTask = {
  id: string;
  title: string;
  status: "not_started" | "in_progress" | "completed";
  detail: string;
  href: string;
  assignmentId: string;
  targetLabel: string;
  estimatedMinutes: number;
  questionnaireKey: string;
};

type VerifyData = {
  email: string;
  full_name: string;
  is_leadership: boolean;
  already_registered: boolean;
  project_name: string;
  tasks: InviteTask[];
};

type InvitePageProps = {
  params: Promise<{ token: string }>;
};

export default function InvitePage({ params }: InvitePageProps) {
  const { token } = use(params);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState<VerifyData | null>(null);

  useEffect(() => {
    async function verify() {
      try {
        if (token === "demo-token" || token === "expired-demo") {
          const bundle = await resolveInviteBundle(token);
          if (bundle.state !== "valid") {
            throw new Error(bundle.message);
          }
          setData({
            email: bundle.participantEmail,
            full_name: "Participant demo",
            is_leadership: false,
            already_registered: false,
            project_name: bundle.projectName,
            tasks: bundle.tasks,
          });
          return;
        }

        const res = await fetch(`/api/auth/invite/verify?token=${encodeURIComponent(token)}`);
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.error?.message || "Invitația este nevalidă sau a expirat.");
        }
        const verifyData: VerifyData = await res.json();
        setData(verifyData);

        sessionStorage.setItem(
          "codrut_invite",
          JSON.stringify({
            email: verifyData.email,
            token,
            fullName: verifyData.full_name,
            isLeadership: verifyData.is_leadership,
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

  if (data.already_registered) {
    return (
      <main className="bg-vines-pattern app-min-height flex items-center justify-center bg-background px-4 py-10">
        <section className="w-full max-w-md rounded-[2.5rem] border border-[var(--border)] bg-surface p-10 text-center shadow-brand">
          <BrandMark size="lg" showText={false} className="mx-auto" />
          <h1 className="font-display mt-8 text-2xl font-bold text-foreground">Cont deja existent</h1>
          <p className="mt-3 text-sm text-foreground/60 leading-6">
            Ai creat deja un cont de Leadership pentru adresa de e-mail <strong className="text-foreground/80">{data.email}</strong>.
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
          Acest link strânge toate chestionarele asociate e-mailului <strong className="text-foreground/80">{data.email}</strong> în proiectul <strong className="text-foreground/80">{data.project_name}</strong>.
        </p>

        <div className="mt-6">
          <SessionBanner note={audienceAccessNote(data.is_leadership ? "participant" : "invitee")} />
        </div>

        <div className="mt-8">
          <TaskBundle
            tasks={data.tasks}
            projectName={data.project_name}
            participantEmail={data.email}
            deadlineLabel="finalul evaluării"
          />
        </div>

        <div className="mt-10 flex flex-col gap-4 sm:flex-row border-t border-[var(--border)] pt-8">
          {data.is_leadership ? (
            <NextLink
              href="/register"
              className="tap-soft rounded-2xl bg-burgundy hover:bg-burgundy-dark px-6 py-4 text-center font-bold text-white shadow-md transition-colors"
            >
              Înregistrează cont Leadership
            </NextLink>
          ) : (
            <NextLink
              href={data.tasks[0]?.href ?? "/participant/questionnaires"}
              className="tap-soft rounded-2xl bg-burgundy hover:bg-burgundy-dark px-6 py-4 text-center font-bold text-white shadow-md transition-colors"
            >
              Începe completarea
            </NextLink>
          )}
          <NextLink
            href="/"
            className="tap-soft rounded-2xl border border-[var(--border)] bg-surface hover:bg-surface-muted px-6 py-4 text-center font-bold text-foreground transition-colors"
          >
            Pagina principală
          </NextLink>
        </div>
      </section>
    </main>
  );
}
