"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";
import { confirmPasswordReset } from "@/api/auth";
import { PASSWORD_MIN_LENGTH, validatePasswordPolicy } from "@/api/password-policy";

export default function UpdatePasswordPage() {
  return (
    <Suspense fallback={<UpdatePasswordShell />}>
      <UpdatePasswordForm />
    </Suspense>
  );
}

function UpdatePasswordForm() {
  const searchParams = useSearchParams();
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const resetToken = searchParams.get("token") ?? "";
    setToken(resetToken);
    if (!resetToken || typeof window === "undefined") return;

    const url = new URL(window.location.href);
    url.searchParams.delete("token");
    window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`);
  }, [searchParams]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
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

    setSubmitting(true);
    try {
      await confirmPasswordReset(token, password);
      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Parola nu a putut fi resetată.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="app-min-height flex items-center justify-center bg-background px-4 py-10">
      <section className="surface-panel w-full max-w-md p-6 md:p-8">
        <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-xl bg-burgundy text-2xl font-bold text-white">C</div>
        <h1 className="text-center text-2xl font-bold text-foreground">Setează parola nouă</h1>
        <p className="mt-2 text-center text-sm leading-6 text-foreground/60">
          Alege o parolă nouă pentru contul tău. Linkul de resetare poate fi folosit o singură dată.
        </p>

        {success ? (
          <div className="status-panel-success mt-6 p-4 text-center">
            Parola a fost actualizată. Te poți autentifica folosind noua parolă.
            <Link href="/login" className="btn-secondary mt-4 w-full">
              Înapoi la autentificare
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <label className="block text-sm font-semibold text-foreground/70">
              Parola nouă
              <input
                className="control-input mt-1 w-full bg-surface-muted py-3 text-base"
                placeholder={`Minim ${PASSWORD_MIN_LENGTH} caractere`}
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                minLength={PASSWORD_MIN_LENGTH}
                required
              />
            </label>
            <label className="block text-sm font-semibold text-foreground/70">
              Confirmă parola
              <input
                className="control-input mt-1 w-full bg-surface-muted py-3 text-base"
                placeholder="Repetă parola nouă"
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                minLength={PASSWORD_MIN_LENGTH}
                required
              />
            </label>
            {error ? (
              <p className="status-panel-danger px-3 py-2">
                {error}
              </p>
            ) : null}
            <button className="btn-primary w-full px-4 py-3" disabled={submitting || !token} type="submit">
              {submitting ? "Se salvează..." : "Salvează parola"}
            </button>
            {!token ? (
              <p className="text-center text-sm text-foreground/58">
                Cere un link nou din pagina de recuperare parolă.
              </p>
            ) : null}
          </form>
        )}
      </section>
    </main>
  );
}

function UpdatePasswordShell() {
  return (
    <main className="app-min-height flex items-center justify-center bg-background px-4 py-10">
      <section className="surface-panel w-full max-w-md p-6 md:p-8">
        <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-xl bg-burgundy text-2xl font-bold text-white">C</div>
        <h1 className="text-center text-2xl font-bold text-foreground">Setează parola nouă</h1>
        <p className="mt-2 text-center text-sm leading-6 text-foreground/60">
          Se verifică linkul de resetare.
        </p>
      </section>
    </main>
  );
}
