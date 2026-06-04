"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { BrandMark } from "@/components/brand/brand-mark";

export default function RegisterPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    // Retrieve invitation data from sessionStorage
    const storedInvite = sessionStorage.getItem("codrut_invite");
    if (!storedInvite) {
      // Redirect to login if no invite details are present
      router.push("/login");
      return;
    }

    try {
      const inviteData = JSON.parse(storedInvite);
      if (!inviteData.email || !inviteData.token) {
        throw new Error("Date invitație nevalide");
      }
      setEmail(inviteData.email);
      setFullName(inviteData.fullName || "");
      setToken(inviteData.token);
      setLoading(false);
    } catch {
      router.push("/login");
    }
  }, [router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password.length < 12) {
      setError("Parola trebuie să aibă cel puțin 12 caractere.");
      return;
    }

    if (password !== confirmPassword) {
      setError("Parolele introduse nu coincid.");
      return;
    }

    setSubmitting(true);

    try {
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          email,
          password,
          token,
        }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.error?.message || "Înregistrarea a eșuat. Reîncearcă.");
      }

      // Registration successful, remove invite session and redirect to dashboard
      sessionStorage.removeItem("codrut_invite");
      router.push("/participant/dashboard");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "A apărut o eroare la înregistrare.";
      setError(msg);
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <main className="bg-vines-pattern app-min-height flex items-center justify-center bg-background px-4 py-10">
        <section className="w-full max-w-md rounded-[2.5rem] border border-[var(--border)] bg-surface p-10 text-center shadow-brand">
          <BrandMark size="lg" showText={false} className="mx-auto" />
          <div className="mt-8 flex justify-center">
            <div className="h-10 w-10 animate-spin rounded-full border-4 border-burgundy border-t-transparent"></div>
          </div>
          <p className="mt-6 text-foreground/60 font-semibold text-sm">Se încarcă datele invitației...</p>
        </section>
      </main>
    );
  }

  return (
    <main className="bg-vines-pattern app-min-height flex items-center justify-center bg-background px-4 py-10">
      <section className="shadow-brand w-full max-w-md rounded-[2.5rem] border border-[var(--border)] bg-surface p-8 md:p-10 transition-all duration-300">
        <div className="mb-8 flex flex-col items-center">
          <BrandMark size="lg" showText={false} />
          <h1 className="font-display mt-6 text-center text-3xl font-bold tracking-tight text-foreground md:text-4xl">
            Înregistrare cont
          </h1>
          <p className="mt-2 text-center text-sm leading-6 text-foreground/60">
            Setează numele și parola pentru acces permanent la platformă.
          </p>
        </div>

        {error && (
          <div className="mb-6 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-600 dark:border-red-900/30 dark:bg-red-950/20 dark:text-red-400">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-foreground/75 mb-1.5">
              Email
            </label>
            <input
              className="w-full rounded-2xl border border-[var(--border)] bg-surface-muted/50 px-4 py-3.5 text-base text-foreground/50 cursor-not-allowed outline-none"
              type="email"
              value={email}
              disabled={true}
              title="Adresa de email este blocată la cea specificată în invitație."
            />
            <p className="mt-1 text-[11px] text-foreground/45 italic">
              * Emailul este blocat la cel din invitația securizată.
            </p>
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-foreground/75 mb-1.5">
              Nume complet
            </label>
            <input
              className="w-full rounded-2xl border border-[var(--border)] bg-surface-muted px-4 py-3.5 text-base text-foreground placeholder-foreground/35 outline-none transition-all duration-200 focus:border-burgundy focus:ring-1 focus:ring-burgundy"
              type="text"
              placeholder="Numele tău"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-foreground/75 mb-1.5">
              Parolă
            </label>
            <input
              className="w-full rounded-2xl border border-[var(--border)] bg-surface-muted px-4 py-3.5 text-base text-foreground placeholder-foreground/35 outline-none transition-all duration-200 focus:border-burgundy focus:ring-1 focus:ring-burgundy"
              type="password"
              placeholder="Minim 12 caractere"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-foreground/75 mb-1.5">
              Confirmă parola
            </label>
            <input
              className="w-full rounded-2xl border border-[var(--border)] bg-surface-muted px-4 py-3.5 text-base text-foreground placeholder-foreground/35 outline-none transition-all duration-200 focus:border-burgundy focus:ring-1 focus:ring-burgundy"
              type="password"
              placeholder="Reintroduce parola"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              required
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="tap-soft mt-2 w-full rounded-2xl bg-burgundy hover:bg-burgundy-dark disabled:bg-burgundy/50 px-4 py-4 font-semibold text-white transition-colors duration-200 shadow-md flex items-center justify-center gap-2"
          >
            {submitting ? (
              <>
                <div className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent"></div>
                Se creează contul...
              </>
            ) : (
              "Finalizează înregistrarea"
            )}
          </button>
        </form>

        <div className="mt-8 pt-6 border-t border-[var(--border)] flex justify-center text-sm">
          <span className="text-foreground/50">Ai deja cont?</span>
          <Link
            href="/login"
            className="ml-2 font-bold text-burgundy hover:text-burgundy-dark transition-colors"
          >
            Intră în cont
          </Link>
        </div>
      </section>
    </main>
  );
}
