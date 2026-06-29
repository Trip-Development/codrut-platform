"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { BrandMark } from "@/components/brand/brand-mark";
import { requestPasswordReset } from "@/api/auth";

export default function ResetPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      await requestPasswordReset(email);
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "A apărut o eroare la trimiterea emailului. Te rugăm să încerci din nou.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="app-min-height flex items-center justify-center bg-background px-4 py-10">
      <section className="surface-panel w-full max-w-md p-8 transition-all duration-150 md:p-10">
        <div className="mb-8 flex flex-col items-center">
          <BrandMark size="lg" showText={false} />
          <h1 className="font-display mt-6 text-center text-3xl font-bold tracking-tight text-foreground md:text-4xl">
            Recuperare parolă
          </h1>
          <div className="mt-3 w-full flex items-center justify-center px-2">
            <p className="text-center text-sm font-medium leading-relaxed text-foreground/60">
              Introdu adresa de email asociată contului tău. Îți vom trimite un link securizat pentru a-ți alege o nouă parolă.
            </p>
          </div>
        </div>

        {success ? (
          <div className="animate-fade-in-up space-y-6 text-center">
            <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400">
              <svg className="h-8 w-8" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div>
              <p className="text-base font-medium text-foreground">
                Linkul de resetare a fost trimis!
              </p>
              <p className="mt-2 text-sm leading-relaxed text-foreground/60">
                Verifică-ți adresa de email <strong className="text-foreground">{email}</strong> și urmează instrucțiunile primite.
              </p>
            </div>
            <Link href="/login" className="btn-secondary mt-6 w-full px-4 py-4">
              Întoarce-te la autentificare
            </Link>
          </div>
        ) : (
          <>
            <form onSubmit={handleSubmit} className="space-y-5 animate-fade-in-up">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-foreground/75 mb-1.5">
                  Email
                </label>
                <input
                  className="control-input w-full bg-surface-muted py-3.5 text-base"
                  placeholder="nume@companie.ro"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                />
              </div>

              <button type="submit" disabled={submitting || !email} className="btn-primary mt-2 w-full gap-2 px-4 py-4">
                {submitting ? (
                  <>
                    <svg className="animate-spin -ml-1 h-4 w-4 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    Se trimite...
                  </>
                ) : (
                  "Trimite link securizat"
                )}
              </button>

              {error ? (
                <p className="status-panel-danger px-4 py-3 animate-fade-in-up">
                  {error}
                </p>
              ) : null}
            </form>

            <div className="mt-8 pt-6 border-t border-[var(--border)] flex justify-center text-sm">
              <span className="text-foreground/50">Ți-ai amintit parola?</span>
              <Link
                href="/login"
                className="ml-2 font-bold text-burgundy transition-colors hover:text-burgundy-dark"
              >
                Înapoi la autentificare
              </Link>
            </div>
          </>
        )}
      </section>
    </main>
  );
}
