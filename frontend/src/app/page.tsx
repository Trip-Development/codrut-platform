export default function HomePage() {
  return (
    <main className="min-h-screen bg-codrut-cream px-6 py-12 text-codrut-ink">
      <section className="mx-auto flex max-w-4xl flex-col gap-8 rounded-3xl border border-codrut-burgundy/15 bg-white/75 p-8 shadow-sm">
        <div>
          <p className="text-sm font-semibold uppercase tracking-[0.3em] text-codrut-burgundy">
            Codrut Platform
          </p>
          <h1 className="mt-4 font-display text-4xl font-semibold tracking-tight md:text-6xl">
            Modular monolith scaffold is online.
          </h1>
        </div>
        <p className="max-w-2xl text-lg leading-8 text-codrut-ink/75">
          Next.js renders the interface. FastAPI owns application data and domain behavior.
          Traefik routes this page and the backend API through the same edge.
        </p>
        <div className="rounded-2xl bg-codrut-burgundy px-5 py-4 text-white">
          <p className="text-sm uppercase tracking-[0.2em] text-white/70">Scaffold status</p>
          <p className="mt-2 text-2xl font-semibold">Ready for module implementation</p>
        </div>
      </section>
    </main>
  );
}
