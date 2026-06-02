import Link from "next/link";

export default function HomePage() {
  return (
    <main className="app-min-height bg-vines-pattern bg-background px-4 py-10 text-foreground md:px-6">
      <section className="mx-auto flex min-h-[calc(100dvh-5rem)] max-w-5xl flex-col justify-center">
        <div className="max-w-2xl">
          <div className="mb-8 flex items-center gap-3">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-burgundy text-2xl font-bold text-white shadow-sm">
              C
            </div>
            <div>
              <p className="text-sm font-semibold uppercase tracking-[0.18em] text-burgundy">
                Codrut Platform
              </p>
              <p className="text-sm text-foreground/55">Training, assessment, and rollout management</p>
            </div>
          </div>

          <h1 className="font-display text-4xl font-semibold tracking-tight md:text-6xl">
            Shell-ul Codrut este pregatit pentru migrare.
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-8 text-foreground/70">
            Interfata veche se muta intai ca experienta vizuala completa. Datele reale vor intra
            treptat prin API-ul FastAPI, fara Supabase sau rutare veche de prototip.
          </p>

          <div className="mt-8 flex flex-col gap-3 sm:flex-row">
            <Link
              href="/trainer"
              className="tap-soft rounded-xl bg-burgundy px-5 py-3 text-center text-sm font-bold text-white shadow-sm hover:bg-burgundy-700"
            >
              Trainer dashboard
            </Link>
            <Link
              href="/participant"
              className="tap-soft rounded-xl border border-burgundy bg-surface px-5 py-3 text-center text-sm font-bold text-burgundy hover:bg-burgundy-50"
            >
              Participant workspace
            </Link>
          </div>
        </div>
      </section>
    </main>
  );
}
