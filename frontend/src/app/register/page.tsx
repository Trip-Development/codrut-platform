import Link from "next/link";

export default function RegisterPage() {
  return (
    <main className="app-min-height flex items-center justify-center bg-background px-4 py-10">
      <section className="w-full max-w-md rounded-2xl border border-[var(--border)] bg-surface p-6 shadow-sm">
        <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-xl bg-burgundy text-2xl font-bold text-white">C</div>
        <h1 className="text-center text-2xl font-bold text-foreground">Inregistrare securizata</h1>
        <p className="mt-2 text-center text-sm leading-6 text-foreground/60">Flux recuperat pentru setup cont din email sau cod de acces.</p>
        <div className="mt-6 space-y-4">
          {["Cod invitatie", "Email", "Nume afisat", "Parola"].map((label) => (
            <label key={label} className="block text-sm font-semibold text-foreground/70">
              {label}
              <input className="mt-1 w-full rounded-xl border border-[var(--border)] bg-surface-muted px-3 py-3 text-base" />
            </label>
          ))}
          <button className="tap-soft w-full rounded-xl bg-burgundy px-4 py-3 font-semibold text-white">Creeaza cont</button>
        </div>
        <p className="mt-5 text-center text-sm text-foreground/60">
          Ai deja cont? <Link href="/login" className="font-semibold text-burgundy">Intra aici</Link>
        </p>
      </section>
    </main>
  );
}
