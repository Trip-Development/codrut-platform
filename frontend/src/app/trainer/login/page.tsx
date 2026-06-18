"use client";

import Link from "next/link";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { BrandMark } from "@/components/brand/brand-mark";
import { loginWithPassword } from "@/api/auth";

const quotes = [
  "„Performanța unei echipe crește atunci când feedback-ul devine obicei.”",
  "„Rolul unui trainer este de a facilita auto-descoperirea.”",
  "„Fiecare echipă are o dinamică unică; identifică tiparele pentru a debloca potențialul.”",
  "„Evaluarea este doar începutul procesului de transformare.”",
];

export default function TrainerLoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [quoteIdx, setQuoteIdx] = useState(0);
  const [fade, setFade] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const interval = setInterval(() => {
      setFade(false);
      setTimeout(() => {
        setQuoteIdx((prev) => (prev + 1) % quotes.length);
        setFade(true);
      }, 150);
    }, 2500);

    return () => clearInterval(interval);
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const session = await loginWithPassword(email, password);
      if (session.user.role !== "trainer") {
        throw new Error("Acest cont nu are acces la portalul de trainer.");
      }
      router.push("/trainer");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Autentificarea a eșuat.");
      setSubmitting(false);
    }
  };

  return (
    <main className="app-min-height flex items-center justify-center bg-vines-inverted relative px-4 py-10 overflow-hidden">
      
      <section className="relative shadow-brand w-full max-w-md rounded-[2.5rem] border border-[var(--border)] bg-surface p-8 md:p-10 transition-all duration-150">
        <div className="mb-8 flex flex-col items-center">
          <BrandMark size="lg" showText={false} />

          <span className="mt-4 flex items-center gap-1 text-[11px] font-bold text-burgundy bg-burgundy/10 px-2.5 py-1 rounded-full border border-burgundy/20 uppercase tracking-wider shadow-sm">
            Portal Trainer & Admin
          </span>

          <h1 className="font-display mt-4 text-center text-3xl font-bold tracking-tight text-foreground md:text-4xl">
            Bine ai venit
          </h1>

          <div className="mt-3 w-full min-h-[3rem] flex items-center justify-center px-2">
            <p className={`text-center text-sm italic font-medium leading-relaxed text-foreground/56 transition-all duration-150 ${fade ? "opacity-100 scale-100" : "opacity-0 scale-95"}`}>
              {quotes[quoteIdx]}
            </p>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-foreground/75 mb-1.5">
              Email Trainer
            </label>
            <input
              className="w-full rounded-2xl border border-[var(--border)] bg-surface-muted px-4 py-3.5 text-base text-foreground placeholder-foreground/35 outline-none transition-all duration-200 focus:border-burgundy focus:ring-1 focus:ring-burgundy"
              placeholder="andrei@codrut.ro"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div>
            <div className="flex justify-between items-center mb-1.5">
              <label className="block text-xs font-bold uppercase tracking-wider text-foreground/75">
                Parolă
              </label>
              <Link
                href="/reset-password"
                className="text-xs font-semibold text-burgundy hover:text-burgundy-dark transition-colors"
              >
                Ai uitat parola?
              </Link>
            </div>
            <input
              className="w-full rounded-2xl border border-[var(--border)] bg-surface-muted px-4 py-3.5 text-base text-foreground placeholder-foreground/35 outline-none transition-all duration-200 focus:border-burgundy focus:ring-1 focus:ring-burgundy"
              placeholder="Introdu parola"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          <button
            type="submit"
            disabled={submitting}
            className="tap-soft mt-2 w-full rounded-2xl bg-burgundy hover:bg-burgundy-dark px-4 py-4 font-semibold text-white transition-colors duration-200 shadow-md disabled:cursor-not-allowed disabled:opacity-65"
          >
            {submitting ? "Se verifică..." : "Intră în portal"}
          </button>
          {error ? (
            <p className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm font-semibold text-red-700">
              {error}
            </p>
          ) : null}
        </form>

        <div className="mt-8 pt-6 border-t border-[var(--border)] flex justify-center text-sm">
          <span className="text-foreground/50">Ești participant?</span>
          <Link
            href="/login"
            className="ml-2 font-bold text-burgundy hover:text-burgundy-dark transition-colors"
          >
            Intră în workspace-ul tău
          </Link>
        </div>
      </section>
    </main>
  );
}
