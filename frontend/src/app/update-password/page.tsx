import Link from "next/link";

export default function UpdatePasswordPage() {
  return (
    <main className="app-min-height flex items-center justify-center bg-background px-4 py-10">
      <section className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-surface p-6 shadow-sm">
        <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-xl bg-burgundy text-2xl font-bold text-white">C</div>
        <h1 className="text-center text-2xl font-bold text-foreground">Setează parola nouă</h1>
        <p className="mt-2 text-center text-sm leading-6 text-foreground/60">Ecran recuperat pentru callback-ul de recovery sau setup inițial.</p>
        <label className="mt-6 block text-sm font-semibold text-foreground/70">
          Parola nouă
          <input className="mt-1 w-full rounded-xl border border-[var(--border)] bg-surface-muted px-3 py-3 text-base" placeholder="Minim 8 caractere" type="password" />
        </label>
        <button className="tap-soft mt-4 w-full rounded-xl bg-burgundy px-4 py-3 font-semibold text-white">Salvează parola</button>
        <p className="mt-5 text-center text-sm">
          <Link href="/participant" className="font-semibold text-burgundy">Continuă la workspace</Link>
        </p>
      </section>
    </main>
  );
}
