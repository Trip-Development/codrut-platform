"use client";

import Link from "next/link";
import type { FormEvent } from "react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { BrandMark } from "@/components/brand/brand-mark";
import { loginWithPassword } from "@/api/auth";

const quotes = [
  "„Liderii nu creează adepți, ei creează alți lideri.”",
  "„Feedback-ul este micul dejun al campionilor.”",
  "„Niciunul dintre noi nu este la fel de inteligent ca noi toți împreună.”",
  "„Performanța unei echipe depinde de claritatea direcției sale.”",
  "„Ascultarea activă este prima formă de respect în leadership.”",
];

export default function LoginPage() {
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
      }, 150); // Wait for fade-out animation to complete
    }, 2500); // Rotate every 2.5 seconds

    return () => clearInterval(interval);
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const session = await loginWithPassword(email, password);
      router.push(session.user.role === "trainer" ? "/trainer" : "/participant");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Autentificarea a eșuat.");
      setSubmitting(false);
    }
  };

  return (
    <main className="app-min-height flex items-center justify-center bg-background bg-vines-pattern px-4 py-10">
      <section className="surface-panel w-full max-w-md p-8 transition-all duration-150 md:p-10">
        <div className="mb-8 flex flex-col items-center">
          <BrandMark size="lg" showText={false} />
          <h1 className="font-display mt-6 text-center text-3xl font-bold tracking-tight text-foreground md:text-4xl">
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
            <label htmlFor="login-email" className="block text-xs font-bold uppercase tracking-wider text-foreground/75 mb-1.5">
              Email
            </label>
            <input
              id="login-email"
              className="control-input w-full py-3.5 text-base"
              placeholder="nume@companie.ro"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div>
            <div className="flex justify-between items-center mb-1.5">
              <label htmlFor="login-password" className="block text-xs font-bold uppercase tracking-wider text-foreground/75">
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
              id="login-password"
              className="control-input w-full py-3.5 text-base"
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
            className="btn-primary mt-2 w-full px-4 py-4"
          >
            {submitting ? "Se verifică..." : "Intră în cont"}
          </button>
          {error ? (
            <p className="status-panel-danger px-4 py-3">
              {error}
            </p>
          ) : null}
        </form>

        <div className="mt-8 pt-6 border-t border-[var(--border)] flex justify-center text-sm">
          <span className="text-foreground/50">Ești trainer sau owner?</span>
          <Link
            href="/trainer/login"
            className="ml-2 font-bold text-burgundy hover:text-burgundy-dark transition-colors"
          >
            Intră în portalul trainer
          </Link>
        </div>
      </section>
    </main>
  );
}
