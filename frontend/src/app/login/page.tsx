"use client";

import Link from "next/link";
import type { FormEvent } from "react";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2Icon } from "lucide-react";

import { dashboardHrefForRole, getAuthenticatedSession, loginWithPassword, type CurrentUser } from "@/api/auth";
import {
  AuthQuotePanel,
  AuthTextLink,
  REMEMBERED_SESSION_DELAY_MS,
  RememberedSessionSplash,
} from "@/components/auth/auth-shell";
import { BrandMark } from "@/components/brand/brand-mark";
import { OperationFeedback } from "@/components/presentation/operation-feedback";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { completeLoginNavigation } from "@/lib/auth-navigation";
import { safeParticipantReturnTo } from "@/lib/auth-return";

function requestedParticipantRoute(): string {
  if (typeof window === "undefined") return "/participant";
  return safeParticipantReturnTo(
    new URLSearchParams(window.location.search).get("returnTo"),
  );
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [rememberedUser, setRememberedUser] = useState<CurrentUser | null>(null);
  const submittingRef = useRef(false);

  useEffect(() => {
    const requestedEmail = new URLSearchParams(window.location.search).get("email");
    if (requestedEmail) setEmail(requestedEmail);
    let cancelled = false;
    let redirectTimer: number | undefined;
    void getAuthenticatedSession().then((session) => {
      if (cancelled || !session || session.user.accessMode === "secure_link") return;
      setRememberedUser(session.user);
      redirectTimer = window.setTimeout(() => {
        if (cancelled) return;
        router.replace(
          requestedParticipantRoute() === "/participant"
            ? dashboardHrefForRole(session.user.defaultWorkspace ?? session.user.role)
            : requestedParticipantRoute(),
        );
        router.refresh();
      }, REMEMBERED_SESSION_DELAY_MS);
    });
    return () => {
      cancelled = true;
      if (redirectTimer !== undefined) {
        window.clearTimeout(redirectTimer);
      }
    };
  }, [router]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (submittingRef.current) return;

    submittingRef.current = true;
    setError(null);
    setSubmitting(true);

    try {
      const session = await loginWithPassword(email, password);
      completeLoginNavigation(
        requestedParticipantRoute() === "/participant"
          ? dashboardHrefForRole(session.user.defaultWorkspace ?? session.user.role)
          : requestedParticipantRoute(),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Autentificarea a eșuat.");
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  if (rememberedUser) {
    return <RememberedSessionSplash user={rememberedUser} />;
  }

  return (
    <main className="grid min-h-[100dvh] bg-background text-foreground lg:grid-cols-[0.95fr_1.05fr]">
      <AuthQuotePanel variant="participant" />

      <section className="flex items-center justify-center px-4 py-10 md:px-8">
        <div className="w-full max-w-md">
          <Link href="/" className="mb-10 inline-flex rounded-lg px-2 py-1 transition-colors hover:bg-muted lg:hidden">
            <BrandMark subtitle="Spațiu participant" />
          </Link>

          <div>
            <Badge variant="outline">Autentificare</Badge>
            <h1 className="mt-5 text-4xl font-semibold leading-tight tracking-normal">
              Bine ai revenit.
            </h1>
          </div>

          <form onSubmit={handleSubmit} className="mt-8 flex flex-col gap-5">
            <FieldGroup>
              <Field data-invalid={Boolean(error) || undefined}>
                <FieldLabel htmlFor="login-email">Email</FieldLabel>
                <Input
                  id="login-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoComplete="email"
                  disabled={submitting}
                  required
                  aria-invalid={Boolean(error) || undefined}
                />
              </Field>

              <Field data-invalid={Boolean(error) || undefined}>
                <div className="flex items-center justify-between gap-3">
                  <FieldLabel htmlFor="login-password">Parolă</FieldLabel>
                  <Link href="/reset-password" className="text-sm font-semibold text-primary hover:underline">
                    Ai uitat parola?
                  </Link>
                </div>
                <Input
                  id="login-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="current-password"
                  disabled={submitting}
                  required
                  aria-invalid={Boolean(error) || undefined}
                />
              </Field>
            </FieldGroup>

            {error ? (
              <Alert variant="destructive">
                <AlertTitle>Autentificarea nu a reușit</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}

            {submitting ? (
              <OperationFeedback
                title="Verificăm accesul participant"
                detail="Confirmăm sesiunea și pregătim spațiul tău de lucru."
                meta="în verificare"
              />
            ) : null}

            <Button type="submit" size="lg" disabled={submitting} className="w-full">
              {submitting ? <Loader2Icon data-icon="inline-start" className="animate-spin" /> : null}
              {submitting ? "Verificăm accesul" : "Intră în cont"}
            </Button>
          </form>

          <div className="mt-8 flex flex-col gap-2 text-sm sm:flex-row sm:items-center sm:justify-between">
            <span className="font-medium text-muted-foreground">Ești trainer sau owner?</span>
            <AuthTextLink href="/trainer/login">Autentificare trainer</AuthTextLink>
          </div>
        </div>
      </section>
    </main>
  );
}
