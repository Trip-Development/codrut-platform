"use client";

import Link from "next/link";
import { useState } from "react";
import { BrandMark } from "@/components/brand/brand-mark";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Simulate login redirect or auth trigger
  };

  return (
    <main className="app-min-height flex items-center justify-center bg-background bg-vines-pattern px-4 py-10">
      <section className="shadow-brand w-full max-w-md rounded-[2.5rem] border border-[var(--border)] bg-surface p-8 md:p-10 transition-all duration-300">
        <div className="mb-8 flex flex-col items-center">
          <BrandMark size="lg" showText={false} />
          <h1 className="font-display mt-6 text-center text-3xl font-bold tracking-tight text-foreground md:text-4xl">
            Bine ai venit
          </h1>
          <p className="mt-2 text-center text-sm leading-6 text-foreground/60">
            Introdu acreditările pentru a accesa platforma Codrut.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          <div>
            <label className="block text-xs font-bold uppercase tracking-wider text-foreground/75 mb-1.5">
              Email
            </label>
            <input
              className="w-full rounded-2xl border border-[var(--border)] bg-surface-muted px-4 py-3.5 text-base text-foreground placeholder-foreground/35 outline-none transition-all duration-200 focus:border-burgundy focus:ring-1 focus:ring-burgundy"
              placeholder="nume@companie.ro"
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
            className="tap-soft mt-2 w-full rounded-2xl bg-burgundy hover:bg-burgundy-dark px-4 py-4 font-semibold text-white transition-colors duration-200 shadow-md"
          >
            Intră în cont
          </button>
        </form>

        <div className="mt-8 pt-6 border-t border-[var(--border)] flex justify-center text-sm">
          <span className="text-foreground/50">Nu ai un cont?</span>
          <Link
            href="/register"
            className="ml-2 font-bold text-burgundy hover:text-burgundy-dark transition-colors"
          >
            Creează cont
          </Link>
        </div>
      </section>
    </main>
  );
}
