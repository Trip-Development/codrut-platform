"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";
import { confirmPasswordReset } from "@/api/auth";

export default function UpdatePasswordPage() {
  return (
    <Suspense fallback={<UpdatePasswordShell />}>
      <UpdatePasswordForm />
    </Suspense>
  );
}

function UpdatePasswordForm() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);

    if (!token) {
      setError("Linkul de resetare lipsește sau este invalid.");
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
      <section className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-surface p-6 shadow-sm">
        <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-xl bg-burgundy text-2xl font-bold text-white">C</div>
        <h1 className="text-center text-2xl font-bold text-foreground">Setează parola nouă</h1>
        <p className="mt-2 text-center text-sm leading-6 text-foreground/60">
          Alege o parolă nouă pentru contul tău. Linkul de resetare poate fi folosit o singură dată.
        </p>

        {success ? (
          <div className="mt-6 rounded-2xl border border-green-200 bg-green-50 p-4 text-center text-sm font-semibold text-green-800">
            Parola a fost actualizată. Te poți autentifica folosind noua parolă.
            <Link href="/login" className="mt-4 block text-burgundy">
              Înapoi la autentificare
            </Link>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="mt-6 space-y-4">
            <label className="block text-sm font-semibold text-foreground/70">
              Parola nouă
              <input
                className="mt-1 w-full rounded-xl border border-[var(--border)] bg-surface-muted px-3 py-3 text-base"
                placeholder="Minim 12 caractere"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                minLength={12}
                required
              />
            </label>
            <label className="block text-sm font-semibold text-foreground/70">
              Confirmă parola
              <input
                className="mt-1 w-full rounded-xl border border-[var(--border)] bg-surface-muted px-3 py-3 text-base"
                placeholder="Repetă parola nouă"
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                minLength={12}
                required
              />
            </label>
            {error ? (
              <p className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm font-semibold text-red-700">
                {error}
              </p>
            ) : null}
            <button
              className="tap-soft w-full rounded-xl bg-burgundy px-4 py-3 font-semibold text-white disabled:cursor-not-allowed disabled:opacity-65"
              disabled={submitting || !token}
              type="submit"
            >
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
      <section className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-surface p-6 shadow-sm">
        <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-xl bg-burgundy text-2xl font-bold text-white">C</div>
        <h1 className="text-center text-2xl font-bold text-foreground">Setează parola nouă</h1>
        <p className="mt-2 text-center text-sm leading-6 text-foreground/60">
          Se verifică linkul de resetare.
        </p>
      </section>
    </main>
  );
}
