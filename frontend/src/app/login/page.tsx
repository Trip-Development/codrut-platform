import Link from "next/link";

import { BrandMark } from "@/components/brand/brand-mark";

export default function LoginPage() {
  return (
    <main className="app-min-height flex items-center justify-center bg-background px-4 py-10">
      <section className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-surface p-6 shadow-sm">
        <div className="mb-6 flex justify-center">
          <BrandMark size="lg" showText={false} />
        </div>
        <h1 className="text-center text-2xl font-bold text-foreground">Bine ai revenit</h1>
        <p className="mt-2 text-center text-sm leading-6 text-foreground/60">Autentificare recuperata din vechiul app, pregatita pentru noul backend de auth.</p>
        <div className="mt-6 space-y-4">
          <label className="block text-sm font-semibold text-foreground/70">
            Email
            <input className="mt-1 w-full rounded-xl border border-[var(--border)] bg-surface-muted px-3 py-3 text-base" placeholder="nume@companie.ro" type="email" />
          </label>
          <label className="block text-sm font-semibold text-foreground/70">
            Parola
            <input className="mt-1 w-full rounded-xl border border-[var(--border)] bg-surface-muted px-3 py-3 text-base" placeholder="Introdu parola" type="password" />
          </label>
          <button className="tap-soft w-full rounded-xl bg-burgundy px-4 py-3 font-semibold text-white">Intra in cont</button>
        </div>
        <div className="mt-5 flex justify-between text-sm font-semibold text-burgundy">
          <Link href="/register">Creeaza cont</Link>
          <Link href="/reset-password">Ai uitat parola?</Link>
        </div>
      </section>
    </main>
  );
}
