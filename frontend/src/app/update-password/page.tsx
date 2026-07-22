"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState, type FormEvent } from "react";
import { ArrowRightIcon, CheckCircle2Icon, Loader2Icon } from "lucide-react";

import { confirmPasswordReset } from "@/api/auth";
import {
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  PASSWORD_POLICY_HELP,
  validatePasswordPolicy,
} from "@/api/password-policy";
import { AuthQuotePanel } from "@/components/auth/auth-shell";
import { BrandMark } from "@/components/brand/brand-mark";
import { OperationFeedback } from "@/components/presentation/operation-feedback";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

export default function UpdatePasswordPage() {
  return (
    <Suspense fallback={<UpdatePasswordShell />}>
      <UpdatePasswordForm />
    </Suspense>
  );
}

function UpdatePasswordForm() {
  const searchParams = useSearchParams();
  const initialTokenRef = useRef(searchParams.get("token") ?? "");
  const [token] = useState(initialTokenRef.current);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submittingRef = useRef(false);

  useEffect(() => {
    if (!token || typeof window === "undefined") return;

    const url = new URL(window.location.href);
    url.searchParams.delete("token");
    window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`);
  }, [token]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (submittingRef.current) return;

    setError(null);

    if (!token) {
      setError("Linkul de resetare lipsește sau este invalid.");
      return;
    }
    const passwordError = validatePasswordPolicy(password);
    if (passwordError) {
      setError(passwordError);
      return;
    }
    if (password !== confirmPassword) {
      setError("Parolele introduse nu coincid.");
      return;
    }

    submittingRef.current = true;
    setSubmitting(true);
    try {
      await confirmPasswordReset(token, password);
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Parola nu a putut fi resetată.");
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  return (
    <PasswordFrame>
      {success ? (
        <section className="rounded-lg border bg-surface p-6 shadow-sm">
          <CheckCircle2Icon className="size-9 text-primary" aria-hidden="true" />
          <h1 className="mt-6 text-3xl font-semibold leading-tight tracking-normal">
            Parola a fost actualizată.
          </h1>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            Te poți autentifica folosind noua parolă.
          </p>
          <Button asChild variant="outline" size="lg" className="mt-8 w-full">
            <Link href="/login">
              Înapoi la autentificare
              <ArrowRightIcon data-icon="inline-end" />
            </Link>
          </Button>
        </section>
      ) : (
        <>
          <Badge variant="outline">Parolă nouă</Badge>
          <h1 className="mt-5 text-4xl font-semibold leading-tight tracking-normal">
            Setează parola nouă.
          </h1>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            Linkul de resetare poate fi folosit o singură dată.
          </p>

          <form onSubmit={handleSubmit} className="mt-8 flex flex-col gap-5">
            <FieldGroup>
              <Field data-invalid={Boolean(error) || undefined}>
                <FieldLabel htmlFor="update-password-new">Parola nouă</FieldLabel>
                <Input
                  id="update-password-new"
                  type="password"
                  placeholder="Parolă sigură"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  minLength={PASSWORD_MIN_LENGTH}
                  maxLength={PASSWORD_MAX_LENGTH}
                  autoComplete="new-password"
                  disabled={submitting}
                  required
                  aria-invalid={Boolean(error) || undefined}
                />
                <FieldDescription>{PASSWORD_POLICY_HELP}</FieldDescription>
              </Field>

              <Field data-invalid={Boolean(error) || undefined}>
                <FieldLabel htmlFor="update-password-confirm">Confirmă parola</FieldLabel>
                <Input
                  id="update-password-confirm"
                  type="password"
                  placeholder="Repetă parola nouă"
                  value={confirmPassword}
                  onChange={(event) => setConfirmPassword(event.target.value)}
                  minLength={PASSWORD_MIN_LENGTH}
                  maxLength={PASSWORD_MAX_LENGTH}
                  autoComplete="new-password"
                  disabled={submitting}
                  required
                  aria-invalid={Boolean(error) || undefined}
                />
              </Field>
            </FieldGroup>

            {error ? (
              <Alert variant="destructive">
                <AlertTitle>Parola nu a fost salvată</AlertTitle>
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            ) : null}

            {submitting ? (
              <OperationFeedback
                title="Salvăm parola nouă"
                detail="Actualizăm accesul contului și invalidăm linkul folosit."
                meta="în salvare"
              />
            ) : null}

            <Button className="w-full" size="lg" disabled={submitting || !token} type="submit">
              {submitting ? <Loader2Icon data-icon="inline-start" className="animate-spin" /> : null}
              {submitting ? "Salvăm parola" : "Salvează parola"}
            </Button>
            {!token ? (
              <p className="text-center text-sm font-medium text-muted-foreground">
                Cere un link nou din pagina de recuperare parolă.
              </p>
            ) : null}
          </form>
        </>
      )}
    </PasswordFrame>
  );
}

function UpdatePasswordShell() {
  return (
    <PasswordFrame>
      <OperationFeedback
        title="Verificăm linkul de resetare"
        detail="Ascundem codul de securitate din adresă înainte să afișăm formularul."
        meta="în verificare"
      />
    </PasswordFrame>
  );
}

function PasswordFrame({ children }: { children: React.ReactNode }) {
  return (
    <main className="grid min-h-[100dvh] bg-background text-foreground lg:grid-cols-[0.9fr_1.1fr]">
      <AuthQuotePanel variant="security" />

      <section className="flex items-center justify-center px-4 py-10 md:px-8">
        <div className="w-full max-w-md">
          <Link href="/" className="mb-10 inline-flex rounded-lg px-2 py-1 transition-colors hover:bg-muted lg:hidden">
            <BrandMark subtitle="Securitate cont" />
          </Link>
          {children}
        </div>
      </section>
    </main>
  );
}
