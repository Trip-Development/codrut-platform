"use client";

import Link from "next/link";
import { useRef, useState, type FormEvent } from "react";
import { ArrowRightIcon, CheckCircle2Icon, Loader2Icon } from "lucide-react";

import { requestPasswordReset } from "@/api/auth";
import { AuthQuotePanel, AuthTextLink } from "@/components/auth/auth-shell";
import { BrandMark } from "@/components/brand/brand-mark";
import { OperationFeedback } from "@/components/presentation/operation-feedback";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";

export default function ResetPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submittingRef = useRef(false);

  const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (submittingRef.current) return;

    const submittedEmail = String(new FormData(e.currentTarget).get("email") ?? "").trim();
    if (!submittedEmail) {
      setError("Introdu adresa de email asociată contului.");
      return;
    }

    submittingRef.current = true;
    setEmail(submittedEmail);
    setError(null);
    setSubmitting(true);

    try {
      await requestPasswordReset(submittedEmail);
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "A apărut o eroare la trimiterea emailului. Te rugăm să încerci din nou.");
    } finally {
      submittingRef.current = false;
      setSubmitting(false);
    }
  };

  return (
    <main className="grid min-h-[100dvh] bg-background text-foreground lg:grid-cols-[0.9fr_1.1fr]">
      <AuthQuotePanel variant="recovery" />

      <section className="flex items-center justify-center px-4 py-10 md:px-8">
        <div className="w-full max-w-md">
          <Link href="/" className="mb-10 inline-flex rounded-lg px-2 py-1 transition-colors hover:bg-muted lg:hidden">
            <BrandMark subtitle="Recuperare acces" />
          </Link>

          {success ? (
            <div className="rounded-lg border bg-surface p-6 shadow-sm">
              <CheckCircle2Icon className="size-9 text-primary" aria-hidden="true" />
              <h1 className="mt-6 text-3xl font-semibold leading-tight tracking-normal">
                Verifică emailul.
              </h1>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                Am trimis instrucțiunile către <strong className="text-foreground">{email}</strong>.
              </p>
              <Button asChild variant="outline" size="lg" className="mt-8 w-full">
                <Link href="/login">
                  Întoarce-te la autentificare
                  <ArrowRightIcon data-icon="inline-end" />
                </Link>
              </Button>
            </div>
          ) : (
            <>
              <Badge variant="outline">Recuperare parolă</Badge>
              <h1 className="mt-5 text-4xl font-semibold leading-tight tracking-normal">
                Primește un link securizat.
              </h1>
              <p className="mt-3 text-sm leading-6 text-muted-foreground">
                Introdu adresa asociată contului. Îți trimitem pașii de resetare.
              </p>

              <form onSubmit={handleSubmit} className="mt-8 flex flex-col gap-5">
                <FieldGroup>
                  <Field data-invalid={Boolean(error) || undefined}>
                    <FieldLabel htmlFor="reset-email">Email</FieldLabel>
                    <Input
                      id="reset-email"
                      name="email"
                      type="email"
                      placeholder="nume@companie.ro"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      autoComplete="email"
                      disabled={submitting}
                      required
                      aria-invalid={Boolean(error) || undefined}
                    />
                  </Field>
                </FieldGroup>

                {error ? (
                  <Alert variant="destructive">
                    <AlertTitle>Emailul nu a fost trimis</AlertTitle>
                    <AlertDescription>{error}</AlertDescription>
                  </Alert>
                ) : null}

                {submitting ? (
                  <OperationFeedback
                    title="Trimitem linkul securizat"
                    detail="Verificăm adresa și pregătim instrucțiunile de resetare."
                    meta="în trimitere"
                  />
                ) : null}

                <Button type="submit" size="lg" disabled={submitting} className="w-full">
                  {submitting ? <Loader2Icon data-icon="inline-start" className="animate-spin" /> : null}
                  {submitting ? "Trimitem linkul" : "Trimite link securizat"}
                </Button>
              </form>

              <div className="mt-8 flex flex-col gap-2 text-sm sm:flex-row sm:items-center sm:justify-between">
                <span className="font-medium text-muted-foreground">Ți-ai amintit parola?</span>
                <AuthTextLink href="/login">Înapoi la autentificare</AuthTextLink>
              </div>
            </>
          )}
        </div>
      </section>
    </main>
  );
}
